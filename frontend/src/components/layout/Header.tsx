import Link from "next/link";
import { getCategoryTree } from "@/lib/api";
import { site } from "@/lib/site";
import { Container } from "@/components/ui/misc";
import { CartButton } from "@/components/cart/CartButton";
import { AccountLink } from "./AccountLink";
import { MegaMenu } from "./MegaMenu";
import { MobileNav } from "./MobileNav";
import { SearchBar } from "./SearchBar";

export async function Header() {
  const tree = await getCategoryTree();
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-canvas/95 backdrop-blur supports-[backdrop-filter]:bg-canvas/80">
      <Container className="flex h-16 items-center gap-3 sm:gap-6">
        <MobileNav tree={tree} />
        <Link href="/" className="shrink-0 font-serif text-xl tracking-tight sm:text-2xl" aria-label={`${site.name} home`}>
          Windy City <span className="italic text-accent">Wares</span>
        </Link>
        <div className="hidden flex-1 md:block">
          <SearchBar className="mx-auto max-w-md" />
        </div>
        <div className="ml-auto flex items-center gap-1 md:ml-0">
          <AccountLink />
          <CartButton />
        </div>
      </Container>
      <div className="border-t border-line md:hidden">
        <Container className="py-2">
          <SearchBar id="site-search-mobile" />
        </Container>
      </div>
      <MegaMenu tree={tree} />
    </header>
  );
}
