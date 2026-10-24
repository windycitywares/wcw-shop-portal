"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

/** A round arrow that appears once you have scrolled a screen down and takes you back to the top. */
export function BackToTop({ label = "Back to top", className }: { label?: string; className?: string }) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      setShow(window.scrollY > window.innerHeight * 0.8);
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  /** Glides up with an ease-out curve (about 0.5-1.2 s depending on distance) instead of jumping. */
  function toTop() {
    const start = window.scrollY;
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const done = () => (document.getElementById("main") ?? document.getElementById("admin-main"))?.focus({ preventScroll: true });
    if (calm || start < 2) {
      window.scrollTo(0, 0);
      done();
      return;
    }
    const duration = Math.min(1200, Math.max(500, start * 0.35));
    const t0 = performance.now();
    const root = document.documentElement;
    const before = root.style.scrollBehavior;
    root.style.scrollBehavior = "auto"; // a CSS smooth value would fight the frame-by-frame steps
    const step = (now: number) => {
      const p = Math.min(1, (now - t0) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      window.scrollTo(0, start * (1 - eased));
      if (p < 1) requestAnimationFrame(step);
      else {
        root.style.scrollBehavior = before;
        done();
      }
    };
    requestAnimationFrame(step);
  }

  return (
    <button
      type="button"
      onClick={toTop}
      aria-label={label}
      title={label}
      tabIndex={show ? 0 : -1}
      aria-hidden={!show}
      className={cn(
        "fixed right-3 top-1/2 z-40 -mt-[1.375rem] grid size-11 place-items-center rounded-full bg-night text-white shadow-lg transition-all duration-200 hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 motion-reduce:transition-none sm:right-5",
        show ? "translate-x-0 opacity-100" : "pointer-events-none translate-x-3 opacity-0",
        className,
      )}
    >
      <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 19V5M5 12l7-7 7 7" />
      </svg>
    </button>
  );
}
