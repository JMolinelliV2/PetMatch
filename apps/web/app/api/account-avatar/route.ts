import { NextRequest, NextResponse } from "next/server";
import { authorization, boundedBody, sameOrigin, serverApi, SESSION_COOKIE } from "@/lib/server-api";
import { admitUpload, releaseUpload } from "@/lib/upload-admission";

const privateHeaders = { "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Cross-Origin-Resource-Policy": "same-origin" };

async function forward(request: NextRequest) {
  const upload = request.method === "POST";
  if (request.method !== "GET" && !sameOrigin(request)) return NextResponse.json({ detail: "Solicitud no permitida." }, { status: 403 });
  if (!request.cookies.has(SESSION_COOKIE)) return NextResponse.json({ detail: "Ingresá con tu cuenta para gestionar tu foto." }, { status: 401, headers: privateHeaders });
  let lease: string | null = null;
  try {
    if (upload && !request.headers.get("content-type")?.startsWith("multipart/form-data;")) return NextResponse.json({ detail: "Elegí una foto JPG, PNG o WebP." }, { status: 415, headers: privateHeaders });
    if (upload) lease = await admitUpload(request);
    const body = upload ? Buffer.from(await boundedBody(request, 11 * 1024 * 1024)) : undefined;
    const response = await fetch(`${serverApi}/auth/avatar`, {
      method: request.method,
      headers: { ...authorization(request), ...(upload ? { "Content-Type": request.headers.get("content-type")! } : {}) },
      body, cache: "no-store", signal: AbortSignal.timeout(30000),
    });
    if (request.method === "GET" && response.ok) return new Response(response.body, { headers: { ...privateHeaders, "Content-Type": "image/jpeg" } });
    const retry = response.headers.get("Retry-After");
    return NextResponse.json(await response.json(), { status: response.status, headers: { ...privateHeaders, ...(retry ? { "Retry-After": retry } : {}) } });
  } catch (cause) {
    const message = cause instanceof Error ? cause.message : "";
    return NextResponse.json({ detail: message === "BODY_TOO_LARGE" ? "La foto supera el tamaño permitido de 10 MB." : "No pudimos actualizar tu foto. Intentá de nuevo." },
      { status: message === "UPLOAD_BUSY" ? 429 : message === "BODY_TOO_LARGE" ? 413 : 503, headers: privateHeaders });
  } finally { await releaseUpload(request, lease); }
}

export const GET = forward;
export const POST = forward;
export const DELETE = forward;
