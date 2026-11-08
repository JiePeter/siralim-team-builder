import type { Segment, SynergyItem } from "@/data";
import { ranks } from "@/domain/facts";
import { t } from "@/i18n";
import { compareText, fold, matchesText, words } from "@/domain/values";
import { kindGroup, kindGroups, type Hit } from "./presentation";

const MECHANISMS = {
  "Event chain": "eventChain",
  "Status condition": "statusCondition",
  "Action modifier": "actionModifier",
  "Event count": "eventCount",
  Amplification: "amplification",
  "Minion support": "minionSupport",
  "Scope overlap": "scopeOverlap",
};

export const pairingMechanisms: Record<string, string> = Object.fromEntries(
  Object.entries(MECHANISMS).map(([relation, key]) => [relation, t(`synergy.mechanisms.${key}`)]),
);

/** One object that pairs with the owner, with every rule path that connects them. */
export interface Candidate {
  id: string;
  name: string;
  kind: string;
  image?: string;
  classification?: SynergyItem["classification"];
  paths: SynergyItem[];
}

export interface Card extends Omit<Candidate, "paths"> {
  /** The owner's Perk or rank the shown connection comes from. */
  source: { perk?: string; rank?: number };
  facts: string[];
  effect: string;
  effectSegments: Segment[];
  hits: Hit[];
}

export function mechanismMatches(path: SynergyItem, value = ""): boolean {
  return value ? path.relation === value : path.relation in pairingMechanisms;
}

function pathScore(item: SynergyItem): number {
  return (
    (item.strength === "context" || item.relation === "Scope overlap" ? 10000 : 0) +
    (item.witness?.requires_target_side ? 1000 : 0) +
    (item.strength === "conditional" ? 200 : 0) +
    (item.shared_constraints?.filter(ranks).length || 0) +
    (item.target_rule?.conditions?.filter(ranks).length || 0)
  );
}

function hitOf(path: SynergyItem): Hit {
  return {
    entity_id: path.id,
    reference: path.target_rule.reference || path.id,
    rank: path.target_rule.rank,
  };
}

function explanation(
  paths: SynergyItem[],
): Pick<Card, "source" | "facts" | "effect" | "effectSegments"> {
  const best = [...paths].sort((a, b) => pathScore(a) - pathScore(b))[0]!;
  const normalized = (text: string) => words(fold(text)).join(" ");
  const body = normalized(best.target_rule.text);
  const facts = [
    ...(best.shared_constraints || []),
    ...(best.witness?.requirements || []),
    ...(best.target_rule.conditions || []),
  ]
    .map((f) => f.text)
    .filter((f) => !body.includes(normalized(f)));
  return {
    source: { perk: best.source_perk, rank: best.source_rank },
    facts: [...new Set(facts)],
    effect: best.target_rule.text,
    effectSegments: best.target_rule.segments,
  };
}

export function candidates(items: SynergyItem[]): Candidate[] {
  const unique = new Map<string, Candidate>();
  for (const item of items) {
    if (!unique.has(item.id))
      unique.set(item.id, {
        id: item.id,
        name: item.name ?? item.id,
        kind: item.kind ?? "",
        image: item.image,
        classification: item.classification,
        paths: [],
      });
    unique.get(item.id)!.paths.push(item);
  }
  return [...unique.values()];
}

/** Candidates whose name or connecting rule text matches the keyword. */
export function matching(items: Candidate[], keyword: string): Candidate[] {
  return items.filter((item) =>
    matchesText([item.name, ...item.paths.map((p) => p.target_rule.text)].join(" "), keyword),
  );
}

export interface Group {
  value: string;
  label: string;
  count: number;
}

/** The type buttons, then the relationship buttons available within the chosen type. */
export function categories(items: Candidate[], kind: string | null, mechanism: string) {
  const available = items.filter((item) =>
    item.paths.some((path) => path.relation in pairingMechanisms),
  );
  const kinds: Group[] = kindGroups
    .map(({ value, label }) => ({
      value,
      label,
      count: available.filter((i) => kindGroup(i.kind) === value).length,
    }))
    .filter((g) => g.count);
  const chosenKind = kinds.some((g) => g.value === kind) ? kind : (kinds[0]?.value ?? null);
  const typed = available.filter((item) => kindGroup(item.kind) === chosenKind);
  const mechanisms: Group[] = [
    { value: "", label: t("synergy.all"), count: typed.length },
    ...Object.entries(pairingMechanisms)
      .map(([value, label]) => ({
        value,
        label,
        count: typed.filter((item) => item.paths.some((path) => mechanismMatches(path, value)))
          .length,
      }))
      .filter((g) => g.count),
  ];
  const chosenMechanism = mechanisms.some((g) => g.value === mechanism) ? mechanism : "";
  return { kinds, kind: chosenKind, mechanisms, mechanism: chosenMechanism };
}

/** Cards of one type and relationship, the most direct connections first. */
export function cards(items: Candidate[], kind: string | null, mechanism: string): Card[] {
  return items
    .flatMap((item) => {
      if (kindGroup(item.kind) !== kind) return [];
      const paths = item.paths.filter((p) => mechanismMatches(p, mechanism));
      if (!paths.length) return [];
      const { id, name, kind: itemKind, image, classification } = item;
      const card: Card = {
        id,
        name,
        kind: itemKind,
        image,
        classification,
        ...explanation(paths),
        hits: paths.map(hitOf),
      };
      return [{ card, score: Math.min(...paths.map(pathScore)) }];
    })
    .sort((a, b) => a.score - b.score || compareText(a.card.name, b.card.name))
    .map(({ card }) => card);
}
