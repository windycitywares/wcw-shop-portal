"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import { Alert } from "@/components/ui/misc";

type Stats = Record<"draft" | "in_review" | "published" | "archived" | "low_stock", number>;

const CARDS: { key: keyof Stats; label: string; href: string }[] = [
  { key: "published", label: "Live products", href: "/admin/products?status=published" },
  { key: "in_review", label: "Awaiting review", href: "/admin/products?status=in_review" },
  { key: "draft", label: "Drafts", href: "/admin/products?status=draft" },
  { key: "low_stock", label: "Low stock (≤ 3)", href: "/admin/products?status=published" },
];

export default function AdminDashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<Stats>("/products/stats").then(setStats, (e) => setError(e.message));
  }, []);

  return (
    <div>
      <h1 className="text-4xl">Welcome{user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}</h1>
      <p className="mt-2 text-muted">Here’s the state of the catalog.</p>
      {error && <Alert tone="danger" className="mt-6">{error}</Alert>}
      <ul className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {CARDS.map((c) => (
          <li key={c.key}>
            <Link href={c.href} className="block rounded-[var(--radius-card)] border border-line bg-surface p-5 hover:border-accent">
              <p className="text-sm text-muted">{c.label}</p>
              <p className="mt-2 font-serif text-4xl">{stats ? stats[c.key] : "—"}</p>
            </Link>
          </li>
        ))}
      </ul>
      <p className="mt-8 text-sm text-muted">
        Sales, active carts and order metrics will appear here once checkout and orders are switched on.
      </p>
    </div>
  );
}
