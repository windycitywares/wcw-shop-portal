import { redirect } from "next/navigation";

/** Etsy connection settings live in Settings → External shops; the working pages hang off the sidebar's Etsy group. */
export default function AdminEtsy() {
  redirect("/admin/etsy/products");
}
