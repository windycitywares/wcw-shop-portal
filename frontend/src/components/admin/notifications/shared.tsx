"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { timeAgo } from "../charts/format";
import { Icon, type IconName } from "../ui/Icon";

export interface Activity {
  id: string;
  type: "order" | "refund" | "message" | "stock_request" | "review" | "signup" | "backup_failed";
  at: string;
  unread: boolean;
  title: string;
  detail: string;
  href: string;
  tone: "success" | "warning" | "danger" | "info" | "accent" | "neutral";
}

export interface Feed {
  items: Activity[];
  unread: number;
  seen_at: string | null;
  kinds: Activity["type"][];
}

export const KIND: Record<Activity["type"], { label: string; icon: IconName }> = {
  order: { label: "Orders", icon: "orders" },
  refund: { label: "Refunds", icon: "orders" },
  message: { label: "Messages", icon: "inbox" },
  stock_request: { label: "Stock requests", icon: "bell" },
  review: { label: "Reviews", icon: "star" },
  signup: { label: "New customers", icon: "customers" },
  backup_failed: { label: "Backups", icon: "archive" },
};

const TONE: Record<Activity["tone"], string> = {
  success: "bg-success/12 text-success",
  warning: "bg-warning/14 text-warning",
  danger: "bg-danger/12 text-danger",
  info: "bg-[color-mix(in_oklab,var(--viz-1)_14%,transparent)] text-ink",
  accent: "bg-accent-soft text-accent-strong",
  neutral: "bg-sand text-muted",
};

/** One line of activity: what happened, who/what, when, and a link to where it's handled. */
export function ActivityRow({ item, onNavigate, compact }: { item: Activity; onNavigate?: () => void; compact?: boolean }) {
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      className={cn("flex items-start gap-3 rounded-[var(--radius-control)] px-3 py-2.5 hover:bg-sand", item.unread && "bg-accent-soft/40")}
    >
      <span className={cn("mt-0.5 grid size-8 shrink-0 place-items-center rounded-full", TONE[item.tone])}>
        <Icon name={KIND[item.type].icon} className="size-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className={cn("block text-sm", item.unread ? "font-semibold" : "font-medium", compact && "truncate")}>{item.title}</span>
        {item.detail && <span className={cn("block text-xs text-muted", compact && "truncate")}>{item.detail}</span>}
        <span className="block text-xs text-muted">{timeAgo(item.at)}</span>
      </span>
      {item.unread && (
        <span className="mt-2 size-2 shrink-0 rounded-full bg-accent">
          <span className="sr-only">New</span>
        </span>
      )}
    </Link>
  );
}
