/**
 * Storefront colour themes. The palettes live in globals.css (html[data-theme="…"]); this file lists
 * them for the switcher and holds the tiny script that applies the saved choice before first paint.
 */

export const THEMES = [
  // swatch: [page, panel, accent] — shown in the switcher
  { id: "classic", scheme: "light", swatch: ["#f2f3ef", "#ffffff", "#2f5468"], meta: "#f2f3ef" },
  { id: "midnight", scheme: "dark", swatch: ["#0f151c", "#17202a", "#e3ad4f"], meta: "#0f151c" },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];
/** What the shopper picked: Default or Dark. "system" is still read from older saved choices (it follows the device). */
export type ThemeChoice = ThemeId | "system";

export const THEME_KEY = "wcw-theme";
export const DEFAULT_THEME: ThemeChoice = "classic";

/*
 * Shared with windycitywares.com and the CRM: the choice is also saved in a `wcw-theme` cookie
 * ("classic" | "midnight") for the whole windycitywares.com domain, so switching on any of the three sites
 * carries over to the others. The cookie wins over this site's localStorage (kept as a fallback).
 * Same cookie in wcw-main-site lib/theme.ts and the CRM's lib/theme.ts.
 */
function cookieDomain(): string {
  const h = location.hostname;
  return h === "windycitywares.com" || h.endsWith(".windycitywares.com") ? "; domain=.windycitywares.com" : "";
}

function readCookie(): string | null {
  const m = document.cookie.match(/(?:^|;\s*)wcw-theme=([^;]*)/);
  return m ? decodeURIComponent(m[1]) : null;
}

/** The saved choice: shared cookie first, then this site's older localStorage value, else the default. */
export function readThemeChoice(): ThemeChoice {
  try {
    const v = readCookie() ?? localStorage.getItem(THEME_KEY);
    return v === "system" || THEMES.some((t) => t.id === v) ? (v as ThemeChoice) : DEFAULT_THEME;
  } catch {
    return DEFAULT_THEME;
  }
}

/** Saves a light/dark choice for all three sites (cookie) and for this one (localStorage). */
export function saveThemeChoice(id: ThemeId) {
  const secure = location.protocol === "https:" ? "; secure" : "";
  document.cookie = `${THEME_KEY}=${id}; path=/; max-age=31536000; samesite=lax${cookieDomain()}${secure}`;
  try {
    localStorage.setItem(THEME_KEY, id);
  } catch {
    /* private mode: the cookie still carries it */
  }
}

export function resolveTheme(choice: ThemeChoice): ThemeId {
  if (choice !== "system") return choice;
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "midnight"
    : "classic";
}

export function applyTheme(choice: ThemeChoice, animate = false) {
  const id = resolveTheme(choice);
  const root = document.documentElement;
  if (animate) {
    root.classList.add("theme-switching");
    window.setTimeout(() => root.classList.remove("theme-switching"), 300);
  }
  root.dataset.theme = id;
  const meta = document.querySelector('meta[name="theme-color"]');
  const t = THEMES.find((x) => x.id === id);
  if (meta && t) meta.setAttribute("content", t.meta);
  window.dispatchEvent(new CustomEvent("wcw-theme", { detail: id }));
}

/**
 * Inline <head> script: applies the saved theme synchronously so the page never flashes the default
 * colours. Order: `?theme=<id>` (a preview, not saved) → the shared cookie → localStorage → default. `?theme=<id>` previews a theme without saving it (shareable links, CI screenshots). Kept dependency-free and wrapped in try/catch (storage can be blocked).
 */
export const themeBootScript = `(function(){try{var ids=${JSON.stringify(THEMES.map((t) => t.id))};var q=new URLSearchParams(location.search).get("theme");var m=document.cookie.match(/(?:^|;\\s*)${THEME_KEY}=([^;]*)/);var c=q||(m&&decodeURIComponent(m[1]))||localStorage.getItem("${THEME_KEY}")||"${DEFAULT_THEME}";var id=c==="system"?(window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches?"midnight":"classic"):c;if(ids.indexOf(id)<0)id="classic";document.documentElement.setAttribute("data-theme",id);}catch(e){document.documentElement.setAttribute("data-theme","classic");}})();`;
