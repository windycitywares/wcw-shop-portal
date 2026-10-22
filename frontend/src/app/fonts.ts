import { Figtree, Open_Sans, Quicksand, Spectral } from "next/font/google";

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

/** Admin only: Quicksand for headings and the menu, Open Sans for text (a clean dashboard look). */
export const adminDisplay = Quicksand({
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-admin-display",
  display: "swap",
});

export const adminBody = Open_Sans({
  subsets: ["latin", "latin-ext"],
  variable: "--font-admin-body",
  display: "swap",
});
