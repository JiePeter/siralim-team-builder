import type {
  Attrs,
  Classification,
  Discovery,
  DiscoveryGroup,
  DiscoveryMember,
  Effect,
  Feature,
  SearchDocument,
} from "@/data/types";
import {
  applicable,
  attributeFacets,
  hasAttributes,
  type AttributeFacet,
  type Attributes,
} from "./attributes";
import { compareText, fold, get, isDict, prefixed, unique, words } from "./values";

export type Scope = "action" | "rule" | "component";

export interface Condition {
  category: string;
  relation: string;
  value: string;
}

type Unit = Feature[];

interface Descriptor {
  entity_id: string;
  rank: number | null;
  reference: string;
  rule: number;
  action: number;
  unit: Unit;
}

type Member = DiscoveryMember;

interface Group {
  entity: Member;
  members: Member[];
  names: Set<string>;
  words: string[];
  kinds: Set<string>;
  action: Unit[];
  rule: Unit[];
  component: Unit[];
  descriptors: Descriptor[];
}

/** discovery.json with its interned features expanded; build once per data pack. */
export interface DiscoveryIndex {
  pack: Discovery;
  groups: Group[];
  canonical: Map<string, string>;
  aliases: Map<string, string>;
  unoffered: { relations: Set<string>; values: Set<string> };
}

const pair = (category: string, value: string) => `${category}\u0000${value}`;

const aliases = (group: DiscoveryGroup) => group.members.flatMap((m) => m.aliases ?? []);

/** MiniSearch documents: each group under its own name, then the references by name only. */
export function searchDocuments(pack: Discovery): SearchDocument[] {
  return [
    ...pack.groups.map((group) => {
      const entity = group.members.find((m) => m.id === group.id)!;
      return {
        id: group.id,
        name: entity.name,
        kind: entity.kind,
        members: [...group.members.map((m) => m.name), ...aliases(group)].join(" "),
        text: entity.description,
        locations: group.locations.join(" "),
      };
    }),
    ...pack.references.map(({ id, name, kind }) => ({
      id,
      name,
      kind,
      members: "",
      text: "",
      locations: "",
    })),
  ];
}

export function discoveryIndex(pack: Discovery): DiscoveryIndex {
  const expand = (unit: number[]): Unit => unit.map((i) => pack.features[i]!);
  const canonical = new Map<string, string>();
  const groups = pack.groups.map((group) => {
    for (const member of group.members) canonical.set(member.id, group.id);
    const action = group.action.map(expand);
    const entity = group.members.find((m) => m.id === group.id)!;
    const names = [...group.members.map((m) => m.name), ...aliases(group)];
    return {
      entity,
      members: group.members,
      names: new Set(names.map(fold)),
      words: unique(
        words(fold([entity.name, entity.description, ...names, ...group.locations].join(" "))),
      ),
      kinds: new Set(group.kinds),
      action,
      rule: group.rule.map(expand),
      component: group.component.map(expand),
      descriptors: group.descriptors.map((d, i) => ({ ...d, unit: action[i]! })),
    };
  });
  const { labels } = pack;
  return {
    pack,
    groups,
    canonical,
    aliases: new Map(labels.value_aliases.map(([c, v, alias]) => [pair(c, v), alias])),
    unoffered: {
      relations: new Set(labels.unoffered_relations.map(([c, r]) => pair(c, r))),
      values: new Set(labels.unoffered_values.map(([c, v]) => pair(c, v))),
    },
  };
}

export class DiscoveryError extends Error {}

function fail(message: string): never {
  throw new DiscoveryError(message);
}

const CONDITION_KEYS = ["category", "relation", "value"];

export const MAX_FILTERS = 8;

const RESULT_LIMIT = 60;

export const blankCondition = (): Condition => ({ category: "", relation: "", value: "" });

