import type { Metadata } from "next";
import { isLocale, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { ForgotPasswordForm } from "@/components/account/PasswordForms";
import { Container } from "@/components/ui/misc";

type Props = { params: Promise<{ locale: string }> };
const dict = (raw: string) => getDictionary((isLocale(raw) ? raw : "en") as Locale);

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  return { title: dict((await params).locale).password.forgotTitle, robots: { index: false, follow: false } };
}

export default async function ForgotPasswordPage({ params }: Props) {
  const t = dict((await params).locale);
  return (
    <Container className="max-w-md py-16 sm:py-24">
      <h1 className="text-5xl">{t.password.forgotTitle}</h1>
      <p className="mt-4 text-muted">{t.password.forgotText}</p>
      <ForgotPasswordForm />
    </Container>
  );
}
