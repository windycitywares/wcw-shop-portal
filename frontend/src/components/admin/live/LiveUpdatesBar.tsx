"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Icon } from "../ui/Icon";
import { useLive, type LiveEvent } from "./LiveProvider";

/**
 * "2 new orders · Refresh" above a list (or "Changed by Sara just now · Reload" on a record) when something it shows
 * changed elsewhere. It never reloads by itself, so nobody loses their place or a half-typed edit.
 */
export function LiveUpdatesBar({
  prefixes,
  refId,
  describe,
  onRefresh,
}: {
  prefixes: string[];
  /** Only events about this record (an order page, a product page). */
  refId?: number;
  /** The words for `n` updates, e.g. n => `${n} new orders`. */
  describe: (n: number, events: LiveEvent[]) => string;
  onRefresh: () => void;
}) {
  const [pending, setPending] = useState<LiveEvent[]>([]);
  useLive(prefixes, (events) => {
    const mine = refId === undefined ? events : events.filter((e) => e.ref_id === refId);
    if (mine.length) setPending((p) => [...p, ...mine]);
  });
  if (!pending.length) return null;
  return (
    <div role="status" className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-card)] border border-accent/30 bg-accent/10 px-4 py-2.5 text-sm">
      <span className="flex items-center gap-2 font-medium">
        <Icon name="bell" className="size-4 text-accent" />
        {describe(pending.length, pending)}
      </span>
      <Button
        size="sm"
        variant="secondary"
        onClick={() => {
          setPending([]);
          onRefresh();
        }}
      >
        {refId === undefined ? "Refresh" : "Reload"}
      </Button>
    </div>
  );
}

/** "1 update" / "3 updates", or the one event's own title when there is just one. */
export const updates = (noun: string) => (n: number, events: LiveEvent[]) => (n === 1 ? events[0].title : `${n} ${noun}`);

/** For a record page: who changed it, if we know. */
export const changedBy = (what: string) => (_n: number, events: LiveEvent[]) => {
  const by = events[events.length - 1]?.actor_name;
  return `This ${what} changed${by ? ` (by ${by})` : ""} since you opened it`;
};
