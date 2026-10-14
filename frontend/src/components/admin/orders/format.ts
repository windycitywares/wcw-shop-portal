import type { Tone } from "@/components/admin/ui/Pill";
import type { OrderStatus, PaymentProvider } from "@/lib/types";

export const STATUS_LABEL: Record<OrderStatus, string> = {
  pending: "Awaiting payment",
  paid: "Paid",
  processing: "Being prepared",
  shipped: "Shipped",
  delivered: "Delivered",
  cancelled: "Cancelled",
  refunded: "Refunded",
};

export const STATUS_TONE: Record<OrderStatus, Tone> = {
  pending: "warning",
  paid: "accent",
  processing: "info",
  shipped: "info",
  delivered: "success",
  cancelled: "neutral",
  refunded: "neutral",
};

export const PROVIDER_LABEL: Record<PaymentProvider, string> = { stripe: "Card (Stripe)", offline: "Invoice", test: "Test payment" };

export const CARRIERS = ["USPS", "UPS", "FedEx", "DHL", "Other"] as const;

const DATE = new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" });
const DAY = new Intl.DateTimeFormat("en-US", { dateStyle: "medium" });

export const fmtDateTime = (iso: string | null | undefined) => (iso ? DATE.format(new Date(iso)) : "—");
export const fmtDay = (iso: string | null | undefined) => (iso ? DAY.format(new Date(iso)) : "—");
