"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { SyntheticEvent } from "react";
import type { SessionUser } from "./account-session";
import { NotificationsLink } from "./notifications-link";
import { Icon } from "./ui/pictogram";
import { UserAvatar } from "./ui/user-avatar";
import type { IconName } from "./ui/pictogram";

type NavigationOption = { href: string; label: string; description: string; icon: IconName };
const primary = [["/", "Inicio"]] as const;
const publish: NavigationOption[] = [
  { href: "/perdi", label: "Perdí una mascota", description: "Publicá un aviso para empezar a buscarla.", icon: "paw" },
  { href: "/avistamiento", label: "Vi una mascota", description: "Compartí dónde viste una mascota suelta.", icon: "eye" },
  { href: "/encontre", label: "Encontré una mascota", description: "Reportá una mascota que está a salvo con vos.", icon: "heart" },
];
const explore = [["/perdidos", "Mascotas reportadas"], ["/mapa", "Mapa"], ["/#como-funciona", "Cómo funciona"], ["/contacto", "Contacto y sugerencias"]] as const;
const accountLinks: NavigationOption[] = [
  { href: "/mi-cuenta", label: "Mi cuenta", description: "Datos de contacto y preferencias", icon: "user" },
  { href: "/mis-avisos", label: "Mis avisos", description: "Publicaciones y coincidencias", icon: "paw" },
  { href: "/notificaciones", label: "Notificaciones", description: "Novedades de tus búsquedas", icon: "bell" },
];
const accessLinks: NavigationOption[] = [
  { href: "/login", label: "Ingresar", description: "Accedé a tus avisos y notificaciones", icon: "user" },
  { href: "/crear-cuenta", label: "Crear cuenta", description: "Registrate para publicar tus avisos", icon: "edit" },
];

