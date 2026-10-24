/** The marketplaces an owner can link to: label for people, and a brand-like colour pair for the storefront tile. */
export const SHOP_PLATFORMS = [
  { id: "etsy", label: "Etsy", bg: "#f1641e", fg: "#ffffff" },
  { id: "amazon", label: "Amazon", bg: "#ff9900", fg: "#111111" },
  { id: "ebay", label: "eBay", bg: "#0064d2", fg: "#ffffff" },
  { id: "walmart", label: "Walmart", bg: "#0071ce", fg: "#ffffff" },
  { id: "shopify", label: "Shopify", bg: "#4d7c3a", fg: "#ffffff" },
  { id: "facebook", label: "Facebook", bg: "#1877f2", fg: "#ffffff" },
  { id: "instagram", label: "Instagram", bg: "#c13584", fg: "#ffffff" },
  { id: "tiktok", label: "TikTok", bg: "#111111", fg: "#ffffff" },
  { id: "other", label: "Other", bg: "#3f4a52", fg: "#ffffff" },
] as const;

export type ShopPlatformId = (typeof SHOP_PLATFORMS)[number]["id"];

export function platformOf(id: string) {
  return SHOP_PLATFORMS.find((p) => p.id === id) ?? SHOP_PLATFORMS[SHOP_PLATFORMS.length - 1];
}
