import { NextRequest, NextResponse } from "next/server";
import { authorization, boundedBody, sameOrigin, serverApi } from "@/lib/server-api";
import { admitUpload, releaseUpload } from "@/lib/upload-admission";

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
async function handle(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const method = request.method;
  const dashboard = method === "GET" && path.length === 1 && path[0] === "dashboard";
  const report = path.length === 2 && ["lost-cases", "observations", "pets"].includes(path[0]) && uuid.test(path[1]) && ["GET", "PATCH", "DELETE"].includes(method);
  const observationEdit = method === "GET" && path.length === 3 && path[0] === "observations" && uuid.test(path[1]) && path[2] === "edit";
  const batch = method === "POST" && path.join("/") === "photos/upload-batch";
  const upload = batch || (method === "POST" && path.join("/") === "photos/upload");
  const edit = method === "PATCH" && path.length === 2 && path[0] === "cases" && uuid.test(path[1]);
  const album = method === "GET" && path.join("/") === "photos/album";
  const cover = method === "PUT" && path.join("/") === "photos/cover";
  const removePhoto = method === "DELETE" && path.length === 2 && path[0] === "photos" && uuid.test(path[1]);
  const image = method === "GET" && path.length === 3 && path[0] === "photos" && uuid.test(path[1]) && path[2] === "image";
  if ((!dashboard && !report && !observationEdit && !upload && !edit && !album && !cover && !removePhoto && !image) || (method !== "GET" && !sameOrigin(request))) {
    return NextResponse.json({ detail: "Solicitud no permitida." }, { status: 403 });
  }
  const query = new URLSearchParams();
  if (album) {
    const kind = request.nextUrl.searchParams.get("owner_type") || "";
    const id = request.nextUrl.searchParams.get("owner_id") || "";
    if (!["pet", "lost_case", "observation"].includes(kind) || !uuid.test(id)) return NextResponse.json({ detail: "Reporte no válido." }, { status: 400 });
    query.set("owner_type", kind); query.set("owner_id", id);
  }
  let lease: string | null = null;
  try {
    if (upload) lease = await admitUpload(request);
    const body = method === "PATCH" || cover || upload ? Buffer.from(await boundedBody(request, batch ? 52 * 1024 * 1024 : upload ? 11 * 1024 * 1024 : 16384)) : undefined;
    const target = dashboard ? "me/dashboard" : edit ? `me/cases/${path[1]}` : path.join("/");
    const response = await fetch(`${serverApi}/${target}${query.size ? `?${query}` : ""}`, {
      method, headers: { ...authorization(request), ...(body ? { "Content-Type": request.headers.get("content-type") || "application/json" } : {}) },
      body, cache: "no-store", signal: AbortSignal.timeout(batch ? 90000 : 30000),
    });
    if (response.status === 204) return new Response(null, { status: 204 });
    if (image && response.ok) return new Response(response.body, { headers: { "Content-Type": response.headers.get("content-type") || "image/jpeg", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" } });
    const data = await response.json();
    if (upload && response.ok) delete data.signed_url;
    return NextResponse.json(data, { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    const message = error instanceof Error ? error.message : "";
    return NextResponse.json({ detail: message === "BODY_TOO_LARGE" ? "Las fotos exceden el tamaño permitido." : "No pudimos guardar los cambios. Intentá de nuevo." }, { status: message === "UPLOAD_BUSY" ? 429 : message === "BODY_TOO_LARGE" ? 413 : 503 });
  } finally { await releaseUpload(request, lease); }
}
export const GET = handle;
export const PATCH = handle;
export const DELETE = handle;
export const POST = handle;
export const PUT = handle;
