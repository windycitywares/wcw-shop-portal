"use client";

import { useEffect } from "react";
import { track } from "@/lib/analytics";

type Props =
  | { type: "product_view"; productId: number; value?: number }
  | { type: "search"; q: string; results: number }
  | { type: "view_cart" | "begin_checkout"; value?: number };

/** Records one event when a page is shown (no-op without consent). Renders nothing. */
export function TrackOnView(props: Props) {
  const key = JSON.stringify(props);
  useEffect(() => {
    if (props.type === "product_view") track("product_view", { product_id: props.productId, value: props.value });
    else if (props.type === "search") track("search", { data: { q: props.q, results: props.results } });
    else track(props.type, { value: props.value });
    // One event per distinct page (key), not per render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return null;
}
