"use client";
import { AdminHeading, AdminLabel } from "./admin-info";
import { adminDate } from "./date-range";

export type BackupStatus = {
  known: boolean; enabled: boolean; inventory_truncated: boolean;
  local_last_success: number; offsite_last_success: number; latest_capture: number;
  offsite_last_attempt: number; pending_count: number; consecutive_failures: number;
  last_size_bytes: number; last_duration_seconds: number; last_deep_verify: number;
  object_count: number; stored_bytes: number; inventory_at: number; heartbeat: number;
  local_interval: number; error_code?: string | null; local_error_code?: string | null;
};
const date = (value?: number) => value ? adminDate(new Date(value * 1000).toISOString()) : "Sin registro";
const bytes = (value: number) => `${new Intl.NumberFormat("es-UY", { maximumFractionDigits: 1 }).format(value / 1024 ** 2)} MiB`;
const errors: Record<string, string> = {
  LOCAL_BACKUP_FAILED: "No se pudo crear el respaldo local.", LOCAL_VERIFY_FAILED: "Falló la verificación del respaldo local.",
  OFFSITE_UPLOAD_FAILED: "No se pudo subir una copia a B2.", OFFSITE_VERIFY_FAILED: "No se pudo verificar una copia en B2.",
  OFFSITE_AUTH_FAILED: "B2 rechazó las credenciales o sus permisos.", OFFSITE_CONFIGURATION_ERROR: "Se debe revisar la configuración de B2.",
  OFFSITE_RETENTION_ERROR: "La protección de retención en B2 no coincide con la configuración esperada.",
};
export function BackupStatusWidget({ status }: { status?: BackupStatus }) {
  const stale = !!status && Date.now() / 1000 - status.heartbeat > 2700;
  const old = !!status && Date.now() / 1000 - status.latest_capture > Math.max(28800, status.local_interval + 7200);
  const label = !status?.known ? "Sin información" : stale ? "Estado desactualizado" : !status.enabled ? "B2 desactivado" : status.error_code || old ? "Requiere atención" : "B2 conectado";
  const detail = (name: string, value: string | number, help: string) => <div key={name}><dt><AdminLabel label={name} help={help} /></dt><dd>{value}</dd></div>;
  return <section className="admin-widget admin-backup-widget" aria-label="Respaldos y recuperación">
    <div className="admin-widget-heading"><div><AdminHeading level={3} label="Respaldos y recuperación" help="Copias cifradas de la base de datos y las fotos. El estado es actual y no cambia con el filtro de fechas." /><p>Estado actual de toda la plataforma · {label}</p></div></div>
    <dl className="admin-recommendation-details">
      {detail("Último respaldo local", date(status?.local_last_success), "Última copia local que pasó la autenticación y la verificación de sus archivos.")}
      {detail("Última copia en B2", date(status?.offsite_last_success), "Momento en que se confirmó una subida. Puede corresponder a un respaldo antiguo pendiente.")}
      {detail("Punto de recuperación en B2", date(status?.latest_capture), "Fecha de creación del respaldo más reciente confirmado en B2. Esta fecha determina cuántos datos podrían perderse ante un desastre.")}
      {detail("Pendientes de subir", status?.known && status.enabled ? status.pending_count : "Sin registro", "Copias locales todavía sin confirmación remota. Se reintentan sin volver a generar el respaldo.")}
      {detail("Verificación profunda", date(status?.last_deep_verify), "Última descarga autenticada con AES y comprobación de los hashes del respaldo.")}
      {detail("Inventario B2", status?.inventory_at ? `${status.object_count} versiones · ${bytes(status.stored_bytes)}${status.inventory_truncated ? " (parcial)" : ""}` : "Sin registro", "Cantidad y tamaño aproximados, incluidas las versiones ocultas. No es una factura. El listado tiene un límite de seguridad.")}
      {detail("Inventario actualizado", date(status?.inventory_at), "Fecha de la última consulta de tamaños y versiones en B2.")}
      {detail("Proceso de respaldo", date(status?.heartbeat), "Última señal del proceso. Una señal reciente por sí sola no garantiza una copia correcta.")}
    </dl>
    {status?.local_error_code && <p role="status">{errors[status.local_error_code] || "Revisar el respaldo local."}</p>}
    {status?.enabled && status.error_code && <p role="status">{errors[status.error_code] || "Revisar la copia remota."} Las copias locales pendientes se conservan para reintentar.</p>}
    {!status?.known && <p className="field-help">Todavía no se recibió información del servicio de respaldos. En desarrollo puede no estar ejecutándose.</p>}
  </section>;
}