/** Check mechanic filters and resolve value aliases; throws DiscoveryError with the message to show. */
export function validateConditions(
  index: DiscoveryIndex,
  conditions: unknown,
  scope: unknown,
): Condition[] {
  const { categories, relations } = index.pack.labels;
  if (scope !== "action" && scope !== "rule" && scope !== "component") fail("Invalid match scope");
  if (!Array.isArray(conditions) || conditions.length > MAX_FILTERS) {
    fail("At most eight mechanic filters");
  }
  return conditions.map((condition) => {
    if (!isDict(condition) || Object.keys(condition).some((k) => !CONDITION_KEYS.includes(k))) {
      fail("Invalid mechanic filter");
    }
    const [category, relation, value] = CONDITION_KEYS.map((k) => get(condition, k, ""));
    if (![category, relation, value].every((x) => typeof x === "string" && [...x].length <= 140)) {
      fail("Invalid mechanic filter");
    }
    const [c, r, v] = [category, relation, value] as string[];
    if (c && !Object.hasOwn(categories, c)) fail("Unknown mechanic category");
    if (r && !(Object.hasOwn(relations, c!) && Object.hasOwn(relations[c!]!, r))) {
      fail("Interaction is incompatible with the mechanic");
    }
    if (!c && (r || v)) fail("Choose a mechanic category first");
    return { category: c!, relation: r!, value: index.aliases.get(pair(c!, v!)) ?? v! };
  });
}

function matches(unit: Unit, condition: Condition): boolean {
  const { category, relation, value } = condition;
  if (!category) return true;
  return unit.some(
    ([c, r, v]) => c === category && (!relation || relation === r) && (!value || value === v),
  );
}

/** Groups whose text matches `q`: the text index's ids when given, else word prefixes. */
export function textMatches(index: DiscoveryIndex, q: string, ids?: ReadonlySet<string>): Group[] {
  const terms = words(fold(q));
  const found = terms.length ? ids : undefined;
  return index.groups.filter((group) =>
    found ? found.has(group.entity.id) : prefixed(group.words, terms),
  );
}

/** Exact name first, then an alias, then a name prefix, then the rest; each by name. */
export function rankGroups<T extends Pick<Group, "entity" | "names">>(groups: T[], q: string): T[] {
  const text = fold(q.trim());
  const rank = (group: T) => {
    const name = fold(group.entity.name);
    const priority =
      !text || name === text ? 0 : group.names.has(text) ? 1 : name.startsWith(text) ? 2 : 3;
    return { priority, name };
  };
  return groups
    .map((group) => ({ group, key: rank(group) }))
    .sort((a, b) => a.key.priority - b.key.priority || compareText(a.key.name, b.key.name))
    .map((entry) => entry.group);
}

const ofKind = (member: Member, kind: string) => member.kind === kind;

/** Whether a component is of the kind and has the attributes itself. */
export function memberWith(
  index: DiscoveryIndex,
  member: Member,
  kind: string,
  wanted: Attributes,
): boolean {
  return ofKind(member, kind) && hasAttributes(index.pack.attributes[member.id], wanted);
}

/** Whether a group has a member of the kind with the attributes; any group when none are wanted. */
export function hasMemberWith(
  index: DiscoveryIndex,
  group: Pick<Group, "members">,
  kind: string,
  wanted: Attributes,
): boolean {
  if (!Object.keys(wanted).length) return true;
  return group.members.some((m) => memberWith(index, m, kind, wanted));
}

export interface MatchedRule {
  entity_id: string;
  rank: number | null;
  reference: string;
  rule: number;
  action: number;
}

export type DiscoveryItem = Member & { matched_names: string[]; matched_rules: MatchedRule[] };

export interface Option {
  value: string;
  label: string;
  count: number;
  group?: string;
}

export interface DiscoveryResult {
  items: DiscoveryItem[];
  total: number;
  facets: {
    kinds: Option[];
    conditions: { categories: Option[]; relations: Option[]; values: Option[] }[];
    /** Attributes of the chosen kind; none without a kind. */
    attributes: AttributeFacet[];
  };
  scope: Scope;
}

