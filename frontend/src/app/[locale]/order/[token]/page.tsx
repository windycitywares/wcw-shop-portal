import type { Metadata } from "next";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { OrderView } from "@/components/checkout/OrderView";
import { Container } from "@/components/ui/misc";

type Props = { params: Promise<{ locale: string; token: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = getDictionary(isLocale(locale) ? locale : "en");
  // Private page: never indexed, never shared in link previews.
  return { title: t.order.metaTitle, robots: { index: false, follow: false }, referrer: "no-referrer" };
}

/** The private order page (link in every order email). Loaded in the browser so it is never cached on the server. */
export default async function OrderPage({ params }: Props) {
  const { token } = await params;
  return (
    <Container className="py-12 sm:py-16">
      <OrderView token={token} />
    </Container>
  );
}
