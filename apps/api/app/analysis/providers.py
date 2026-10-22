from abc import ABC, abstractmethod
import base64
import hashlib
import json
from time import monotonic
import httpx2 as httpx
from app.analysis.prompts import TEXT_PROMPT, VISION_PROMPT
from app.analysis.schemas import AnimalFeatures, ExtractionOutput, parse_extraction_output
from app.core.config import settings

_CAPABILITIES = {}


class ProviderError(Exception):
    def __init__(self, code: str, retryable: bool = True):
        super().__init__(code)
        self.code, self.retryable = code, retryable


class LLMProvider(ABC):
    @abstractmethod
    async def extract_observation(self,text: str) -> AnimalFeatures: ...


class VisionProvider(ABC):
    @abstractmethod
    async def analyze_image(self,image: bytes,mime_type: str) -> AnimalFeatures: ...


class ExtractionProvider(LLMProvider,VisionProvider):
    pass


def _check_response(response):
    if response.status_code == 404:
        raise ProviderError("MODEL_UNAVAILABLE",retryable=False)
    if response.status_code in (401,403):
        raise ProviderError("PROVIDER_AUTH_FAILED",retryable=False)
    if 400 <= response.status_code < 500 and response.status_code not in (408,429):
        raise ProviderError("PROVIDER_CONFIGURATION_ERROR",retryable=False)
    response.raise_for_status()


def clear_capability_cache():
    _CAPABILITIES.clear()


async def model_metadata(model,base_url=None,*,force=False,client=None):
    base_url=(base_url or settings.ollama_base_url).rstrip("/")
    key=(base_url,model,settings.ollama_num_ctx,settings.ollama_num_predict)
    cached=_CAPABILITIES.get(key)
    if cached and cached[0]>monotonic() and not force:
        return cached[1]
    if client is None:
        async with httpx.AsyncClient(timeout=15,follow_redirects=False,trust_env=False) as owned:
            return await model_metadata(model,base_url,force=force,client=owned)
    response=await client.post(base_url+"/api/show",json={"model":model})
    _check_response(response)
    data=response.json()
    if not isinstance(data,dict):
        raise ProviderError("MODEL_METADATA_INVALID",retryable=False)
    capabilities=data.get("capabilities",[])
    if not isinstance(capabilities,list):
        raise ProviderError("MODEL_METADATA_INVALID",retryable=False)
    metadata={"capabilities":[item for item in capabilities if isinstance(item,str)],"details":data.get("details",{})}
    if settings.app_env=="production" and model=="gemma3:4b":
        from app.analysis.gemma_setup import GEMMA_DIGEST
        tags=await client.get(base_url+"/api/tags")
        _check_response(tags)
        if not any(item.get("name")==model and item.get("digest")==GEMMA_DIGEST for item in tags.json().get("models",[])):
            raise ProviderError("MODEL_REVISION_MISMATCH",retryable=False)
        metadata["revision"]=GEMMA_DIGEST
    _CAPABILITIES[key]=(monotonic()+settings.ollama_capabilities_cache_seconds,metadata)
    return metadata


