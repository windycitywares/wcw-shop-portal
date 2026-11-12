import type { Metadata } from "next";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { TestPaymentForm } from "@/components/checkout/TestPaymentForm";
import { Container } from "@/components/ui/misc";

type Props = { params: Promise<{ locale: string; token: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = getDictionary(isLocale(locale) ? locale : "en");
  return { title: t.testPayment.title, robots: { index: false, follow: false }, referrer: "no-referrer" };
}

/** Test mode's stand-in for Stripe's hosted card page. Private (the order's token is the key), never indexed. */
export default async function TestPaymentPage({ params }: Props) {
  const { token } = await params;
  return (
    <Container className="max-w-lg py-12 sm:py-16">
      <TestPaymentForm token={token} />
    </Container>
  );
}
