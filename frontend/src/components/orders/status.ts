import type { OrderStatus } from "@/lib/types";

export const STATUS_TONE: Record<OrderStatus, "neutral" | "accent" | "success" | "danger"> = {
  pending: "neutral",
  paid: "accent",
  processing: "accent",
  shipped: "success",
  delivered: "success",
  cancelled: "danger",
  refunded: "neutral",
};

/** A tracking page for the carriers we usually ship with; null for anything else. */
export function trackingUrl(carrier: string | null, number: string | null): string | null {
  if (!carrier || !number) return null;
  const n = encodeURIComponent(number);
  const c = carrier.toLowerCase();
  if (c.includes("usps")) return `https://tools.usps.com/go/TrackConfirmAction?tLabels=${n}`;
  if (c.includes("ups")) return `https://www.ups.com/track?tracknum=${n}`;
  if (c.includes("fedex")) return `https://www.fedex.com/fedextrack/?trknbr=${n}`;
  if (c.includes("dhl")) return `https://www.dhl.com/en/express/tracking.html?AWB=${n}`;
  return null;
}