class OllamaProvider(ExtractionProvider):
    def __init__(self,model: str,base_url: str|None=None):
        self.model=model
        self.base_url=(base_url or settings.ollama_base_url).rstrip("/")
        self.last_metrics={}

    async def _extract(self,prompt,message,source):
        self.last_metrics={}
        timeout=settings.ai_vision_request_timeout_seconds if source=="image" else settings.ai_text_request_timeout_seconds
        try:
            async with httpx.AsyncClient(timeout=timeout,follow_redirects=False,trust_env=False) as client:
                metadata=await model_metadata(self.model,self.base_url,client=client)
                if metadata.get("revision"):self.last_metrics["model_revision"]=metadata["revision"]
                capabilities=metadata["capabilities"]
                if source=="image" and "vision" not in capabilities:
                    raise ProviderError("MODEL_HAS_NO_VISION",retryable=False)
                body={"model":self.model,"messages":[{"role":"system","content":prompt},{"role":"user",**message}],
                      "format":ExtractionOutput.model_json_schema(),"stream":False,"keep_alive":settings.ollama_keep_alive,
                      "options":{"temperature":0,"num_predict":settings.ollama_num_predict,"num_ctx":settings.ollama_num_ctx,
                                 "num_thread":settings.ollama_num_threads}}
                if "thinking" in capabilities:
                    body["think"]=False
                started=monotonic()
                response=await client.post(self.base_url+"/api/chat",json=body)
                self.last_metrics["ollama_request_ms"]=round((monotonic()-started)*1000,3)
                _check_response(response)
                data=response.json()
                if not isinstance(data,dict):
                    raise ProviderError("INVALID_FEATURE_RESPONSE",retryable=False)
                for key in ("total_duration","load_duration","prompt_eval_duration","eval_duration","prompt_eval_count","eval_count"):
                    if isinstance(data.get(key),(int,float)):
                        self.last_metrics[key]=data[key]
                self.last_metrics["cold_start"]=float(data.get("load_duration",0)>500_000_000)
                self.last_metrics["model_load_ms"]=float(data.get("load_duration",0))/1_000_000
                if data.get("done") is not True or data.get("done_reason")=="length":
                    raise ProviderError("INCOMPLETE_MODEL_RESPONSE",retryable=False)
                started=monotonic()
                result=parse_extraction_output(data["message"]["content"],source)
                self.last_metrics["parse_validate_ms"]=round((monotonic()-started)*1000,3)
                return result
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError("PROVIDER_TIMEOUT") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("PROVIDER_UNAVAILABLE") from exc
        except (ValueError,KeyError,TypeError,AttributeError) as exc:
            raise ProviderError("INVALID_FEATURE_RESPONSE",retryable=False) from exc

    async def extract_observation(self,text):
        return await self._extract(TEXT_PROMPT,{"content":"Animal evidence:\n"+text},"text")

    async def analyze_image(self,image,mime_type):
        return await self._extract(VISION_PROMPT,{"content":"Extract the visible animal's physical characteristics as JSON.",
            "images":[base64.b64encode(image).decode("ascii")]},"image")


async def prewarm_models(force=False):
    if not settings.ai_enabled or not settings.ollama_prewarm:
        return []
    from redis import Redis
    outcomes=[]
    for model in sorted({settings.ai_text_model,settings.ai_vision_model}):
        started=monotonic()
        try:
            with Redis.from_url(settings.redis_url,socket_connect_timeout=2,socket_timeout=2) as redis:
                key="mascomatch:prewarm:"+hashlib.sha256((settings.ollama_base_url+model).encode()).hexdigest()
                with redis.lock(key,timeout=settings.ai_vision_request_timeout_seconds+30,blocking=False) as lock:
                    metadata=await model_metadata(model,force=force)
                    async with httpx.AsyncClient(timeout=settings.ai_vision_request_timeout_seconds,trust_env=False,follow_redirects=False) as client:
                        response=await client.post(settings.ollama_base_url+"/api/chat",json={
                            "model":model,"messages":[],"keep_alive":settings.ollama_keep_alive,"stream":False,
                            "options":{"num_ctx":settings.ollama_num_ctx,"num_thread":settings.ollama_num_threads}})
                        _check_response(response)
                outcome={"model":model,"status":"ready","duration_ms":round((monotonic()-started)*1000)}
                redis.set("mascomatch:prewarm:last",json.dumps(outcome),ex=86400)
                outcomes.append(outcome)
        except Exception as exc:
            from redis.exceptions import LockError
            outcome={"model":model,"status":"already_warming" if isinstance(exc,LockError) else "unavailable",
                     "error_code":exc.code if isinstance(exc,ProviderError) else "PREWARM_UNAVAILABLE",
                     "duration_ms":round((monotonic()-started)*1000)}
            if outcome["status"]!="already_warming":
                try:
                    with Redis.from_url(settings.redis_url,socket_connect_timeout=2,socket_timeout=2) as redis:
                        redis.set("mascomatch:prewarm:last",json.dumps(outcome),ex=86400)
                except Exception:
                    pass
            outcomes.append(outcome)
    return outcomes


def get_provider(provider,model):
    if provider=="ollama":
        return OllamaProvider(model)
    raise ProviderError("PROVIDER_NOT_CONFIGURED",retryable=False)
