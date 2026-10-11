import Link from "next/link";
import { site } from "@/lib/site";
import { Container } from "@/components/ui/misc";
import { NewsletterForm } from "./NewsletterForm";

const columns = [
  {
    title: "Shop",
    links: [
      { label: "Shop all", href: "/shop" },
      { label: "New arrivals", href: "/shop?sort=newest" },
      { label: "Search", href: "/search" },
    ],
  },
  {
    title: "Your account",
    links: [
      { label: "Sign in", href: "/login" },
      { label: "Account", href: "/account" },
      { label: "Cart", href: "/cart" },
    ],
  },
];

export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="mt-24 border-t border-line bg-sand/60">
      <Container className="grid gap-12 py-14 md:grid-cols-[1.5fr_1fr_1fr]">
        <div className="max-w-sm">
          <p className="font-serif text-2xl">Stay in the loop</p>
          <p className="mt-2 text-sm text-muted">New pieces and the occasional shop update. No spam.</p>
          <NewsletterForm />
        </div>
        {columns.map((col) => (
          <nav key={col.title} aria-label={col.title}>
            <h2 className="font-sans text-sm font-semibold uppercase tracking-wider">{col.title}</h2>
            <ul className="mt-4 space-y-2.5 text-sm">
              {col.links.map((l) => (
                <li key={l.href}>
                  <Link href={l.href} className="text-muted hover:text-ink">
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </Container>
      <Container className="flex flex-col gap-4 border-t border-line py-6 text-sm text-muted sm:flex-row sm:items-center sm:justify-between">
        <p>
          © {year} {site.name}. All rights reserved.
        </p>
        <ul className="flex gap-4" aria-label="Social media">
          {site.social.map((s) => (
            <li key={s.href}>
              <a href={s.href} target="_blank" rel="noopener noreferrer" className="hover:text-ink">
                {s.label}
                <span className="sr-only"> (opens in a new tab)</span>
              </a>
            </li>
          ))}
        </ul>
      </Container>
    </footer>
  );
}
