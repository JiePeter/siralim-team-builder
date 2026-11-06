import { shallowRef } from "vue";
import { catalog, type Catalog } from "@/data";
import { memoRequest } from "@/data/memo";

const catalogState = shallowRef<Catalog | null>(null);
const request = memoRequest(() => catalog().then((value) => (catalogState.value = value)));

/** The configuration catalog, loaded on first use; perks need it to resolve what gets added. */
export function useCatalog() {
  request().catch(() => {});
  return catalogState;
}

export interface Candidate {
  id: string;
  kind?: string;
  related?: { id: string; kind: string }[];
}

/** A Perk and the character base it belongs to. */
export function perkBase(catalog: Catalog | null, id: string) {
  const perk = catalog?.perks.find((p) => p.id === id);
  const base = perk && catalog?.specializations.find((s) => s.name === perk.specialization);
  return { perk, base };
}

/** A perk adds its character base unless it is an Anointment. */
export function selectionId(data: Candidate, perks: Catalog | null): string {
  if (data.kind !== "perk") return data.id;
  const { perk, base } = perkBase(perks, data.id);
  return perk?.anointment ? data.id : base?.id || data.id;
}

export function selectionLabel(data: Candidate, perks: Catalog | null): string {
  if (data.kind !== "perk") return "Add";
  const perk = perks?.perks.find((p) => p.id === data.id);
  return perk?.anointment
    ? "Add"
    : perk?.specialization
      ? `${perk.specialization} Specialization`
      : "Specialization";
}
