import Link from "next/link";
import { getCategoryTree } from "@/lib/api";
import { localePath, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { Container } from "@/components/ui/misc";
import { CartButton } from "@/components/cart/CartButton";
import { AccountLink } from "./AccountLink";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { MegaMenu } from "./MegaMenu";
import { MobileNav } from "./MobileNav";
import { SearchBar } from "./SearchBar";

export async function Header({ locale }: { locale: Locale }) {
  const [tree, t] = [await getCategoryTree(locale), getDictionary(locale)];
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-canvas/95 backdrop-blur supports-[backdrop-filter]:bg-canvas/85">
      <Container className="flex h-16 items-center gap-3 sm:gap-6 lg:h-[4.5rem]">
        <MobileNav tree={tree} />
        <Link
          href={localePath(locale, "/")}
          className="shrink-0 font-serif text-[1.35rem] font-normal tracking-[-0.01em] sm:text-2xl"
          aria-label={t.nav.homeLabel}
        >
          Windy City Wares
        </Link>
        <div className="hidden flex-1 lg:block">
          <MegaMenu tree={tree} />
        </div>
        <div className="ml-auto flex items-center gap-1 lg:ml-0">
          <SearchBar className="mr-2 hidden w-56 xl:block" />
          <LanguageSwitcher className="hidden sm:block" />
          <AccountLink />
          <CartButton />
        </div>
      </Container>
      <div className="border-t border-line xl:hidden">
        <Container className="py-2">
          <SearchBar id="site-search-compact" />
        </Container>
      </div>
    </header>
  );
}
