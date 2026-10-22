"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useI18n } from "@/i18n/client";
import { useAuth } from "@/lib/auth";
import { ApiRequestError } from "@/lib/client-api";
import { reviewsApi, type Review, type ReviewPage, type ReviewSort } from "@/lib/engagement";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Stars } from "@/components/ui/Stars";
import { Alert } from "@/components/ui/misc";

const SORTS: ReviewSort[] = ["helpful", "newest", "highest", "lowest"];

/** Product reviews: summary, the list (approved reviews only), helpful votes, and the form for shoppers. */
export function Reviews({ slug }: { slug: string }) {
  const { t, fmt, locale, href } = useI18n();
  const { user } = useAuth();
  const pathname = usePathname();
  const [sort, setSort] = useState<ReviewSort>("helpful");
  const [data, setData] = useState<ReviewPage | null>(null);
  const [items, setItems] = useState<Review[]>([]);
  const [page, setPage] = useState(1);
  const [thanks, setThanks] = useState<string | null>(null);

  const load = useCallback(
    async (nextSort: ReviewSort, nextPage: number) => {
      try {
        const res = await reviewsApi.list(slug, nextSort, nextPage);
        setData(res);
        setItems((prev) => (nextPage === 1 ? res.items : [...prev, ...res.items]));
        setPage(nextPage);
      } catch {
        setData((d) => d ?? { summary: { average: 0, count: 0, distribution: {} }, items: [], total: 0, page: 1, page_size: 5, can_review: false, purchased: false, reviewed: false });
      }
    },
    [slug],
  );

  useEffect(() => {
    load(sort, 1);
    // Reload when signing in or out (can_review and "helpful by me" depend on the viewer).
  }, [load, sort, user]);

  const summary = data?.summary;
  const count = summary?.count ?? 0;

  async function vote(review: Review) {
    try {
      const updated = await reviewsApi.helpful(review.id);
      setItems((list) => list.map((r) => (r.id === updated.id ? updated : r)));
    } catch {
      /* own review or signed out: the button is hidden in those cases */
    }
  }

  return (
    <section id="reviews" aria-labelledby="reviews-heading" className="mt-28 scroll-mt-24 border-t border-line pt-16">
      <div className="grid gap-12 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <div>
          <h2 id="reviews-heading" className="text-4xl">
            {t.reviews.title}
          </h2>
          {count > 0 && summary ? (
            <div className="mt-6">
              <p className="font-serif text-5xl font-light">{summary.average.toFixed(1)}</p>
              <Stars rating={summary.average} label={fmt(t.reviews.average, { rating: summary.average.toFixed(1) })} className="mt-2 text-lg" />
              <p className="mt-1 text-sm text-muted">{count === 1 ? t.reviews.basedOnOne : fmt(t.reviews.basedOn, { count })}</p>
              <ul className="mt-5 space-y-1.5 text-sm">
                {[5, 4, 3, 2, 1].map((stars) => {
                  const n = summary.distribution[String(stars)] ?? 0;
                  return (
                    <li key={stars} className="flex items-center gap-3">
                      <span className="w-6 tabular-nums text-muted" aria-hidden="true">
                        {stars}★
                      </span>
                      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-sand" aria-hidden="true">
                        <span className="block h-full rounded-full bg-accent" style={{ width: `${count ? (n / count) * 100 : 0}%` }} />
                      </span>
                      <span className="w-6 text-right tabular-nums text-muted" aria-hidden="true">
                        {n}
                      </span>
                      <span className="sr-only">{fmt(t.reviews.starsRow, { stars, count: n })}</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : (
            data && <p className="mt-4 text-muted">{t.reviews.none}</p>
          )}

          <div className="mt-8">
            {thanks ? (
              <Alert tone="success">{thanks}</Alert>
            ) : !user ? (
              <Link href={`${href("/login")}?next=${encodeURIComponent(`${pathname}#reviews`)}`} className="text-sm underline">
                {t.reviews.signIn}
              </Link>
            ) : data?.can_review ? (
              <ReviewForm
                slug={slug}
                locale={locale}
                onDone={(status) => {
                  setThanks(status === "approved" ? t.reviews.thanksLive : t.reviews.thanksPending);
                  load(sort, 1);
                }}
              />
            ) : data ? (
              <p className="text-sm text-muted">{data.reviewed ? t.reviews.already : t.reviews.afterDelivery}</p>
            ) : null}
            {count === 0 && <p className="mt-3 text-sm text-muted">{t.reviews.beFirst}</p>}
          </div>
        </div>

        <div>
          {items.length > 0 && (
            <div className="mb-6 flex justify-end">
              <label className="flex items-center gap-2 text-sm">
                <span className="text-muted">{t.reviews.sort}</span>
                <Select value={sort} onChange={(e) => setSort(e.target.value as ReviewSort)} className="w-auto">
                  {SORTS.map((s) => (
                    <option key={s} value={s}>
                      {t.reviews.sorts[s]}
                    </option>
                  ))}
                </Select>
              </label>
            </div>
          )}
          <ul className="divide-y divide-line">
            {items.map((r) => (
              <li key={r.id} className="py-6">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <Stars rating={r.rating} label={fmt(t.reviews.ratingOption, { count: r.rating })} />
                  {r.title && <p className="font-medium">{r.title}</p>}
                </div>
                <p className="mt-1 text-sm text-muted">
                  {r.author_name} · {new Date(r.created_at).toLocaleDateString(locale, { year: "numeric", month: "long", day: "numeric" })}
                  {r.verified && <span className="ml-2 text-success">✓ {t.reviews.verified}</span>}
                </p>
                <p className="mt-3 whitespace-pre-line leading-relaxed">{r.body}</p>
                {r.reply && (
                  <div className="mt-4 rounded-[var(--radius-card)] bg-sand px-4 py-3 text-sm">
                    <p className="font-medium">{t.reviews.reply}</p>
                    <p className="mt-1 whitespace-pre-line">{r.reply}</p>
                  </div>
                )}
                {user && (
                  <button
                    type="button"
                    aria-pressed={r.helpful_by_me}
                    onClick={() => vote(r)}
                    className={cn("mt-3 text-xs underline", r.helpful_by_me ? "text-accent" : "text-muted hover:text-ink")}
                  >
                    {fmt(t.reviews.helpful, { count: r.helpful_count })}
                    <span className="sr-only"> {t.reviews.markHelpful}</span>
                  </button>
                )}
                {!user && r.helpful_count > 0 && <p className="mt-3 text-xs text-muted">{fmt(t.reviews.helpful, { count: r.helpful_count })}</p>}
              </li>
            ))}
          </ul>
          {data && items.length < data.total && (
            <Button variant="secondary" className="mt-6" onClick={() => load(sort, page + 1)}>
              {t.reviews.more}
            </Button>
          )}
        </div>
      </div>
    </section>
  );
}

function ReviewForm({ slug, locale, onDone }: { slug: string; locale: string; onDone: (status: "pending" | "approved") => void }) {
  const { t, fmt } = useI18n();
  const [rating, setRating] = useState(0);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [state, setState] = useState<"idle" | "sending">("idle");
  const [problem, setProblem] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      <p className="font-serif text-xl">{t.reviews.write}</p>
      <fieldset>
        <legend className="mb-1.5 text-sm font-medium">{t.reviews.rating}</legend>
        <div className="flex gap-1">
          {[1, 2, 3, 4, 5].map((n) => (
            <label key={n} className="cursor-pointer has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent">
              <input type="radio" name="review-rating" value={n} checked={rating === n} onChange={() => setRating(n)} className="sr-only" />
              <span aria-hidden="true" className={cn("text-2xl leading-none", n <= rating ? "text-accent" : "text-line")}>
                ★
              </span>
              <span className="sr-only">{fmt(t.reviews.ratingOption, { count: n })}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <Field label={`${t.reviews.titleLabel} ${t.addresses.optional}`}>
        {(p) => <Input {...p} maxLength={160} value={title} onChange={(e) => setTitle(e.target.value)} />}
      </Field>
      <Field label={t.reviews.body} hint={t.reviews.bodyHint}>
        {(p) => <Textarea {...p} maxLength={4000} value={body} onChange={(e) => setBody(e.target.value)} />}
      </Field>
      {problem && <Alert tone="danger">{problem}</Alert>}
      <Button
        type="button"
        disabled={state === "sending" || body.trim().length < 10}
        onClick={async () => {
          if (!rating) {
            setProblem(t.reviews.chooseRating);
            return;
          }
          setState("sending");
          setProblem(null);
          try {
            const res = await reviewsApi.submit(slug, { rating, title: title.trim() || null, body: body.trim(), locale });
            onDone(res.status);
          } catch (err) {
            setProblem(err instanceof ApiRequestError ? err.message : t.auth.error);
            setState("idle");
          }
        }}
      >
        {state === "sending" ? t.reviews.submitting : t.reviews.submit}
      </Button>
    </div>
  );
}