export function SiteHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<SessionUser | null>(null);
  const [sessionReady, setSessionReady] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [logoutError, setLogoutError] = useState("");
  const exploreMenu = useRef<HTMLDetailsElement>(null);
  const publishMenu = useRef<HTMLDetailsElement>(null);
  const mobileMenu = useRef<HTMLDetailsElement>(null);
  const mobilePublishMenu = useRef<HTMLDetailsElement>(null);
  const accountMenu = useRef<HTMLDetailsElement>(null);
  const header = useRef<HTMLElement>(null);
  useEffect(() => {
    const element = header.current;
    if (!element) return;
    const updateHeight = () => document.documentElement.style.setProperty("--site-header-height", `${Math.ceil(element.getBoundingClientRect().height)}px`);
    updateHeight();
    const observer = new ResizeObserver(updateHeight);
    observer.observe(element);
    return () => { observer.disconnect(); document.documentElement.style.removeProperty("--site-header-height"); };
  }, []);
  useEffect(() => {
    const menus = [exploreMenu, publishMenu, mobilePublishMenu, mobileMenu, accountMenu];
    function dismissOutside(event: Event) {
      if (!(event.target instanceof Node)) return;
      for (const ref of menus) {
        const menu = ref.current;
        if (menu?.open && !menu.contains(event.target)) menu.open = false;
      }
    }
    function dismissEscape(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      for (const ref of menus) {
        const menu = ref.current;
        if (!menu?.open) continue;
        const focusedInside = menu.contains(document.activeElement);
        menu.open = false;
        if (focusedInside) { menu.querySelector("summary")?.focus(); event.preventDefault(); }
      }
    }
    document.addEventListener("pointerdown", dismissOutside, true);
    document.addEventListener("focusin", dismissOutside);
    document.addEventListener("keydown", dismissEscape);
    return () => {
      document.removeEventListener("pointerdown", dismissOutside, true);
      document.removeEventListener("focusin", dismissOutside);
      document.removeEventListener("keydown", dismissEscape);
    };
  }, []);
  useEffect(() => {
    let disposed = false;
    let controller: AbortController | undefined;
    async function load() {
      controller?.abort(); controller = new AbortController();
      const signal = controller.signal;
      try {
        const response = await fetch("/api/session", { cache: "no-store", signal });
        if (response.ok) {
          const session = await response.json();
          if (!disposed && !signal.aborted) setUser(session.user ?? null);
        }
      } catch { /* Navigation stays available while the session service is unavailable. */ }
      finally { if (!disposed && !signal.aborted) setSessionReady(true); }
    }
    void load(); window.addEventListener("mascomatch:session", load); window.addEventListener("focus", load);
    return () => { disposed = true; controller?.abort(); window.removeEventListener("mascomatch:session", load); window.removeEventListener("focus", load); };
  }, []);
  useEffect(() => {
    for (const ref of [exploreMenu, publishMenu, mobilePublishMenu, mobileMenu, accountMenu]) if (ref.current) ref.current.open = false;
    setLogoutError("");
  }, [pathname]);
  function toggleMenu(event: SyntheticEvent<HTMLDetailsElement>) {
    const opened = event.currentTarget;
    if (!opened.open) {
      if (opened === mobileMenu.current && mobilePublishMenu.current) mobilePublishMenu.current.open = false;
      return;
    }
    for (const ref of [exploreMenu, publishMenu, mobilePublishMenu, mobileMenu, accountMenu]) {
      const menu = ref.current;
      if (menu && !menu.contains(opened) && !opened.contains(menu)) menu.open = false;
    }
  }
  function closeOnNavigation(event: SyntheticEvent<HTMLElement>) {
    if (event.target instanceof Element && event.target.closest("a")) {
      let menu = event.target.closest("details");
      while (menu) { menu.open = false; menu = menu.parentElement?.closest("details") ?? null; }
    }
  }
  async function logout() {
    if (leaving) return;
    setLeaving(true); setLogoutError("");
    try {
      const response = await fetch("/api/session", { method: "DELETE" });
      if (!response.ok) throw new Error("LOGOUT_UNAVAILABLE");
      setUser(null);
      if (accountMenu.current) accountMenu.current.open = false;
      window.dispatchEvent(new Event("mascomatch:session"));
      router.push("/"); router.refresh();
    } catch {
      setLogoutError("No pudimos cerrar la sesión. Intentá de nuevo.");
      if (accountMenu.current) accountMenu.current.open = true;
    } finally { setLeaving(false); }
  }
  const active = (href: string) => href !== "/#como-funciona" && (href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/"));
  const links = (items: readonly (readonly [string, string])[]) => items.map(([href, label]) => <Link key={href} href={href} aria-current={active(href) ? "page" : undefined}>{label}</Link>);
  const publishLinks = () => publish.map(item => <Link key={item.href} href={item.href} aria-current={active(item.href) ? "page" : undefined}><Icon name={item.icon} /><span><strong>{item.label}</strong><small>{item.description}</small></span></Link>);
  const publishing = publish.some(item => active(item.href));
  const accountActive = user ? accountLinks.some(item => active(item.href)) || active("/admin") : accessLinks.some(item => active(item.href));
  return (
    <header ref={header} className="site-header" data-session={!sessionReady ? "checking" : user ? "signed-in" : "signed-out"}>
      <a className="skip-link" href="#main-content">Ir al contenido</a>
      <div className="site-header-inner">
        <Link href="/" className="site-name" aria-label="MascoMatch, inicio"><span className="brand-mark"><Icon name="paw" /></span><span>Masco<span className="brand-accent">Match</span></span></Link>
        <nav className="desktop-navigation" aria-label="Navegación principal">
          {links(primary)}
          <details ref={publishMenu} className="publish-menu" data-active={publishing} onToggle={toggleMenu}><summary>Publicar <Icon name="chevron" className="publish-chevron" /></summary><div className="publish-links" onClick={closeOnNavigation}>{publishLinks()}</div></details>
          <details ref={exploreMenu} className="explore-menu" onToggle={toggleMenu}><summary aria-label="Explorar MascoMatch">Explorar <Icon name="chevron" className="explore-chevron" /></summary><div className="explore-links" onClick={closeOnNavigation}>{links(explore)}</div></details>
        </nav>
        <div className="header-actions">
          <Link href="/apoyanos" className="button support-link" aria-current={active("/apoyanos") ? "page" : undefined}><Icon name="heart" />Apoyanos</Link>
          <div className="header-tools session-tools" role="group" aria-label="Acceso a tu cuenta" aria-busy={!sessionReady}>
            {!sessionReady ? <span className="session-placeholder" role="status"><Icon name="user" /><span className="session-placeholder-line" aria-hidden="true" /><span className="sr-only">Consultando sesión</span></span> : <>
              {user && <><NotificationsLink /><span className="session-divider" aria-hidden="true" /></>}
              <details ref={accountMenu} className="account-menu" data-active={accountActive} onToggle={toggleMenu}>
                <summary aria-label={user ? "Abrir opciones de mi cuenta" : "Abrir opciones de cuenta"} aria-controls="header-account-panel">{user ? <UserAvatar name={user.name} version={user.avatar_version} className="account-avatar" /> : <span className="account-avatar" aria-hidden="true"><Icon name="user" /></span>}<span className="account-trigger-label">{user?.name.trim().split(/\s+/)[0] || "Mi cuenta"}</span><Icon name="chevron" className="account-chevron" /></summary>
                <div id="header-account-panel" className="account-panel" onClick={closeOnNavigation}>
                  <div className="account-panel-heading">{user ? <UserAvatar name={user.name} version={user.avatar_version} className="account-avatar account-panel-avatar" /> : <span className="account-avatar account-panel-avatar" aria-hidden="true"><Icon name="user" /></span>}<div><strong>{user?.name || "Tu cuenta en MascoMatch"}</strong><span>{user ? "Tus avisos y preferencias" : "Ingresá o creá una cuenta"}</span></div></div>
                  <nav className="account-panel-links" aria-label={user ? "Navegación de tu cuenta" : "Acceso a tu cuenta"}>
                    {(user ? accountLinks : accessLinks).map(item => <Link key={item.href} href={item.href} aria-current={active(item.href) ? "page" : undefined}><Icon name={item.icon} /><span><strong>{item.label}</strong><small>{item.description}</small></span></Link>)}
                    {user?.admin_access && <Link href="/admin" aria-current={active("/admin") ? "page" : undefined}><Icon name="shield" /><span><strong>Administración</strong><small>Gestionar la plataforma</small></span></Link>}
                  </nav>
                  {user && <div className="account-panel-footer"><button type="button" className="account-signout" disabled={leaving} onClick={() => void logout()}><Icon name="logout" />{leaving ? "Cerrando sesión…" : "Cerrar sesión"}</button>{logoutError && <p className="account-signout-error" role="alert">{logoutError}</p>}</div>}
                </div>
              </details>
            </>}
          </div>
          <details ref={mobileMenu} className="mobile-menu" onToggle={toggleMenu}><summary aria-label="Abrir navegación principal"><Icon name="menu" />Menú</summary><nav aria-label="Navegación móvil" onClick={closeOnNavigation}>{links(primary)}<details ref={mobilePublishMenu} className="publish-menu mobile-publish-menu" data-active={publishing} onToggle={toggleMenu}><summary>Publicar <Icon name="chevron" className="publish-chevron" /></summary><div className="publish-links">{publishLinks()}</div></details>{links(explore)}</nav></details>
        </div>
      </div>
    </header>
  );
}
