"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** The old "Customer accounts" page now lives on Customers → Accounts. Kept so bookmarks still work. */
export default function CustomerAccountsMoved() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/admin/customers?view=accounts");
  }, [router]);
  return <p className="text-sm text-muted">Customer accounts moved to Customers → Accounts…</p>;
}
