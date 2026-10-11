"use client";

import Link from "next/link";
import { isStaff, useAuth } from "@/lib/auth";

export function AccountLink() {
  const { user } = useAuth();
  const href = user ? (isStaff(user) ? "/admin" : "/account") : "/login";
  const label = user ? (isStaff(user) ? "Admin dashboard" : "Your account") : "Sign in";
  return (
    <Link href={href} className="grid size-10 place-items-center rounded-full hover:bg-sand" title={label}>
      <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.8">
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21a8 8 0 0 1 16 0" strokeLinecap="round" />
      </svg>
      <span className="sr-only">{label}</span>
    </Link>
  );
}
