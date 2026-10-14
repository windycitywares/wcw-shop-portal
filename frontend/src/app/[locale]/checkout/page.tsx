import type { Metadata } from "next";
import { isLocale, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { CheckoutView } from "@/components/checkout/CheckoutView";

type Props = { params: Promise<{ locale: string }> };
const dict = (raw: string) => getDictionary((isLocale(raw) ? raw : "en") as Locale);

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const t = dict((await params).locale);
  return { title: t.checkout.title, description: t.checkout.metaDescription, robots: { index: false, follow: false } };
}

export default function CheckoutPage() {
  return <CheckoutView />;
}
