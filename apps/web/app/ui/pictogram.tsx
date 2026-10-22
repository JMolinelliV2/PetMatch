import type { ReactNode } from "react";

const paths = {
  paw: <><ellipse cx="5.5" cy="8" rx="2" ry="2.8" /><ellipse cx="10" cy="5.5" rx="2" ry="2.8" /><ellipse cx="15.5" cy="5.5" rx="2" ry="2.8" /><ellipse cx="20" cy="9" rx="2" ry="2.8" /><path d="M6 18c0-3 3-7 6.5-7S19 15 19 18c0 2-1.5 3-3.5 2.5-2-.7-4-.7-6 0C7.5 21 6 20 6 18Z" /></>,
  camera: <><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3Z" /><circle cx="12" cy="13" r="4" /></>,
  pin: <><path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z" /><circle cx="12" cy="10" r="2.5" /></>,
  eye: <><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></>,
  heart: <path d="M20.5 4.5a5 5 0 0 0-7 0L12 6l-1.5-1.5a5 5 0 0 0-7 7L12 20l8.5-8.5a5 5 0 0 0 0-7Z" />,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4" /><path d="M12 2V1" /></>,
  user: <><circle cx="12" cy="7" r="4" /><path d="M20 22v-3a8 8 0 0 0-16 0v3Z" /></>,
  arrow: <><path d="M4 12h16M14 6l6 6-6 6" /></>,
  chevron: <path d="m9 5 7 7-7 7" />,
  check: <path d="m4 12 5 5L20 6" />,
  menu: <path d="M3 6h18M3 12h18M3 18h18" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  expand: <path d="M9 3H3v6M15 3h6v6M21 15v6h-6M9 21H3v-6" />,
  search: <><circle cx="10.5" cy="10.5" r="7.5" /><path d="m16 16 6 6" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 6v6l4 2" /></>,
  refresh: <><path d="M20 7a9 9 0 0 0-15-2L2 8m0-5v5h5M4 17a9 9 0 0 0 15 2l3-3m0 5v-5h-5" /></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M7 2v6M17 2v6M3 11h18" /></>,
  edit: <><path d="m15 4 5 5M4 20l4-1 12-12a3.5 3.5 0 0 0-5-5L3 14l-1 6Z" /></>,
  spark: <path d="m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3Z" />,
  shield: <><path d="m12 2 9 4v6c0 6-9 10-9 10S3 18 3 12V6Z" /><path d="m8 12 3 3 5-6" /></>,
  grid: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
  chart: <><path d="M3 3v18h18M7 15l4-5 4 3 6-8" /></>,
  mail: <><rect x="2" y="4" width="20" height="16" rx="3" /><path d="m3 6 9 7 9-7" /></>,
  message: <path d="M21 12a8 8 0 0 1-8 8H3l2-5a8 8 0 1 1 16-3Z" />,
  layers: <><path d="m12 2 10 5-10 5L2 7Zm-9 10 9 5 9-5M3 17l9 5 9-5" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 1v2M12 21v2M1 12h2M21 12h2M4 4l1.5 1.5M18.5 18.5 20 20M4 20l1.5-1.5M18.5 5.5 20 4" /></>,
  moon: <path d="M21 13a9 9 0 0 1-10-10A9 9 0 1 0 21 13Z" />,
  logout: <><path d="M9 4H3v16h6M9 12h12m-5-5 5 5-5 5" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6" /><circle cx="12" cy="7.5" r=".7" fill="currentColor" stroke="none" /></>,
} satisfies Record<string, ReactNode>;

export type IconName = keyof typeof paths;

export function Icon({ name, className = "" }: { name: IconName; className?: string }) {
  return <svg viewBox="0 0 24 24" className={`ui-icon ${className}`} aria-hidden="true" focusable="false" fill={name === "paw" ? "currentColor" : "none"} stroke={name === "paw" ? "none" : "currentColor"} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}
