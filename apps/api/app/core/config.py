from typing import Literal
from ipaddress import ip_address, ip_network
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    app_env: Literal["development", "production", "test"] = "development"
    runtime_role: Literal["api", "worker", "ops", "migrate"] = "api"
    analytics_enabled: bool = True
    analytics_visitor_days: int = Field(default=180, ge=1, le=365)
    analytics_session_minutes: int = Field(default=30, ge=5, le=120)
    analytics_raw_days: int = Field(default=90, ge=1, le=180)
    analytics_daily_days: int = Field(default=730, ge=180, le=1825)
    rate_limit_analytics: int = Field(default=120, ge=1, le=600)
    rate_limit_analytics_daily: int = Field(default=200000,ge=100,le=10000000)
    database_url: str = Field(default="postgresql+psycopg://mascomatch:mascomatch@localhost:5432/mascomatch", repr=False)
    jwt_secret: str = Field(default="local-development-only-change-this-secret", repr=False)
    database_url_file: str | None = None
    jwt_secret_file: str | None = None
    s3_secret_key_file: str | None = None
    smtp_password_file: str | None = None
    redis_url_file: str | None = None
    backup_key_file: str | None = None
    backup_key: SecretStr = SecretStr("")
    access_token_minutes: int = Field(default=60, ge=5, le=1440)
    web_origin: str = "http://localhost:3000"
    s3_endpoint: str = "http://localhost:9000"
    s3_public_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "pet-photos"
    s3_access_key: str = "mascomatch"
    s3_secret_key: str = Field(default="change-this-minio-password", repr=False)
    max_photo_size_bytes: int = 10 * 1024 * 1024
    redis_url: str = Field(default="redis://localhost:6379/0", repr=False)
    ai_enabled: bool = False
    ai_provider: Literal["ollama"] = "ollama"
    ai_text_model: str = "gemma3:4b"
    ai_vision_model: str = "gemma3:4b"
    ollama_base_url: str = "http://localhost:11434"
    ai_request_timeout_seconds: int = Field(default=180, ge=10, le=600)
    ai_text_request_timeout_seconds: int = Field(default=120, ge=10, le=600)
    ai_vision_request_timeout_seconds: int = Field(default=240, ge=10, le=600)
    ollama_num_ctx: int = Field(default=4096, ge=2048, le=32768)
    ollama_num_predict: int = Field(default=768, ge=256, le=4096)
    ollama_num_threads: int = Field(default=3, ge=1, le=8)
    ollama_keep_alive: str = Field(default="15m", pattern=r"^[1-9][0-9]{0,3}[sm]$")
    ollama_prewarm: bool = True
    ollama_capabilities_cache_seconds: int = Field(default=3600, ge=60, le=86400)
    vlm_image_max_side: int = Field(default=1024, ge=224, le=2048)
    vlm_image_jpeg_quality: int = Field(default=88, ge=70, le=95)
    analysis_worker_kind: Literal["all", "semantic", "visual"] = "all"
    ai_max_attempts: int = Field(default=3, ge=1, le=5)
    ai_dispatch_interval_seconds: int = Field(default=5, ge=1, le=60)
    linked_match_threshold: float = Field(default=0.75, ge=0.5, le=1)
    linked_feature_confidence: float = Field(default=0.7, ge=0.5, le=1)
    mail_delivery_mode: Literal["disabled", "preview", "smtp"] = "disabled"
    smtp_host: str = "localhost"
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = "MascoMatch <avisos@mascomatch.local>"
    smtp_tls_mode: Literal["none", "starttls", "ssl"] = "starttls"
    public_site_url: str = "http://localhost:3000"
    photo_reminder_delay_minutes: int = Field(default=30, ge=1, le=1440)
    embeddings_enabled: bool = False
    embedding_model: Literal["ViT-B-32"] = "ViT-B-32"
    embedding_pretrained: Literal["openai"] = "openai"
    embedding_cache_dir: str = "/models/clip"
    embedding_cpu_threads: int = Field(default=2, ge=1, le=8)
    pet_reid_enabled: bool = True
    openclip_enabled: bool = True
    pet_reid_cache_dir: str = "/models/pet-reid"
    detector_cache_dir: str = "/models/detector"
    pet_crop_enabled: bool = True
    pet_crop_confidence: float = Field(default=.75, ge=.5, le=.99)
    pet_crop_margin: float = Field(default=.18, ge=0, le=.5)
    pet_crop_timeout_seconds: int = Field(default=15, ge=1, le=60)
    embedding_request_timeout_seconds: int = Field(default=90, ge=15, le=600)
    openclip_visual_floor: float = Field(default=.55, ge=0, le=.99)
    openclip_visual_ceiling: float = Field(default=.95, ge=0, le=1)
    pet_reid_visual_floor: float = Field(default=.50, ge=0, le=.99)
    pet_reid_visual_ceiling: float = Field(default=.90, ge=0, le=1)
    visual_best_weight: float = Field(default=.7, ge=.5, le=1)
    matching_analysis_wait_seconds: int = Field(default=30, ge=0, le=300)
    matching_notify_min_coverage: float = Field(default=.35, ge=.25, le=1)
    matching_notify_min_feature: float = Field(default=.65, ge=.5, le=1)
    matching_notify_min_geo: float = Field(default=.35, ge=.1, le=1)
    matching_candidate_threshold: float = Field(default=0.55, ge=0, le=1)
    matching_notify_threshold: float = Field(default=0.82, ge=0.5, le=1)
    matching_max_radius_meters: int = Field(default=50000, ge=1000, le=300000)
    matching_temporal_days: int = Field(default=30, ge=1, le=365)
    matching_visual_floor: float = Field(default=0.55, ge=0, le=0.9)
    matching_visual_ceiling: float = Field(default=0.95, ge=0.6, le=1)
    mail_group_seconds: int = Field(default=15, ge=0, le=300)
    rate_limit_enabled: bool = True
    rate_limit_auth: int = Field(default=30,ge=1,le=10000)
    rate_limit_register: int = Field(default=5,ge=1,le=100)
    rate_limit_contact: int = Field(default=5, ge=1, le=100)
    rate_limit_contact_daily: int = Field(default=50, ge=1, le=10000)
    rate_limit_publish: int = Field(default=60,ge=1,le=10000)
    rate_limit_read: int = Field(default=300,ge=1,le=10000)
    rate_limit_backend: Literal["memory", "redis"] = "memory"
    trusted_proxy_ips: str = ""
    allowed_hosts: str = "localhost,127.0.0.1,testserver,api"
    metrics_token: SecretStr = SecretStr("")
    metrics_token_file: str | None = None
    upload_slots: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="before")
    @classmethod
    def secret_files(cls, values):
        values = dict(values)
        for name in ("database_url", "jwt_secret", "s3_secret_key", "smtp_password", "redis_url", "backup_key", "metrics_token"):
            filename = values.get(f"{name}_file")
            if not filename:
                continue
            if values.get(name):
                raise ValueError(f"Configure {name.upper()} or its file, not both")
            try:
                with Path(filename).open("rb") as stream:
                    payload = stream.read(16385)
                if len(payload) > 16384:
                    raise ValueError("Secret file exceeds limit")
                values[name] = payload.decode("utf-8").strip()
            except (OSError, UnicodeError) as exc:
                raise ValueError(f"Cannot read {name.upper()} secret file") from exc
        return values

    @model_validator(mode="after")
    def production_configuration(self):
        for value in self.trusted_proxy_ips.split(","):
            if value.strip():
                network = ip_network(value.strip(), strict=False)
                if network.prefixlen == 0:
                    raise ValueError("Do not trust every address as a proxy")
        if self.app_env != "production":
            return self
        required = [self.jwt_secret, self.s3_secret_key] if self.runtime_role=="api" else [self.s3_secret_key] if self.runtime_role!="migrate" else []
        for value in required:
            if len(value) < 32 or any(marker in value.lower() for marker in ("change-this", "replace-with", "development-only")):
                raise ValueError("Production requires generated JWT and S3 secrets")
        if not self.database_url.startswith("postgresql"):
            raise ValueError("Production requires PostgreSQL")
        if self.runtime_role=="api" and (not self.rate_limit_enabled or self.rate_limit_backend != "redis"):
            raise ValueError("Production requires shared request limits")
        if "*" in self.allowed_hosts or not self.allowed_hosts.strip():
            raise ValueError("Production requires explicit allowed hosts")
        if self.runtime_role=="api" and len(self.metrics_token.get_secret_value()) < 32:
            raise ValueError("Production requires a private monitoring token")
        for value in self.cors_origins + [self.public_site_url]:
            parsed = urlsplit(value)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("Production site URLs must use HTTPS")
        if self.mail_delivery_mode == "preview":
            raise ValueError("Production cannot use a preview mail server")
        return self

    @model_validator(mode="after")
    def matching_configuration(self):
        for provider in ("openclip", "pet_reid"):
            if getattr(self, provider + "_visual_floor") >= getattr(self, provider + "_visual_ceiling"):
                raise ValueError("Provider visual floor must be below ceiling")
        if self.matching_visual_floor >= self.matching_visual_ceiling:
            raise ValueError("Visual floor must be below ceiling")
        if self.matching_candidate_threshold > self.matching_notify_threshold:
            raise ValueError("Candidate threshold must not exceed notification threshold")
        return self

    @model_validator(mode="after")
    def mail_configuration(self):
        if any(character in self.smtp_from for character in ("\r", "\n")):
            raise ValueError("SMTP_FROM cannot contain line breaks")
        if self.mail_delivery_mode == "smtp" and self.smtp_tls_mode == "none":
            raise ValueError("Real SMTP delivery requires SSL or STARTTLS")
        if self.mail_delivery_mode == "preview":
            host = self.smtp_host.lower()
            private = host in {"mailpit", "localhost", "host.docker.internal"}
            try:
                address = ip_address(host)
                private = address.is_private or address.is_loopback
            except ValueError:
                pass
            if not private:
                raise ValueError("Mail previews must use a local/private SMTP server")
        parsed = urlsplit(self.public_site_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("PUBLIC_SITE_URL must be an HTTP(S) site URL without credentials")
        return self

    @field_validator("ai_text_model", "ai_vision_model")
    @classmethod
    def local_model_only(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 120 or "cloud" in value.split(":")[-1].lower():
            raise ValueError("Configure a local Ollama model, not a cloud model")
        return value

    @field_validator("ollama_base_url")
    @classmethod
    def local_ollama_only(cls, value: str) -> str:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        allowed = host in {"localhost", "ollama", "host.docker.internal"}
        try:
            address = ip_address(host)
            allowed = address.is_private or address.is_loopback
        except ValueError:
            pass
        if parsed.scheme not in {"http", "https"} or not allowed or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise ValueError("OLLAMA_BASE_URL must point to a local/private Ollama server without credentials")
        return value.rstrip("/")

    @property
    def ai_job_timeout_seconds(self) -> int:
        return max(self.ai_text_request_timeout_seconds, self.ai_vision_request_timeout_seconds, self.embedding_request_timeout_seconds) + 60

    def timeout_for_source(self, source: str) -> int:
        return {"text": self.ai_text_request_timeout_seconds, "image": self.ai_vision_request_timeout_seconds,
                "embedding": self.embedding_request_timeout_seconds}[source] + 45

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.web_origin.split(",") if origin.strip()]


settings = Settings()

