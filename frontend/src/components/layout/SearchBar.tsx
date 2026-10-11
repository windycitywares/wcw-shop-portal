import { cn } from "@/lib/utils";

/** Plain GET form: works without JavaScript and is indexable-friendly. */
export function SearchBar({
  className,
  defaultValue,
  id = "site-search",
}: {
  className?: string;
  defaultValue?: string;
  id?: string;
}) {
  return (
    <form action="/search" method="get" role="search" className={cn("relative", className)}>
      <label htmlFor={id} className="sr-only">
        Search products
      </label>
      <input
        id={id}
        name="q"
        type="search"
        defaultValue={defaultValue}
        placeholder="Search the shop"
        autoComplete="off"
        className="h-10 w-full rounded-full border border-line bg-surface pl-4 pr-11 text-sm placeholder:text-muted/80 focus-visible:border-accent"
      />
      <button
        type="submit"
        className="absolute right-1 top-1 grid size-8 place-items-center rounded-full text-muted hover:bg-sand hover:text-ink"
      >
        <svg aria-hidden="true" viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" strokeLinecap="round" />
        </svg>
        <span className="sr-only">Search</span>
      </button>
    </form>
  );
}
