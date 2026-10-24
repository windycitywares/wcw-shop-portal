/** The social networks an owner can link to. Glyphs are simple outline drawings (24x24, currentColor) so they match the
 *  rest of the site; they are not the networks' official logos. `hover` is the network's colour: shown on hover for the icons, and as the badge colour in the Follow us band. */
export const SOCIAL_PLATFORMS = [
  { id: "instagram", label: "Instagram", hover: "#c13584", glyph: '<rect x="3.5" y="3.5" width="17" height="17" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17" cy="7" r="0.8" fill="currentColor"/>' },
  { id: "facebook", label: "Facebook", hover: "#1877f2", glyph: '<path d="M14 8.5h2.5V5H14c-2 0-3.5 1.6-3.5 3.6V11H8v3.5h2.5V21H14v-6.5h2.4l.6-3.5H14V9.1c0-.4.2-.6.6-.6z"/>' },
  { id: "tiktok", label: "TikTok", hover: "#111111", glyph: '<path d="M14 4v10.5a3.5 3.5 0 1 1-3.5-3.5"/><path d="M14 4c.3 2.3 1.8 3.8 4.5 4"/>' },
  { id: "pinterest", label: "Pinterest", hover: "#e60023", glyph: '<circle cx="12" cy="12" r="8.5"/><path d="M11 16.5l1.6-7.4M10.3 13c-1-2.6 1-4.5 2.8-4.3 2.2.3 2.3 3.2.8 4.4-.9.7-2 .6-2.3-.2"/>' },
  { id: "youtube", label: "YouTube", hover: "#ff0000", glyph: '<rect x="3" y="6" width="18" height="12" rx="3.5"/><path d="M10.2 9.5v5l4.3-2.5z"/>' },
  { id: "x", label: "X", hover: "#111111", glyph: '<path d="M5 5l14 14M19 5L5 19"/>' },
  { id: "linkedin", label: "LinkedIn", hover: "#0a66c2", glyph: '<rect x="3.5" y="3.5" width="17" height="17" rx="3"/><path d="M8 10.5V16M8 7.8v.1M11.5 16v-5.5M11.5 12.5c0-1.3 1-2.2 2.2-2.2s2.1.9 2.1 2.2V16"/>' },
  { id: "whatsapp", label: "WhatsApp", hover: "#1a9a4f", glyph: '<path d="M4 20l1.2-4A8 8 0 1 1 8.2 19z"/><path d="M9.5 9.2c0 3 2.3 5.3 5.3 5.3l.9-1.3-1.6-.9-.8.6c-.9-.4-1.6-1.1-2-2l.6-.8-.9-1.6z"/>' },
] as const;

export type SocialPlatformId = (typeof SOCIAL_PLATFORMS)[number]["id"];

export function socialOf(id: string) {
  return SOCIAL_PLATFORMS.find((p) => p.id === id) ?? SOCIAL_PLATFORMS[0];
}
