import type { Metadata } from "next";
import { fmt, isLocale, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { OrderView } from "@/components/orders/OrderView";

type Props = { params: Promise<{ locale: string; number: string }> };
const dict = (raw: string) => getDictionary((isLocale(raw) ? raw : "en") as Locale);

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, number } = await params;
  // The link carries a secret token, so keep it out of search results and never send it to other sites.
  return {
    title: fmt(dict(locale).order.title, { number }),
    robots: { index: false, follow: false },
    referrer: "no-referrer",
  };
}

export default async function OrderPage({ params }: Props) {
  const { number } = await params;
  return <OrderView number={number} />;
}