export interface DiscoveryQuery {
  q?: string;
  kind?: string;
  conditions?: unknown;
  scope?: unknown;
  /** Ids a text index matched for `q`; when given, they replace the word-prefix match. */
  ids?: ReadonlySet<string>;
  /** Attributes of the chosen kind; ignored without a kind. */
  attributes?: Attributes;
}

/** A `cards/<kind>.json` entry. */
export interface CardFields {
  effects: Effect[];
  facts: string[];
  attrs: Attrs;
  classification?: Classification[];
}

export function withCard<T extends DiscoveryItem>(item: T, card: CardFields) {
  return {
    ...item,
    effects: card.effects,
    facts: card.facts,
    attrs: card.attrs,
    classification: card.classification ?? [],
  };
}

const GROUP_ORDER: Record<string, number> = { Category: 0, Buff: 1, Debuff: 2, General: 3 };

function options(
  index: DiscoveryIndex,
  category: string,
  counts: Map<string, Set<string>>,
  relations: boolean,
  selected: string,
): Option[] {
  const { labels, status_kinds } = index.pack;
  const unoffered = relations ? index.unoffered.relations : index.unoffered.values;
  const result: Required<Option>[] = [];
  for (const [value, ids] of counts) {
    if (unoffered.has(pair(category, value)) && value !== selected) continue;
    let group = "";
    if (category === "status" && !relations) {
      const kind = Object.hasOwn(status_kinds, value) ? status_kinds[value] : undefined;
      group = value.startsWith("@")
        ? "Category"
        : kind === "buff"
          ? "Buff"
          : kind === "debuff"
            ? "Debuff"
            : "General";
    }
    const table = relations ? labels.relations[category] : labels.values[category];
    const label = table && Object.hasOwn(table, value) ? table[value]! : value;
    result.push({ value, label, count: ids.size, group });
  }
  return result.sort(
    (a, b) =>
      (GROUP_ORDER[a.group] ?? 0) - (GROUP_ORDER[b.group] ?? 0) ||
      compareText(fold(a.label), fold(b.label)),
  );
}

function addTo(table: Map<string, Set<string>>, key: string, id: string) {
  let ids = table.get(key);
  if (!ids) table.set(key, (ids = new Set()));
  ids.add(id);
}

/**
 * Components matching name words (prefix per word), a kind and mechanic filters, with the
 * facet counts for refining each filter. Card fields are joined separately from cards/.
 */
