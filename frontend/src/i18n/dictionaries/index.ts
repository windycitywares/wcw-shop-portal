import type { Locale } from "../config";
import en, { type Dictionary } from "./en";
import es from "./es";
import nl from "./nl";

const dictionaries: Record<Locale, Dictionary> = { en, es, nl };

export function getDictionary(locale: Locale): Dictionary {
  return dictionaries[locale] ?? en;
}

export type { Dictionary };
