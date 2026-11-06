import type { Fact, StoredFact } from "@/data/types";

export function fact(stored: StoredFact): Fact {
  const [layer, name, text] = stored;
  return { layer, name, text };
}

export function facts(table: Record<string, StoredFact>, ids: string[], where: string): Fact[] {
  return ids.map((id) => {
    const stored = table[id];
    if (!stored) throw new Error(`${where}: missing fact ${id}`);
    return fact(stored);
  });
}

/** Events, modifiers and requirements rank a path; availability, limits and untyped text do not. */
export function ranks(f: Fact): boolean {
  return f.layer === "ev" || f.layer === "mod" || f.layer === "req";
}
