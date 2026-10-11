import Link from "next/link";
import { getCategoryTree, getProducts } from "@/lib/api";
import { site } from "@/lib/site";
import { ButtonLink } from "@/components/ui/Button";
import { Container, EmptyState } from "@/components/ui/misc";
import { ProductGrid } from "@/components/catalog/ProductCard";

export const revalidate = 300;

export default async function HomePage() {
  const [tree, latest] = await Promise.all([
    getCategoryTree(),
    getProducts({ sort: "newest", page_size: "8" }),
  ]);

  return (
    <>
      <section className="border-b border-line bg-sand/50">
        <Container className="grid items-center gap-10 py-16 sm:py-24 lg:grid-cols-[1.2fr_1fr]">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-accent">{site.name}</p>
            <h1 className="mt-4 text-5xl leading-[1.05] sm:text-6xl lg:text-7xl">
              Made with care.
              <br />
              <span className="italic text-accent">Built to last.</span>
            </h1>
            <p className="mt-6 max-w-lg text-lg text-muted">{site.tagline}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <ButtonLink href="/shop" size="lg">
                Shop the collection
              </ButtonLink>
              {tree[0] && (
                <ButtonLink href={`/category/${tree[0].slug}`} variant="secondary" size="lg">
                  Explore {tree[0].name}
                </ButtonLink>
              )}
            </div>
          </div>
          <div aria-hidden="true" className="relative hidden aspect-square lg:block">
            <div className="absolute inset-6 rounded-full bg-accent-soft" />
            <div className="absolute inset-16 rounded-full border border-accent/30" />
            <div className="absolute inset-0 grid place-items-center">
              <span className="font-serif text-8xl italic text-accent/80">W</span>
            </div>
          </div>
        </Container>
      </section>

      {tree.length > 0 && (
        <section aria-labelledby="categories-heading">
          <Container className="py-16">
            <h2 id="categories-heading" className="text-3xl sm:text-4xl">
              Shop by category
            </h2>
            <ul className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-4">
              {tree.slice(0, 8).map((c) => (
                <li key={c.id}>
                  <Link
                    href={`/category/${c.slug}`}
                    className="group flex aspect-[4/3] flex-col justify-end rounded-[var(--radius-card)] border border-line bg-surface p-5 transition-colors hover:border-accent"
                  >
                    <span className="font-serif text-2xl group-hover:text-accent">{c.name}</span>
                    <span className="mt-1 text-sm text-muted">
                      {c.children.length > 0 ? `${c.children.length} collections` : "Browse"}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </Container>
        </section>
      )}

      <section aria-labelledby="new-heading">
        <Container className="py-8">
          <div className="flex items-end justify-between gap-4">
            <h2 id="new-heading" className="text-3xl sm:text-4xl">
              New arrivals
            </h2>
            <Link href="/shop?sort=newest" className="text-sm font-medium text-accent underline-offset-4 hover:underline">
              View all
            </Link>
          </div>
          <div className="mt-8">
            {latest.items.length ? (
              <ProductGrid products={latest.items} priorityCount={4} />
            ) : (
              <EmptyState title="Products are on their way">Check back soon.</EmptyState>
            )}
          </div>
        </Container>
      </section>

      <section aria-labelledby="etsy-heading">
        <Container className="py-16">
          <div className="flex flex-col items-start justify-between gap-6 rounded-[var(--radius-card)] bg-accent px-8 py-10 text-white sm:flex-row sm:items-center">
            <div>
              <h2 id="etsy-heading" className="text-3xl">
                Also on Etsy
              </h2>
              <p className="mt-2 text-white/80">Prefer to shop there? Find us on Etsy.</p>
            </div>
            <a
              href={site.social[0].href}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-11 items-center rounded-full bg-white px-6 text-sm font-medium text-accent hover:bg-canvas"
            >
              Visit our Etsy shop<span className="sr-only"> (opens in a new tab)</span>
            </a>
          </div>
        </Container>
      </section>
    </>
  );
}
