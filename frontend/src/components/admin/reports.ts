/** Shapes and formatting for `/admin/reports/*` (see backend/app/services/reports). */
import { money, pct, fmtInt } from "./charts/format";
import type { Tone } from "./ui/Pill";

export interface Kpi {
  key: string;
  label: string;
  value: number | null;
  previous: number | null;
  delta: number | null;
  change: number | null;
  format: "money" | "number" | "percent";
  help: string;
  better: "up" | "down" | "none";
}

export interface Insight {
  key: string;
  severity: "critical" | "warning" | "opportunity" | "info" | "success";
  title: string;
  detail: string;
  action: string | null;
  href: string | null;
  metrics: Record<string, unknown>;
}

export interface Overview {
  range: { start: string; end: string; days: number; granularity: "day" | "week" | "month" };
  kpis: Kpi[];
  series: { bucket: string; label: string; orders: number; gross: number; refunds: number; net: number; sessions: number; visitors: number }[];
  channels: { channel: string; sessions: number; orders: number; revenue: number; conversion: number | null; share: number | null }[];
  top_products: { id: number; title: string; slug: string; units: number; merchandise: number; share: number | null }[];
  attention: { key: string; label: string; count: number; href: string; tone: "critical" | "warning" | "info" }[];
  live_visitors: number;
  recent_orders: { id: number; number: string; email: string; customer_name: string | null; status: string; payment_status: string; grand_total: number; placed_at: string | null }[];
  suggestions: Insight[];
  suggestion_count: number;
  generated_at: string;
}

export function formatKpi(k: Pick<Kpi, "value" | "format">): string {
  if (k.value == null) return "—";
  if (k.format === "money") return money(k.value);
  if (k.format === "percent") return pct(k.value);
  return fmtInt(k.value);
}

export const SEVERITY: Record<Insight["severity"], { label: string; tone: Tone }> = {
  critical: { label: "Urgent", tone: "danger" },
  warning: { label: "Fix soon", tone: "warning" },
  opportunity: { label: "Opportunity", tone: "accent" },
  info: { label: "Good to know", tone: "info" },
  success: { label: "Going well", tone: "success" },
};

export const CHANNEL_LABEL: Record<string, string> = {
  direct: "Direct",
  organic_search: "Search engines",
  paid_search: "Search ads",
  social: "Social media",
  paid_social: "Social ads",
  email: "Email",
  marketplace: "Marketplaces (Etsy…)",
  referral: "Other websites",
  affiliate: "Affiliates",
  display: "Display ads",
};

export const ORDER_STATUS: Record<string, { label: string; tone: Tone }> = {
  pending: { label: "Awaiting payment", tone: "warning" },
  paid: { label: "Paid, to ship", tone: "accent" },
  processing: { label: "Preparing", tone: "info" },
  shipped: { label: "Shipped", tone: "info" },
  delivered: { label: "Delivered", tone: "success" },
  cancelled: { label: "Cancelled", tone: "neutral" },
  refunded: { label: "Refunded", tone: "neutral" },
};
