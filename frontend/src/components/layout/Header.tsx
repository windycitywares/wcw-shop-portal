import Link from "next/link";
import { getCategoryTree } from "@/lib/api";
import { localePath, type Locale } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { Container } from "@/components/ui/misc";
import { Logo } from "@/components/ui/Logo";
import { CartButton } from "@/components/cart/CartButton";
import { AccountMenu } from "./AccountMenu";
import { NotificationBell } from "./NotificationBell";
import { WishlistLink } from "./WishlistLink";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { ThemeSwitcher } from "./ThemeSwitcher";
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
          className="flex shrink-0 items-center rounded-full"
          aria-label={t.nav.homeLabel}
        >
          <Logo className="h-6 w-auto sm:h-8 xl:h-10" />
        </Link>
        <div className="hidden flex-1 lg:block">
          <MegaMenu tree={tree} />
        </div>
        <div className="ml-auto flex items-center gap-1 lg:ml-0">
          <SearchBar className="mr-2 hidden w-56 xl:block" />
          <LanguageSwitcher className="hidden sm:block" />
          <ThemeSwitcher className="hidden sm:block" />
          <WishlistLink />
          <NotificationBell />
          <AccountMenu />
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
