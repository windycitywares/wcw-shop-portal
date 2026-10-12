import type { Dictionary } from "./dictionaries";

/** Translate a stored detail name ("Finish") or value ("High-gloss enamel"); unknown ones pass through. */
export function attrKey(t: Dictionary, key: string): string {
  return t.attributes.keys[key] ?? key;
}

export function attrValue(t: Dictionary, value: string): string {
  return t.attributes.values[value] ?? value;
}
