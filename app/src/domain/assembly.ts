// Independent equipment instances: moving consumes a pool item; copying clones its configuration.
import {
  isCharacterPart,
  itemId,
  type Equipment,
  type EquipmentRef,
  type Slot,
  type Team,
} from "./team";

export type SlotField = "base" | "fusion" | "artifact" | "spells" | "relic";
export type CharacterField = "characterBase" | "characterAnointment";

export const fieldLabels: Record<SlotField, string> = {
  base: "Primary",
  fusion: "Fusion",
  artifact: "Artifact",
  relic: "Relic",
  spells: "Spell Gem",
};

export interface Position {
  slot: number;
  field: SlotField;
  index?: number;
}

export type TraitField = "base" | "fusion" | "artifact";

export interface TraitPosition {
  slot: number;
  field: TraitField;
}

/** The catalog parts character moves read. */
export interface CharacterDefinitions {
  specializations: { id: string; name: string }[];
  perks: {
    id: string;
    specialization: string;
    ranks: number;
    ascension?: boolean;
    anointment?: boolean;
  }[];
}

export function newInstance(id: string, properties: string[] = []): Equipment {
  return { uid: crypto.randomUUID(), id, properties: [...properties] };
}

export function cloneInstance(item: EquipmentRef): Equipment {
  return typeof item === "string"
    ? newInstance(item)
    : { ...structuredClone(item), uid: crypto.randomUUID() };
}

/** Ranks of `perks` with every non-Ascension Perk at its maximum. */
export function fullRanks(perks: CharacterDefinitions["perks"]): Record<string, number> {
  return Object.fromEntries(perks.filter((p) => !p.ascension).map((p) => [p.id, p.ranks]));
}

function poolIndex(value: Team, uid: string): number {
  const index = value.inventory.findIndex((i) => i.uid === uid);
  if (index < 0) throw new Error("Component has moved");
  return index;
}

/** Equip a pool instance as the component `resolvedId`; `validateTeam` checks the field takes it. */
export function installInstance(
  value: Team,
  uid: string,
  slotIndex: number,
  field: SlotField,
  resolvedId: string,
): Team {
  const next = structuredClone(value);
  const index = poolIndex(next, uid);
  const item = next.inventory[index]!;
  const slot = next.slots[slotIndex];
  if (!slot) throw new Error("Invalid slot");
  if (field !== "spells" && slot[field]) throw new Error("This slot is occupied");
  const installed: Equipment = { ...item, id: resolvedId };
  if (field === "relic") installed.rank ??= 1;
  if (field === "spells") (slot.spells ??= []).push(installed);
  else slot[field] = installed;
  next.inventory.splice(index, 1);
  return next;
}

export function equipmentAt(value: Team, slot: number, field: SlotField, index = 0) {
  const at: Slot | undefined = value.slots[slot];
  return field === "spells" ? at?.spells?.[index] : at?.[field];
}

/** Unequip into the pool. */
export function returnEquipment(value: Team, slot: number, field: SlotField, index = 0): Team {
  const next = structuredClone(value);
  const item = equipmentAt(next, slot, field, index);
  if (!item) throw new Error("Equipment not found");
  next.inventory.push(typeof item === "string" ? newInstance(item) : item);
  if (field === "spells") next.slots[slot]!.spells!.splice(index, 1);
  else delete next.slots[slot]![field];
  return next;
}

/** Send everything in a slot to the pool. */
export function returnSlot(value: Team, slot: number): Team {
  let next = value;
  for (const field of ["base", "fusion", "artifact", "relic"] as const)
    if (next.slots[slot]![field]) next = returnEquipment(next, slot, field);
  while (next.slots[slot]!.spells?.length) next = returnEquipment(next, slot, "spells", 0);
  return next;
}

/** Add a configured copy of an equipped Spell Gem or Artifact to the pool. */
export function copyEquipment(value: Team, slot: number, field: SlotField, index = 0): Team {
  const next = structuredClone(value);
  const item = equipmentAt(next, slot, field, index);
  if (!item || !["artifact", "spells"].includes(field))
    throw new Error("Select a Spell Gem or an Artifact");
  next.inventory.push(cloneInstance(item));
  return next;
}

