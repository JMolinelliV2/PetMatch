"use client";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { Icon } from "../ui/pictogram";
import type { IconName } from "../ui/pictogram";
import type { SessionUser } from "../account-session";
import type { OperationSection } from "./operations-dashboard";
import type {AnalyticsSection} from "./analytics-dashboard";
import {AdminReloadButton} from "./admin-reload";

export type AdminView = OperationSection | "matching" | "management" | "donations" | AnalyticsSection;
const groups: { label: string; items: { view: AdminView; label: string; icon: IconName }[] }[] = [
  {label:"Datos del producto",items:[{view:"growth",label:"Crecimiento",icon:"chart"},{view:"usage",label:"Uso",icon:"paw"},{view:"analytics-matching",label:"Matching e IA",icon:"spark"},{view:"impact",label:"Impacto",icon:"heart"},{view:"inventory",label:"Inventario potencial",icon:"layers"}]},
  { label: "Plataforma", items: [{ view: "overview", label: "Resumen", icon: "grid" }, { view: "users", label: "Usuarios", icon: "user" }, { view: "publications", label: "Publicaciones", icon: "paw" }, { view: "donations", label: "Aportes", icon: "heart" }] },
  { label: "Inteligencia", items: [{ view: "jobs", label: "Trabajos", icon: "layers" }] },
  { label: "Comunicación", items: [{ view: "mail", label: "Correos", icon: "mail" }, { view: "contacts", label: "Contactos", icon: "message" }] },
  { label: "Control", items: [{ view: "management", label: "Denuncias y correcciones", icon: "shield" }, { view: "audit", label: "Auditoría", icon: "clock" }] },
];

export function AdminWorkspace({ user, logout, children }: { user: SessionUser; logout: () => Promise<void>; children: (view: AdminView, navigate: (view: AdminView) => void) => ReactNode }) {
  const [view, setView] = useState<AdminView>("overview");
  const [theme, setTheme] = useState("dark");
  const [menuOpen, setMenuOpen] = useState(false);
  const [leaving, setLeaving] = useState(false);
  useEffect(() => { try { const stored = localStorage.getItem("mascomatch:admin-theme"); if (stored === "light" || stored === "dark") setTheme(stored); } catch {} }, []);
  function toggleTheme() { const next = theme === "dark" ? "light" : "dark"; setTheme(next); try { localStorage.setItem("mascomatch:admin-theme", next); } catch {} }
  function navigate(next: AdminView) { setView(next); setMenuOpen(false); }
  const label = groups.flatMap(group => group.items).find(item => item.view === view)?.label;
  const initials = user.name.trim().split(/\s+/).slice(0, 2).map(word => word[0]).join("").toUpperCase();
  return <div className="admin-workspace" data-theme={theme} data-menu-open={menuOpen} onKeyDown={event => { if (event.key === "Escape") setMenuOpen(false); }}>
    <h1 className="sr-only">Panel de administración de MascoMatch</h1>
    <a className="skip-link" href="#admin-workspace-content">Ir al panel</a>
    {menuOpen && <button type="button" className="admin-menu-backdrop" aria-label="Cerrar navegación" onClick={() => setMenuOpen(false)} />}
    <aside className="admin-sidebar" id="admin-sidebar">
      <Link className="admin-brand" href="/" aria-label="MascoMatch, inicio"><span className="admin-brand-mark"><Icon name="paw" /></span><span>Masco<span>Match</span><small>Administración</small></span></Link>
      <nav aria-label="Secciones de administración" className="admin-sidebar-navigation">{groups.map(group => <div className="admin-navigation-group" key={group.label}><p>{group.label}</p>{group.items.map(item => <button key={item.view} type="button" aria-pressed={view === item.view} onClick={() => navigate(item.view)}><Icon name={item.icon} /><span>{item.label}</span>{view === item.view && <span className="admin-nav-indicator" aria-hidden="true" />}</button>)}</div>)}</nav>
      <div className="admin-sidebar-bottom"><Link className="admin-user-profile" href="/mi-cuenta"><span className="admin-user-avatar" aria-hidden="true">{initials}</span><span><strong>{user.name}</strong><small>Cuenta administradora</small></span></Link><button className="admin-signout" type="button" disabled={leaving} onClick={async () => { setLeaving(true); try { await logout(); } finally { setLeaving(false); } }}><Icon name="logout" />{leaving ? "Cerrando sesión…" : "Cerrar sesión"}</button></div>
    </aside>
    <div className="admin-workspace-main">
      <header className="admin-topbar"><div className="admin-breadcrumb"><button type="button" className="admin-mobile-menu" aria-label={menuOpen ? "Cerrar menú del panel" : "Abrir menú del panel"} aria-expanded={menuOpen} aria-controls="admin-sidebar" onClick={() => setMenuOpen(value => !value)}><Icon name={menuOpen ? "close" : "menu"} /></button><span>Administración</span><Icon name="chevron" /><strong>{label}</strong></div><div className="admin-topbar-actions"><span className="admin-private-label"><Icon name="shield" />Acceso privado</span><button type="button" className="admin-theme-button" onClick={toggleTheme} aria-label={`Cambiar a modo ${theme === "dark" ? "claro" : "oscuro"}`}><Icon name={theme === "dark" ? "sun" : "moon"} /></button></div></header>
      <div id="admin-workspace-content" className="admin-workspace-content" tabIndex={-1}>{children(view, navigate)}</div>
    </div>
    <AdminReloadButton/>
  </div>;
}
