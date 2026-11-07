import type { Catalog, DiscoveryMember } from "@/data";
import type { ClassName } from "@/data/types";
import {
  applicable,
  attributeFacets,
  hasAttributes,
  type AttributeFacet,
  type Attributes,
} from "@/domain/attributes";
import { memberWith, rankGroups, textMatches } from "@/domain/discovery";
import { memoRequest } from "@/data/memo";
import { discoveryPack, textIds } from "@/stores/search";
import { compareText } from "@/domain/values";
import { fieldKind, type PickerField } from "./assembly";

export interface Candidate extends DiscoveryMember {
  /** The trait a creature or material carries, or the base an Anointment comes from. */
  detail: string;
  /** A Spell Gem's class, which picks its sprite. */
  classification?: { class: ClassName }[];
}

/** Every component a field accepts from the full data, in name order. */
const compatible = memoRequest(async (field: PickerField, catalog: Catalog) => {
  const index = await discoveryPack();
  const kind = fieldKind[field];
  const anointments = new Map(
    catalog.perks.filter((p) => p.anointment).map((p) => [p.id, p.specialization]),
  );
  const result: Candidate[] = [];
  for (const group of index.groups) {
    const trait = group.members.find((m) => m.kind === "trait")?.name ?? "";
    for (const member of group.members) {
      if (member.kind !== kind) continue;
      if (field === "characterAnointment" && !anointments.has(member.id)) continue;
      const cls = index.pack.attributes[member.id]?.class;
      result.push({
        ...member,
        ...(cls ? { classification: [{ class: cls as ClassName }] } : {}),
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
): Promise<Picked> {
  const kind = fieldKind[field];
  const wanted = applicable(kind, attributes);
  const [all, index, ids] = await Promise.all([
    compatible(field, catalog),
    discoveryPack(),
    textIds(q),
  ]);
  const groups = ids ? rankGroups(textMatches(index, q, ids), q) : index.groups;
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
  if (!ids && !Object.keys(wanted).length) return { items: all, matched: null, facets };
  const matched = new Set(
    groups
      .flatMap((g) => g.members.map((m) => m.id))
      .filter((id) => hasAttributes(table[id], wanted)),
  );
  return { items: texted.filter((c) => memberWith(index, c, kind, wanted)), matched, facets };
}
