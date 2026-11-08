import type { Segment } from "@/data/types";

// Teams and queries arrive as untyped JSON; these helpers apply the Python rules the ported
// checks were written against (dict, int and truthiness differ from their JavaScript meaning).

export type Dict = Record<string, unknown>;

export function isDict(value: unknown): value is Dict {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isInt(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value);
}

export function truthy(value: unknown): boolean {
  if (Array.isArray(value)) return value.length > 0;
  if (isDict(value)) return Object.keys(value).length > 0;
  return Boolean(value);
}

/** dict.get(key, fallback): a present key wins even when its value is null. */
export function get(value: Dict, key: string, fallback?: unknown): unknown {
  return Object.hasOwn(value, key) ? value[key] : fallback;
}

export function unique<T>(values: Iterable<T>): T[] {
  return [...new Set(values)];
}

/** Lowercase, with the curly apostrophe some names use read as a straight one; the pack's text is otherwise ASCII apart from `·`. */
export function fold(text: string): string {
  return text.replaceAll("’", "'").toLowerCase();
}

/** Runs of letters and digits; every Han character is a word of its own. */
export function words(text: string): string[] {
  return text.match(/\p{Script=Han}|(?:(?!\p{Script=Han})[\p{L}\p{N}])+/gu) ?? [];
}

/** Runs of consecutive Han characters; typed text reads each one as a phrase. */
export function hanRuns(text: string): string[] {
  return text.match(/\p{Script=Han}+/gu) ?? [];
}

/** Every term begins some word of `have`; true without terms. */
export function prefixed(have: readonly string[], terms: readonly string[]): boolean {
  return terms.every((term) => have.some((word) => word.startsWith(term)));
}

/** Whether `text` has every word of `q` as a word prefix and every Han run of `q` unbroken. */
export function matchesText(text: string, q: string): boolean {
  const folded = fold(text);
  return prefixed(words(folded), words(fold(q))) && hanRuns(q).every((run) => folded.includes(run));
}

/** Python string order (code points), for sort keys. */
export function compareText(a: string, b: string): number {
  if (a === b) return 0;
  const left = [...a];
  const right = [...b];
  for (let i = 0; i < Math.min(left.length, right.length); i++) {
    const diff = left[i]!.codePointAt(0)! - right[i]!.codePointAt(0)!;
    if (diff) return diff;
  }
  return left.length - right.length;
}

/** str(value) for the JSON values a team name or note can hold. */
export function pyStr(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "None";
  if (typeof value === "boolean") return value ? "True" : "False";
  return typeof value === "number" ? String(value) : JSON.stringify(value);
}

export function slicePoints(text: string, length: number): string {
  return [...text].slice(0, length).join("");
}

export function joinSegments(segments: Segment[]): string {
  return segments.map((part) => part.text).join("");
}

/** A random id. `crypto.randomUUID` exists only in secure contexts, and the planner is also opened over plain HTTP on a local network. */
export function newUid(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6]! & 0x0f) | 0x40;
  bytes[8] = (bytes[8]! & 0x3f) | 0x80;
  const hex = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
