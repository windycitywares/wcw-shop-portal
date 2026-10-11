import Link from "next/link";
import { cn, formatPrice } from "@/lib/utils";

export function Container({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8", className)} {...props} />;
}

export function VisuallyHidden({ children }: { children: React.ReactNode }) {
  return <span className="sr-only">{children}</span>;
}

export function Badge({
  tone = "neutral",
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: "neutral" | "accent" | "success" | "danger" }) {
  const tones = {
    neutral: "bg-sand text-ink",
    accent: "bg-accent-soft text-accent",
    success: "bg-success/10 text-success",
    danger: "bg-danger/10 text-danger",
  };
  return (
    <span
      className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", tones[tone], className)}
      {...props}
    />
  );
}

export function Price({
  amount,
  compareAt,
  currency = "USD",
  className,
}: {
  amount: number;
  compareAt?: number | null;
  currency?: string;
  className?: string;
}) {
  const onSale = compareAt != null && compareAt > amount;
  return (
    <span className={cn("inline-flex items-baseline gap-2", className)}>
      <span className={onSale ? "text-sale" : undefined}>
        {onSale && <span className="sr-only">Sale price </span>}
        {formatPrice(amount, currency)}
      </span>
      {onSale && (
        <s className="text-sm text-muted">
          <span className="sr-only">Original price </span>
          {formatPrice(compareAt, currency)}
        </s>
      )}
    </span>
  );
}

export interface Crumb {
  label: string;
  href?: string;
}

export function Breadcrumbs({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="text-sm text-muted">
      <ol className="flex flex-wrap items-center gap-1.5">
        {items.map((item, i) => {
          const last = i === items.length - 1;
          return (
            <li key={`${item.label}-${i}`} className="flex items-center gap-1.5">
              {item.href && !last ? (
                <Link href={item.href} className="hover:text-ink hover:underline">
                  {item.label}
                </Link>
              ) : (
                <span aria-current={last ? "page" : undefined} className={last ? "text-ink" : undefined}>
                  {item.label}
                </span>
              )}
              {!last && <span aria-hidden="true">/</span>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="rounded-[var(--radius-card)] border border-dashed border-line px-6 py-16 text-center">
      <p className="font-serif text-xl">{title}</p>
      {children && <div className="mt-2 text-sm text-muted">{children}</div>}
    </div>
  );
}

export function Alert({
  tone = "info",
  children,
  className,
}: {
  tone?: "info" | "success" | "danger";
  children: React.ReactNode;
  className?: string;
}) {
  const tones = {
    info: "border-accent/30 bg-accent-soft text-accent-strong",
    success: "border-success/30 bg-success/10 text-success",
    danger: "border-danger/30 bg-danger/10 text-danger",
  };
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cn("rounded-lg border px-4 py-3 text-sm", tones[tone], className)}>
      {children}
    </div>
  );
}
