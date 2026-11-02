import { NextRequest, NextResponse } from "next/server";
import { authorization, boundedBody, sameOrigin, serverApi, SESSION_COOKIE } from "@/lib/server-api";

async function forward(request: NextRequest) {
  if (!sameOrigin(request)) return NextResponse.json({ detail: "Solicitud no permitida." }, { status: 403 });
  try {
    const action = request.nextUrl.searchParams.get("action");
    const method = request.method;
    const path = method === "PATCH" && !action ? "contact" : method === "DELETE" && !action ? "me"
      : method === "POST" && action === "password" ? "change-password"
      : method === "POST" && (action === "resend" || action === "cancel") ? `contact/email/${action}` : null;
    if (!path) return NextResponse.json({ detail: "Solicitud no permitida." }, { status: 403 });
    const body = method === "POST" && action !== "password" ? undefined : Buffer.from(await boundedBody(request, 8192));
    const response = await fetch(`${serverApi}/auth/${path}`, {
      method, headers: { ...authorization(request), "Content-Type": "application/json" }, body,
      cache: "no-store", signal: AbortSignal.timeout(30000),
    });
    const result = response.status === 204 ? new NextResponse(null, { status: 204 })
      : NextResponse.json(await response.json(), { status: response.status });
    result.headers.set("Cache-Control", "no-store");
    const retry = response.headers.get("Retry-After");
    if (retry) result.headers.set("Retry-After", retry);
    if (response.status === 401 || (method === "DELETE" && response.ok)) result.cookies.delete(SESSION_COOKIE);
    return result;
  } catch (cause) {
    return NextResponse.json({ detail: "No pudimos guardar el cambio. Intentá de nuevo." },
      { status: cause instanceof Error && cause.message === "BODY_TOO_LARGE" ? 413 : 503 });
  }
}

export const PATCH = forward;
export const DELETE = forward;
export const POST = forward;
