/**
 * Storefront colour themes. The palettes live in globals.css (html[data-theme="…"]); this file lists
 * them for the switcher and holds the tiny script that applies the saved choice before first paint.
 */

export const THEMES = [
  // swatch: [page, panel, accent] — shown in the switcher
  { id: "classic", scheme: "light", swatch: ["#f2f3ef", "#ffffff", "#2f5468"], meta: "#f2f3ef" },
  { id: "linen", scheme: "light", swatch: ["#f6f1ea", "#fffdf9", "#9a4a2a"], meta: "#f6f1ea" },
  { id: "sage", scheme: "light", swatch: ["#eef2ec", "#ffffff", "#3a684c"], meta: "#eef2ec" },
  { id: "blush", scheme: "light", swatch: ["#f8f1f1", "#ffffff", "#874459"], meta: "#f8f1f1" },
  { id: "midnight", scheme: "dark", swatch: ["#0f151c", "#17202a", "#e3ad4f"], meta: "#0f151c" },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];
/** What the shopper picked: a theme, or "system" (Lakefront by day, Midnight if the device is in dark mode). */
export type ThemeChoice = ThemeId | "system";

export const THEME_KEY = "wcw-theme";
export const DEFAULT_THEME: ThemeChoice = "classic";

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
 * colours. `?theme=<id>` previews a theme without saving it (shareable links, CI screenshots). Kept dependency-free and wrapped in try/catch (storage can be blocked).
 */
export const themeBootScript = `(function(){try{var ids=${JSON.stringify(THEMES.map((t) => t.id))};var q=new URLSearchParams(location.search).get("theme");var c=q||localStorage.getItem("${THEME_KEY}")||"${DEFAULT_THEME}";var id=c==="system"?(window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches?"midnight":"classic"):c;if(ids.indexOf(id)<0)id="classic";document.documentElement.setAttribute("data-theme",id);}catch(e){document.documentElement.setAttribute("data-theme","classic");}})();`;
