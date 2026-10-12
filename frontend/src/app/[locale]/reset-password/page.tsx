import type { Metadata } from "next";
import { isLocale, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { ResetPasswordForm } from "@/components/account/PasswordForms";
import { Container } from "@/components/ui/misc";

type Props = { params: Promise<{ locale: string }> };
const dict = (raw: string) => getDictionary((isLocale(raw) ? raw : "en") as Locale);

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  // no-referrer: the reset token is in the URL, so never send it to other sites.
  return {
    title: dict((await params).locale).password.resetTitle,
    robots: { index: false, follow: false },
    referrer: "no-referrer",
  };
}

export default async function ResetPasswordPage({ params }: Props) {
  const t = dict((await params).locale);
  return (
    <Container className="max-w-md py-16 sm:py-24">
      <h1 className="text-5xl">{t.password.resetTitle}</h1>
      <p className="mt-4 text-muted">{t.password.resetText}</p>
      <ResetPasswordForm />
    </Container>
  );
}