export function query(index: DiscoveryIndex, input: DiscoveryQuery = {}): DiscoveryResult {
  const { labels, references } = index.pack;
  const q = (input.q ?? "").replaceAll("’", "'");
  const kind = input.kind ?? "";
  const scope = (input.scope ?? "action") as Scope;
  const conditions = validateConditions(index, input.conditions ?? [], scope);
  const active = conditions.filter((c) => c.category);
  const terms = words(fold(q));
  const text = fold(q.trim());
  const found = terms.length ? input.ids : undefined;
  const wanted = applicable(kind, input.attributes ?? {});
  const candidates = textMatches(index, q, input.ids);
  const accepted = (group: Group, filters: Condition[]) => {
    const on = filters.filter((c) => c.category);
    return !on.length || group[scope].some((unit) => on.every((c) => matches(unit, c)));
  };
  const narrowed = candidates.filter(
    (g) => (!kind || g.kinds.has(kind)) && accepted(g, conditions),
  );
  const selected: Group[] = narrowed.filter((g) => hasMemberWith(index, g, kind, wanted));
  if (terms.length && !kind && !active.length) {
    for (const item of references) {
      if (found ? found.has(item.id) : prefixed(words(fold(item.name)), terms)) {
        selected.push({
          entity: item,
          members: [item],
          names: new Set([fold(item.name)]),
          words: [],
          kinds: new Set(),
          action: [],
          rule: [],
          component: [],
          descriptors: [],
        });
      }
    }
  }
  const ranked = rankGroups(selected, q);

  const items = ranked.slice(0, RESULT_LIMIT).map((group): DiscoveryItem => {
    const fits = (m: Member) => memberWith(index, m, kind, wanted);
    const exact = group.members.find((m) => fold(m.name) === text && (!kind || fits(m)));
    const explicit = group.members.find(fits);
    const named = group.members.find(
      (m) =>
        ["creature", "material"].includes(m.kind) &&
        terms.length > 0 &&
        prefixed(words(fold(m.name)), terms),
    );
    const item = { ...(exact ?? explicit ?? named ?? group.entity) };
    const names = group.members
      .filter((m) => m.name !== item.name)
      .filter(
        (m) =>
          !terms.length ||
          prefixed(words(fold(m.name)), terms) ||
          kind === "creature" ||
          kind === "material",
      )
      .map((m) => m.name);
    const { descriptors } = group;
    let evidence: Descriptor[];
    if (scope === "rule") {
      const grouped = new Map<string, Unit>();
      for (const d of descriptors) {
        const key = JSON.stringify([d.reference, d.rule]);
        grouped.set(key, [...(grouped.get(key) ?? []), ...d.unit]);
      }
      const valid = new Set(
        [...grouped].filter(([, unit]) => active.every((c) => matches(unit, c))).map(([k]) => k),
      );
      evidence = descriptors.filter(
        (d) =>
          valid.has(JSON.stringify([d.reference, d.rule])) &&
          active.some((c) => matches(d.unit, c)),
      );
    } else if (scope === "component") {
      evidence = descriptors.filter((d) => active.some((c) => matches(d.unit, c)));
    } else {
      evidence = descriptors.filter(
        (d) => active.length > 0 && active.every((c) => matches(d.unit, c)),
      );
    }
    return {
      ...item,
      matched_names: unique(names),
      matched_rules: evidence.map(({ entity_id, rank, reference, rule, action }) => ({
        entity_id,
        rank,
        reference,
        rule,
        action,
      })),
    };
  });

  const kindCounts = new Map<string, Set<string>>();
  for (const group of candidates) {
    if (!accepted(group, conditions)) continue;
    for (const k of group.kinds) {
      if (Object.hasOwn(labels.types, k)) addTo(kindCounts, k, group.entity.id);
    }
  }
  const context = candidates.filter(
    (g) => (!kind || g.kinds.has(kind)) && hasMemberWith(index, g, kind, wanted),
  );
  const rows = (conditions.length ? conditions : [blankCondition()]).map((current, position) => {
    const others = conditions.filter((c, i) => i !== position && c.category);
    const categories = new Map<string, Set<string>>();
    const relations = new Map<string, Set<string>>();
    const values = new Map<string, Set<string>>();
    for (const group of context) {
      if (!others.length && !group[scope].length) continue;
      const key = group.entity.id;
      for (const unit of group[scope]) {
        if (!others.every((c) => matches(unit, c))) continue;
        for (const [category, relation, value] of unit) {
          addTo(categories, category, key);
          if (category !== current.category) continue;
          if (!current.value || value === current.value) addTo(relations, relation, key);
          if (!current.relation || relation === current.relation) addTo(values, value, key);
        }
      }
    }
    return {
      categories: Object.entries(labels.categories)
        .filter(([k]) => categories.get(k)?.size)
        .map(([k, label]) => ({ value: k, label, count: categories.get(k)!.size })),
      relations: options(index, current.category, relations, true, current.relation),
      values: options(index, current.category, values, false, current.value),
    };
  });
  return {
    items,
    total: ranked.length,
    facets: {
      kinds: Object.entries(labels.types)
        .filter(([k]) => kindCounts.get(k)?.size)
        .map(([k, label]) => ({ value: k, label, count: kindCounts.get(k)!.size })),
      conditions: rows,
      attributes: kind
        ? attributeFacets(
            kind,
            narrowed.flatMap((g) => g.members.filter((m) => ofKind(m, kind)).map((m) => m.id)),
            index.pack.attributes,
            wanted,
          )
        : [],
    },
    scope,
  };
}
