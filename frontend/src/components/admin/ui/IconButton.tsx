"use client";

import { forwardRef } from "react";
import { cn } from "@/lib/utils";
import { Icon, type IconName } from "./Icon";

/** An icon-only button. `label` is both the tooltip and the accessible name ("Edit coupon SAVE10"). */
export const IconButton = forwardRef<
  HTMLButtonElement,
  { icon: IconName; label: string; tone?: "default" | "danger" } & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "children" | "title">
>(function IconButton({ icon, label, tone = "default", className, type = "button", ...props }, ref) {
  return (
    <button
      ref={ref}
      type={type}
      title={label}
      aria-label={label}
      className={cn(
        "grid size-8 place-items-center rounded-full text-muted transition-colors focus-visible:outline-2 disabled:pointer-events-none disabled:opacity-50",
        tone === "danger" ? "hover:bg-danger/10 hover:text-danger" : "hover:bg-sand hover:text-ink",
        className,
      )}
      {...props}
    >
      <Icon name={icon} className="size-4" />
    </button>
  );
});

/** Right-aligned group of row actions. */
export function RowActions({ children }: { children: React.ReactNode }) {
  return <div className="flex items-center justify-end gap-1">{children}</div>;
}
