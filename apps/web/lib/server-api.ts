import type { NextRequest } from "next/server";
import { isIP } from "node:net";

export const SESSION_COOKIE = process.env.NODE_ENV === "production" ? "__Host-mascomatch_session" : "mascomatch_session";
export const serverApi = (process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");

export function sameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  if (request.headers.get("sec-fetch-site") === "cross-site") return false;
  if (!origin) return process.env.NODE_ENV !== "production";
  try {
    const expected = process.env.PUBLIC_SITE_URL;
    if (expected) return new URL(origin).origin === new URL(expected).origin;
    return new URL(origin).host === request.headers.get("host");
  } catch { return false; }
}

export function proxyHeaders(request: NextRequest): Record<string, string> {
  const address = request.headers?.get("x-mascomatch-client-ip");
  const analytics: string[]=[];
  for(const [name,pattern] of [["mm_visitor",/^[A-Za-z0-9_-]{43}$/],["mm_visit",/^[0-9a-f-]{36}\.[0-9a-f]{64}$/]] as const){const value=request.cookies?.get(name)?.value;if(value&&pattern.test(value))analytics.push(`${name}=${value}`);}
  return {...(process.env.TRUST_PROXY_HEADERS === "true" && address && isIP(address)
    ? { "X-MascoMatch-Client-IP": address } : {}),...(analytics.length?{Cookie:analytics.join("; ")}:{})};
}

export function authorization(request: NextRequest): Record<string, string> {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  return { ...proxyHeaders(request), ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

export async function boundedBody(request: NextRequest, limit: number): Promise<Uint8Array> {
  const reader = request.body?.getReader();
  if (!reader) return new Uint8Array();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) throw new Error("BODY_TOO_LARGE");
      chunks.push(value);
    }
  } catch (error) { await reader.cancel(); throw error; }
  const body = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
  return body;
}
