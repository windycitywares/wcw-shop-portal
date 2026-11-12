import type { Metadata } from "next";
import { isLocale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";

type Props = { children: React.ReactNode; params: Promise<{ locale: string }> };

/** The page itself is a client component, so its title is set here. */
export async function generateMetadata({ params }: Pick<Props, "params">): Promise<Metadata> {
  const { locale } = await params;
  const t = getDictionary(isLocale(locale) ? locale : "en");
  return { title: t.account.title, robots: { index: false, follow: false } };
}

export default function Layout({ children }: Props) {
  return children;
}
