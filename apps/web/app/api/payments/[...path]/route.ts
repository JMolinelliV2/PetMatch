import { randomBytes } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { boundedBody, proxyHeaders, sameOrigin, serverApi } from "@/lib/server-api";

const cookieName = process.env.NODE_ENV === "production" ? "__Host-mascomatch_donation" : "mascomatch_donation";
const browserKey = /^[A-Za-z0-9_-]{43}$/;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function handle(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const method = request.method;
  const configuration = method === "GET" && path.join("/") === "config";
  const checkout = method === "POST" && path.join("/") === "checkout";
  const receipt = path[0] === "donations" && uuid.test(path[1] || "") &&
    ((path.length === 2 && method === "GET") || (path.length === 3 && path[2] === "refresh" && method === "POST"));
  const webhook = method === "POST" && path.join("/") === "mercadopago/webhook";
  if ((!configuration && !checkout && !receipt && !webhook) || (method !== "GET" && !webhook && !sameOrigin(request))) {
    return NextResponse.json({ detail: "Solicitud no permitida." }, { status: 403 });
  }
  const existing = request.cookies.get(cookieName)?.value;
  const session = existing && browserKey.test(existing) ? existing : null;
  if ((checkout || receipt) && !session) return NextResponse.json({ detail: "Recargá la página de aportes y permití las cookies de MascoMatch para continuar." }, { status: 401 });
  try {
    const headers = { ...proxyHeaders(request), "Content-Type": "application/json" } as Record<string, string>;
    const query = new URLSearchParams();
    if (webhook) {
      const identities = request.nextUrl.searchParams.getAll("data.id");
      const topics = request.nextUrl.searchParams.getAll("type");
      if (identities.length !== 1 || topics.length > 1) return NextResponse.json({ detail: "Notificación no válida." }, { status: 401 });
      query.set("data.id", identities[0]);
      if (topics.length) query.set("type", topics[0]);
      for (const name of ["x-signature", "x-request-id"]) {
        const value = request.headers.get(name);
        if (value) headers[name] = value;
      }
    } else if (session) headers["X-Donation-Session"] = session;
    const body = method === "POST" ? Buffer.from(await boundedBody(request, webhook ? 32768 : 4096)) : undefined;
    const upstream = await fetch(`${serverApi}/payments/${path.join("/")}${query.size ? `?${query}` : ""}`, {
      method, headers, body, cache: "no-store", signal: AbortSignal.timeout(webhook ? 20000 : 30000),
    });
    const data = await upstream.json();
    const response = NextResponse.json(data, { status: upstream.status, headers: { "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" } });
    const retry = upstream.headers.get("Retry-After");
    if (retry) response.headers.set("Retry-After", retry);
    if (configuration && upstream.ok && data.enabled) response.cookies.set(cookieName, session || randomBytes(32).toString("base64url"), {
      httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge: 30 * 86400,
    });
    return response;
  } catch (cause) {
    return NextResponse.json({ detail: "No pudimos completar la consulta del aporte. Intentá de nuevo." },
      { status: cause instanceof Error && cause.message === "BODY_TOO_LARGE" ? 413 : 503, headers: { "Cache-Control": "no-store" } });
  }
}

export const GET = handle;
export const POST = handle;