/** Install a pool instance, sending the field's current occupant back to the pool. */
export function replaceInstance(
  value: Team,
  uid: string,
  slot: number,
  field: SlotField,
  resolvedId: string,
): Team {
  const occupied = field !== "spells" && equipmentAt(value, slot, field);
  return installInstance(
    occupied ? returnEquipment(value, slot, field) : value,
    uid,
    slot,
    field,
    resolvedId,
  );
}

/** Move equipped gear; an occupied target field sends its occupant back to the pool. */
export function moveEquipment(value: Team, source: Position, target: Position): Team {
  if (source.slot === target.slot && source.field === target.field && target.field !== "spells")
    return structuredClone(value);
  const item = equipmentAt(value, source.slot, source.field, source.index);
  const cleared =
    target.field !== "spells" && equipmentAt(value, target.slot, target.field)
      ? returnEquipment(value, target.slot, target.field)
      : value;
  const next = returnEquipment(cleared, source.slot, source.field, source.index);
  return installInstance(
    next,
    next.inventory.at(-1)!.uid,
    target.slot,
    target.field,
    itemId(item)!,
  );
}

/**
 * Exchange two filled Trait fields; the rest of each slot's gear stays. Two creature fields or two
 * Artifacts trade whole instances. Between an Artifact and a creature field only the Traits change
 * places, through `carriers`, so the Artifact keeps its configuration.
 */
export function swapTraits(
  value: Team,
  a: TraitPosition,
  b: TraitPosition,
  carriers?: { creature: string; material: string },
): Team {
  // Drag feedback passes the live reactive team, which structuredClone rejects.
  const next = { ...value, slots: value.slots.map((slot) => ({ ...slot })) };
  const first = next.slots[a.slot]?.[a.field];
  const second = next.slots[b.slot]?.[b.field];
  if (!first || !second) throw new Error("Component has moved");
  const carrying = (item: EquipmentRef, field: TraitField, other: EquipmentRef) => {
    if (!carriers) return other;
    const id = field === "artifact" ? carriers.material : carriers.creature;
    if (typeof item === "string") return id;
    const renamed = { ...item, id };
    delete renamed.shown;
    return renamed;
  };
  next.slots[a.slot]![a.field] = carrying(first, a.field, second);
  next.slots[b.slot]![b.field] = carrying(second, b.field, first);
  return next;
}

/** Use a pool instance as the Specialization or as the Anointment at `position`. */
export function installCharacterPart(
  value: Team,
  uid: string,
  field: CharacterField,
  definitions: CharacterDefinitions,
  position = 0,
): Team {
  const next = structuredClone(value);
  const index = poolIndex(next, uid);
  const item = next.inventory[index]!;
  const c = next.character;
  if (!isCharacterPart(definitions, item.id, field))
    throw new Error(
      field === "characterBase"
        ? "Select a Specialization"
        : "This Perk cannot be used as an Anointment",
    );
  if (field === "characterBase") {
    const spec = definitions.specializations.find((s) => s.id === item.id)!;
    if (c.specialization === item.id) throw new Error("This Specialization is already selected");
    if (c.specialization) next.inventory.push(newInstance(c.specialization));
    c.specialization = item.id;
    c.perks = fullRanks(definitions.perks.filter((p) => p.specialization === spec.name));
    c.ascended = false;
    c.all_ascended = false;
  } else if (field === "characterAnointment") {
    if (position < c.anointments.length) {
      next.inventory.push(newInstance(c.anointments[position]!));
      c.anointments[position] = item.id;
    } else c.anointments.push(item.id);
  } else throw new Error("Invalid character slot");
  next.inventory.splice(index, 1);
  return next;
}

/** Return the Specialization or the Anointment at `position` to the pool. */
export function returnCharacterPart(value: Team, field: CharacterField, position = 0): Team {
  const next = structuredClone(value);
  const c = next.character;
  if (field === "characterBase") {
    if (c.specialization) next.inventory.push(newInstance(c.specialization));
    c.specialization = null;
    c.perks = {};
    c.ascended = false;
    c.all_ascended = false;
  } else if (field === "characterAnointment") {
    const id = c.anointments[position];
    if (id) {
      next.inventory.push(newInstance(id));
      c.anointments.splice(position, 1);
    }
  } else throw new Error("Invalid character slot");
  return next;
}
