import {NextRequest,NextResponse} from "next/server";
import {authorization,boundedBody,sameOrigin,serverApi} from "@/lib/server-api";

export async function POST(request:NextRequest){
  if(!sameOrigin(request))return new Response(null,{status:403});
  try{
    const body=Buffer.from(await boundedBody(request,4096));
    const upstream=await fetch(`${serverApi}/analytics/events`,{method:"POST",headers:{...authorization(request),
      Origin:request.headers.get("origin")||request.nextUrl.origin,"User-Agent":request.headers.get("user-agent")||"",
      "Content-Type":"application/json",...(request.headers.get("x-mascomatch-synthetic")==="1"?{"X-MascoMatch-Synthetic":"1"}:{})},body,cache:"no-store",signal:AbortSignal.timeout(3000)});
    const result=new NextResponse(null,{status:upstream.status,headers:{"Cache-Control":"no-store"}});
    for(const cookie of upstream.headers.getSetCookie())if(/^(mm_visitor|mm_visit)=/.test(cookie))result.headers.append("Set-Cookie",cookie);
    return result;
  }catch{return new Response(null,{status:503,headers:{"Cache-Control":"no-store"}});}
}
