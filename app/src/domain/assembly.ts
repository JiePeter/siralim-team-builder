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

/**
 * Why a slot field cannot take gear, or null when it can: gear belongs to a slot's Primary, so a
 * Primary cannot become gear in its own slot. `source` is where placed gear comes from.
 */
export function gearRefusal(value: Team, target: Position, source?: Position): string | null {
  if (target.field === "base") return null;
  if (!value.slots[target.slot]?.base) return "Equip a Primary first";
  if (source?.field === "base" && source.slot === target.slot)
    return "A Primary cannot move within its own slot";
  return null;
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
  const refusal = gearRefusal(next, { slot: slotIndex, field });
  if (refusal) throw new Error(refusal);
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

/** Gear belongs to a slot's Primary: a slot without one sends the rest of its gear to the pool. */
export function returnOrphans(value: Team): Team {
  let next = value;
  value.slots.forEach((slot, i) => {
    if (slot.base) return;
    for (const field of ["fusion", "artifact", "relic"] as const)
      if (next.slots[i]![field]) next = returnEquipment(next, i, field);
    while (next.slots[i]!.spells?.length) next = returnEquipment(next, i, "spells", 0);
  });
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
  const refusal = gearRefusal(value, target, source);
  if (refusal) throw new Error(refusal);
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
