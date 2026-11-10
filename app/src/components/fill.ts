import type { SynergyItem } from "@/data";
import { compareText } from "@/domain/values";
import type { Hit } from "./presentation";

/**
 * The most one tray item adds to a suggestion: one link through a point twenty objects share.
 * Links through rarer points, such as one minion's, would otherwise let a single tray item fill
 * the top of the list ahead of suggestions that connect several tray items.
 */
export const SEED_CAP = 1 / 20;

/** A tray item with the Synergies of the trait or rules it brings. */
export interface Seed {
  id: string;
  name: string;
  items: SynergyItem[];
}

/** What one tray item adds to a suggestion. */
export interface Link {
  seed: { id: string; name: string };
  weight: number;
}

export interface Suggestion {
  id: string;
  name: string;
  kind: string;
  image?: string;
  classification?: SynergyItem["classification"];
  score: number;
  links: Link[];
  hits: Hit[];
}

/**
 * Objects linked to the tray, scored by the resource allocation index: each point a suggestion
 * shares with a tray item adds 1 / its degree, so points many objects meet on count for little.
 * Points are counted per event, so the same trigger reached through several relations adds once.
 */
export function suggestions(seeds: Seed[], excluded: (id: string) => boolean): Suggestion[] {
  const found = new Map<string, Suggestion>();
  const hitKeys = new Map<string, Set<string>>();
  const verdicts = new Map<string, boolean>();
  const isExcluded = (id: string) => {
    if (!verdicts.has(id)) verdicts.set(id, excluded(id));
    return verdicts.get(id);
  };
  for (const seed of seeds) {
    const reached = new Map<string, Map<string, number>>();
    for (const item of seed.items) {
      if (isExcluded(item.id)) continue;
      let suggestion = found.get(item.id);
      if (!suggestion) {
        suggestion = {
          id: item.id,
          name: item.name ?? item.id,
          kind: item.kind ?? "",
          image: item.image,
          classification: item.classification,
          score: 0,
          links: [],
          hits: [],
        };
        found.set(item.id, suggestion);
        hitKeys.set(item.id, new Set());
      }
      const hit: Hit = {
        entity_id: item.id,
        reference: item.target_rule.reference || item.id,
        rank: item.target_rule.rank,
      };
      const hitKey = JSON.stringify(hit);
      if (!hitKeys.get(item.id)!.has(hitKey)) {
        hitKeys.get(item.id)!.add(hitKey);
        suggestion.hits.push(hit);
      }
      // One event reached through several relations counts once, through its rarest point.
      const events = reached.get(item.id) ?? new Map();
      reached.set(item.id, events);
      const weight = 1 / item.point.degree;
      if (weight > (events.get(item.point.event) ?? 0)) events.set(item.point.event, weight);
    }
    for (const [id, events] of reached) {
      const total = [...events.values()].reduce((sum, weight) => sum + weight, 0);
      const weight = Math.min(SEED_CAP, total);
      const suggestion = found.get(id)!;
      suggestion.links.push({ seed: { id: seed.id, name: seed.name }, weight });
      suggestion.score += weight;
    }
  }
  const ranked = [...found.values()];
  for (const suggestion of ranked) suggestion.links.sort((a, b) => b.weight - a.weight);
  return ranked.sort(
    (a, b) => b.score - a.score || b.links.length - a.links.length || compareText(a.name, b.name),
  );
}
