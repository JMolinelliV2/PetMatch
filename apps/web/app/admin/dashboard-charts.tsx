"use client";
import { useId, useState } from "react";
import { AdminInfo, AdminLabel } from "./admin-info";
export type ChartSlice = { label: string; value: number; tone: string; help?: string };
export type TimelinePoint = { date: string; users: number; publications: number };
export const chartNumber = (value: number) => new Intl.NumberFormat("es-UY").format(value);
const fullDate = (value: string) => new Intl.DateTimeFormat("es-UY", { dateStyle: "medium", timeZone: "America/Montevideo" }).format(new Date(`${value}T12:00:00-03:00`));
const shortDate = (value: string) => new Intl.DateTimeFormat("es-UY", { day: "numeric", month: "short", timeZone: "America/Montevideo" }).format(new Date(`${value}T12:00:00-03:00`));

export function DonutChart({ slices, label, empty = "Sin registros" }: { slices: ChartSlice[]; label: string; empty?: string }) {
  const [active, setActive] = useState<number | null>(null);
  const total = slices.reduce((sum, item) => sum + item.value, 0);
  let offset = 0;
  const highlighted = active === null ? null : slices[active];
  return <div className="admin-donut-layout"><div className="admin-donut">
    <svg viewBox="0 0 200 200" role="img" aria-label={total ? `${label}: ${slices.map(item => `${item.label} ${item.value}`).join(", ")}` : `${label}: ${empty}`}>
      <circle cx="100" cy="100" r="78" pathLength="100" className="admin-donut-track" />
      {total > 0 && slices.map((item, index) => { const length = 100 * item.value / total; const start = offset; offset += length; return item.value > 0 ? <circle key={item.label} cx="100" cy="100" r="78" pathLength="100" className={`admin-donut-segment admin-tone-${item.tone}`} strokeDasharray={`${length} ${100 - length}`} strokeDashoffset={-start} opacity={active === null || active === index ? 1 : .35}><title>{item.label}: {chartNumber(item.value)} ({Math.round(length)}%)</title></circle> : null; })}
    </svg><div className="admin-donut-center"><strong>{chartNumber(highlighted?.value ?? total)}</strong><span>{highlighted?.label || (total ? "Total" : empty)}</span></div>
  </div><ul className="admin-chart-legend">{slices.map((item, index) => <li key={item.label}><div className="admin-legend-row"><button className="admin-legend-toggle" type="button" onMouseEnter={() => setActive(index)} onMouseLeave={() => setActive(null)} onFocus={() => setActive(index)} onBlur={() => setActive(null)} onClick={() => setActive(value => value === index ? null : index)} aria-pressed={active === index}><span className={`admin-legend-dot admin-tone-${item.tone}`} /><span>{item.label}</span><strong>{chartNumber(item.value)}</strong></button>{item.help && <AdminInfo label={item.label} help={item.help} />}</div></li>)}</ul></div>;
}

