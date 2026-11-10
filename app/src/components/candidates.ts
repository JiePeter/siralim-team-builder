import { cards, type Catalog, type DiscoveryMember } from "@/data";
import {
  applicable,
  attributeFacets,
  hasAttributes,
  type AttributeFacet,
  type Attributes,
} from "@/domain/attributes";
import {
  groupsMeeting,
  memberWith,
  query,
  rankGroups,
  textMatches,
  type CardFields,
  type Condition,
  type DiscoveryResult,
  type Scope,
} from "@/domain/discovery";
import { memoRequest } from "@/data/memo";
import { discoveryPack, fallBackToScattered, textHits } from "@/stores/search";
import { compareText } from "@/domain/values";
import { fieldKind, type PickerField } from "./assembly";

export interface Candidate extends DiscoveryMember {
  /** The trait a creature or material carries, or the base an Anointment comes from. */
  detail: string;
  effects: CardFields["effects"];
  facts: CardFields["facts"];
  attrs: CardFields["attrs"];
  classification: NonNullable<CardFields["classification"]>;
}

/** Every component a field accepts from the full data, in name order. */
const compatible = memoRequest(async (field: PickerField, catalog: Catalog) => {
  const kind = fieldKind[field];
  const [index, shard] = await Promise.all([discoveryPack(), cards(kind)]);
  const anointments = new Map(
    catalog.perks.filter((p) => p.anointment).map((p) => [p.id, p.specialization]),
  );
  const result: Candidate[] = [];
  for (const group of index.groups) {
    const trait = group.members.find((m) => m.kind === "trait")?.name ?? "";
    for (const member of group.members) {
      if (member.kind !== kind) continue;
      if (field === "characterAnointment" && !anointments.has(member.id)) continue;
      const card = shard[member.id];
      result.push({
        ...member,
        effects: card?.effects ?? [],
        facts: card?.facts ?? [],
        attrs: card?.attrs ?? {},
        classification: card?.classification ?? [],
        detail:
          field === "characterAnointment"
            ? anointments.get(member.id)!
            : member.kind === "trait"
              ? ""
              : trait,
      });
    }
  }
  return result.sort((a, b) => compareText(a.name, b.name));
});

export interface Picked {
  items: Candidate[];
  /** Member ids that pass the text and attributes, so tray items are filtered the same way; null when neither is set. */
  matched: Set<string> | null;
  /** Counted over the components that match the text, as Search counts them. */
  facets: AttributeFacet[];
  /** The options of each mechanic filter row. */
  conditionFacets: DiscoveryResult["facets"]["conditions"];
}

/**
 * Components a field accepts that match `q` and the attributes, ranked as Search ranks them;
 * all of them in name order when neither is set.
 */
export async function candidates(
  field: PickerField,
  q: string,
  catalog: Catalog,
  attributes: Attributes = {},
  conditions: Condition[] = [],
  scope: Scope = "action",
): Promise<Picked> {
  const kind = fieldKind[field];
  const wanted = applicable(kind, attributes);
  const [all, index, phrased] = await Promise.all([
    compatible(field, catalog),
    discoveryPack(),
    textHits(q),
  ]);
  const accepted = new Set(all.map((c) => index.canonical.get(c.id) ?? c.id));
  // The field can accept none of the components holding the phrase.
  const { ids, found: groups } = await fallBackToScattered(
    q,
    phrased,
    (matching) =>
      matching ? rankGroups(textMatches(index, q, matching), q, matching) : index.groups,
    (found) => found.some((g) => accepted.has(g.entity.id)),
  );
  const conditionFacets = query(index, {
    q,
    kind,
    attributes,
    conditions,
    scope,
    ids,
    limit: 0,
  }).facets.conditions;
  const order = new Map(groups.map((g, i) => [g.entity.id, i]));
  const position = (id: string) => order.get(index.canonical.get(id) ?? id) ?? Infinity;
  const texted = ids
    ? all.filter((c) => position(c.id) < Infinity).sort((a, b) => position(a.id) - position(b.id))
    : all;
  const table = index.pack.attributes;
  const facets = attributeFacets(
    kind,
    texted.map((c) => c.id),
    table,
    wanted,
  );
  const mechanics = conditions.some((c) => c.category);
  if (!ids && !Object.keys(wanted).length && !mechanics)
    return { items: all, matched: null, facets, conditionFacets };
  const meeting = groupsMeeting(index, conditions, scope);
  const met = (id: string) => meeting.has(index.canonical.get(id) ?? id);
  const matched = new Set(
    groups
      .flatMap((g) => g.members.map((m) => m.id))
      .filter((id) => hasAttributes(table[id], wanted) && met(id)),
  );
  return {
    items: texted.filter((c) => memberWith(index, c, kind, wanted) && met(c.id)),
    matched,
    facets,
    conditionFacets,
  };
}
