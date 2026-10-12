import { Figtree, Spectral } from "next/font/google";

/** Headings: Spectral (light, bookish serif). Text and UI: Figtree. */
export const display = Spectral({
  subsets: ["latin", "latin-ext"],
  weight: ["300", "400", "500"],
  style: ["normal", "italic"],
  variable: "--font-display",
  display: "swap",
});

export const body = Figtree({
  subsets: ["latin", "latin-ext"],
  variable: "--font-body",
  display: "swap",
});