export function TimelineChart({ points, unit }: { points: TimelinePoint[]; unit: string }) {
  const [active, setActive] = useState<number | null>(null);
  const [visible, setVisible] = useState({ users: true, publications: true });
  const id = useId().replace(/:/g, "");
  const width = 760, height = 246, left = 38, right = 20, top = 20, bottom = 38;
  const maxValue = Math.max(1, ...points.flatMap(point => [visible.users ? point.users : 0, visible.publications ? point.publications : 0]));
  const ceiling = Math.max(4, Math.ceil(maxValue / 4) * 4);
  const x = (index: number) => points.length > 1 ? left + index * (width - left - right) / (points.length - 1) : (width + left - right) / 2;
  const y = (value: number) => height - bottom - value * (height - top - bottom) / ceiling;
  const path = (key: "users" | "publications") => points.map((point, index) => `${index ? "L" : "M"}${x(index)},${y(point[key])}`).join(" ");
  const point = active === null ? null : points[active];
  const units: Record<string, string> = { day: "día", week: "semana", month: "mes", year: "año" };
  return <><div className="admin-line-legend">{(["publications", "users"] as const).map(key => <span className="admin-series-label" key={key}><button className="admin-series-toggle" type="button" aria-pressed={visible[key]} onClick={() => setVisible(value => ({ ...value, [key]: !value[key] }))}><span className={`admin-legend-dot admin-tone-${key === "users" ? "coral" : "teal"}`} />{key === "users" ? "Cuentas nuevas" : "Publicaciones"}</button><AdminInfo label={key === "users" ? "Cuentas nuevas" : "Publicaciones"} help={key === "users" ? "Cuentas creadas en cada intervalo del gráfico. Incluye los registros conservados dentro del período seleccionado." : "Avisos de pérdida, avistamientos y reportes de mascotas encontradas creados en cada intervalo, incluidos los recuperados, cerrados u ocultos."} /></span>)}<small>Por {units[unit] || "período"}</small></div>
    {!points.length ? <div className="admin-chart-empty"><span>Sin movimientos en este período</span><small>Los registros y publicaciones aparecerán a medida que se creen.</small></div> : <div className="admin-line-chart" tabIndex={0} role="group" aria-label="Gráfico de cuentas nuevas y publicaciones. Usá las flechas para consultar cada fecha." onKeyDown={event => { if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); setActive(current => Math.max(0, Math.min(points.length - 1, (current ?? 0) + (event.key === "ArrowRight" ? 1 : -1)))); } if (event.key === "Escape") setActive(null); }} onBlur={() => setActive(null)} onMouseLeave={() => setActive(null)}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Cuentas nuevas y publicaciones en ${points.length} períodos. Horarios de Uruguay.`} onMouseMove={event => { const rect = event.currentTarget.getBoundingClientRect(); const at = (event.clientX - rect.left) / rect.width * width; setActive(Math.max(0, Math.min(points.length - 1, Math.round((at - left) / (width - left - right) * (points.length - 1))))); }}>
        <defs><linearGradient id={`${id}-fill`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--chart-teal)" stopOpacity=".24" /><stop offset="100%" stopColor="var(--chart-teal)" stopOpacity="0" /></linearGradient></defs>
        {[0, 1, 2, 3, 4].map(step => <g key={step}><line className="admin-chart-gridline" x1={left} x2={width - right} y1={y(step * ceiling / 4)} y2={y(step * ceiling / 4)} /><text className="admin-chart-axis" x={left - 10} y={y(step * ceiling / 4) + 4} textAnchor="end">{chartNumber(step * ceiling / 4)}</text></g>)}
        {visible.publications && <><path d={`${path("publications")} L${x(points.length - 1)},${height - bottom} L${x(0)},${height - bottom} Z`} fill={`url(#${id}-fill)`} /><path d={path("publications")} className="admin-chart-line admin-tone-teal" /></>}
        {visible.users && <path d={path("users")} className="admin-chart-line admin-tone-coral" strokeDasharray="5 5" />}
        {points.map((item, index) => (index === 0 || index === points.length - 1 || index % Math.max(1, Math.ceil(points.length / 5)) === 0) && <text className="admin-chart-axis" key={item.date} x={x(index)} y={height - 10} textAnchor={index === 0 ? "start" : index === points.length - 1 ? "end" : "middle"}>{unit === "year" ? item.date.slice(0, 4) : shortDate(item.date)}</text>)}
        {point && active !== null && <line className="admin-chart-guide" x1={x(active)} x2={x(active)} y1={top} y2={height - bottom} />}
        {points.length === 1 && (["publications", "users"] as const).filter(key => visible[key]).map(key => <circle key={key} cx={x(0)} cy={y(points[0][key])} r="4" className={`admin-chart-point admin-tone-${key === "users" ? "coral" : "teal"}`} />)}
        {point && active !== null && (["publications", "users"] as const).filter(key => visible[key]).map(key => <circle key={key} cx={x(active)} cy={y(point[key])} r="5" className={`admin-chart-point admin-tone-${key === "users" ? "coral" : "teal"}`} />)}
      </svg>{point && <div className="admin-chart-tooltip" style={{ left: `${Math.min(72, Math.max(0, (active || 0) / Math.max(1, points.length - 1) * 100))}%` }} role="status"><strong>{fullDate(point.date)}{unit !== "day" && ` · inicio de ${units[unit]}`}</strong><span>Publicaciones: {chartNumber(point.publications)}</span><span>Cuentas nuevas: {chartNumber(point.users)}</span></div>}
      <details className="admin-chart-data"><summary>Ver datos del gráfico</summary><div className="admin-table-scroll"><table className="admin-results-table"><thead><tr><th><AdminLabel label="Inicio del período" help="Primer día del intervalo del gráfico, en horario de Uruguay. Los valores corresponden a las fechas incluidas en el filtro seleccionado." /></th><th><AdminLabel label="Cuentas nuevas" /></th><th><AdminLabel label="Publicaciones" /></th></tr></thead><tbody>{points.map(item => <tr key={item.date}><td>{fullDate(item.date)}</td><td>{chartNumber(item.users)}</td><td>{chartNumber(item.publications)}</td></tr>)}</tbody></table></div></details>
    </div>}
  </>;
}

export function HorizontalBars({ items, empty }: { items: ChartSlice[]; empty: string }) {
  const max = Math.max(1, ...items.map(item => item.value));
  return items.length ? <ul className="admin-horizontal-bars">{items.map(item => <li key={item.label}><div><AdminLabel label={item.label} help={item.help} /><strong>{chartNumber(item.value)}</strong></div><span className="admin-horizontal-track"><span className={`admin-tone-${item.tone}`} style={{ width: `${100 * item.value / max}%` }} /></span></li>)}</ul> : <div className="admin-chart-empty"><span>{empty}</span><small>Solo se muestran envíos registrados y aceptados por SMTP.</small></div>;
}
