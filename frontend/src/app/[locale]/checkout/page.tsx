import type { Metadata } from "next";
import { isLocale, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { CheckoutForm } from "@/components/checkout/CheckoutForm";
import { Container } from "@/components/ui/misc";

type Props = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  const t = getDictionary(isLocale(locale) ? locale : "en");
  return { title: t.checkout.title, robots: { index: false, follow: false } };
}

export default async function CheckoutPage({ params }: Props) {
  const { locale: raw } = await params;
  const locale: Locale = isLocale(raw) ? raw : "en";
  const t = getDictionary(locale);
  return (
    <Container className="py-12 sm:py-16">
      <p className="text-sm uppercase tracking-[0.14em] text-muted">{t.checkout.secure}</p>
      <h1 className="mt-2 text-5xl sm:text-6xl">{t.checkout.title}</h1>
      <div className="mt-10">
        <CheckoutForm />
      </div>
    </Container>
  );
}
