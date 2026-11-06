import { gearRefusal, type CharacterField, type Position, type SlotField } from "./assembly";
import {
  asItem,
  itemId,
  characterEffects,
  entityOf,
  PARTY_SIZE,
  type EquipmentRef,
  type Slot,
  type SpellGemRules,
  type Team,
  type TeamIndex,
} from "./team";

/** Where a component sits in the team, outside the tray. */
export type Placement =
  | { slot: number; field: SlotField; index?: number }
  | { character: CharacterField; position: number };

export interface Whereabouts {
  /** Tray instances of the component, in tray order. */
  tray: string[];
  placed: Placement[];
}

/** Every component placed in the team, with where it sits. */
export function placedParts(team: Team): { ref: EquipmentRef; at: Placement }[] {
  const parts: { ref: EquipmentRef; at: Placement }[] = [];
  team.slots.forEach((slot, i) => {
    for (const field of ["base", "fusion", "artifact", "relic"] as const) {
      const ref = slot[field];
      if (ref) parts.push({ ref, at: { slot: i, field } });
    }
    slot.spells?.forEach((ref, index) =>
      parts.push({ ref, at: { slot: i, field: "spells", index } }),
    );
  });
  const { specialization, anointments } = team.character;
  if (specialization)
    parts.push({ ref: specialization, at: { character: "characterBase", position: 0 } });
  anointments.forEach((ref, position) =>
    parts.push({ ref, at: { character: "characterAnointment", position } }),
  );
  return parts;
}

/** `entity` maps an id to what it stands for, so a creature, its trait and its material match. */
export function whereIs(
  team: Team,
  id: string,
  entity: (id: string) => string = (key) => key,
): Whereabouts {
  const target = entity(id);
  const same = (item: EquipmentRef) => entity(itemId(item)!) === target;
  return {
    tray: team.inventory.filter(same).map((item) => item.uid),
    placed: placedParts(team)
      .filter((part) => same(part.ref))
      .map((part) => part.at),
  };
}

/** More copies of one Trait than a team has creatures cannot all take effect. */
export const MAX_TRAIT_COPIES = PARTY_SIZE;

/** Copies of each Trait across the team and tray, counting creatures and materials as their Trait. */
function traitCopies(index: TeamIndex, team: Team): Map<string, number> {
  const counts = new Map<string, number>();
  for (const item of [...team.inventory, ...placedParts(team).map((part) => part.ref)]) {
    const trait = entityOf(index, itemId(item)!);
    if (trait?.startsWith("trait:")) counts.set(trait, (counts.get(trait) ?? 0) + 1);
  }
  return counts;
}

/** A Trait that `after` holds more copies of than allowed, and more than `before` did. */
export function excessTrait(index: TeamIndex, before: Team, after: Team): string | null {
  const old = traitCopies(index, before);
  for (const [trait, count] of traitCopies(index, after)) {
    if (count > MAX_TRAIT_COPIES && count > (old.get(trait) ?? 0)) return trait;
  }
  return null;
}

export const ARMY_OF_GODS = "perk:312";

/**
 * Avatar creatures the party may hold: one, plus one per rank of Army of Gods; none while the
 * Deprived base is set, since Total Deprivation is always active for it.
 */
export function avatarLimit(index: TeamIndex, character: Team["character"]): number {
  const { effects, specialization } = characterEffects(index, character);
  if (specialization === "Deprived") return 0;
  const army = effects.find((effect) => effect.id === ARMY_OF_GODS && effect.active);
  return 1 + (army?.rank ?? 0);
}

export interface AvatarCheck {
  limit: number;
  /** Slots whose primary creature is an Avatar. */
  slots: number[];
  notice: string | null;
}

/** Fused creatures do not join the party, so only primary creatures count. */
export function avatarCheck(
  index: TeamIndex,
  team: Team,
  isAvatar: (id: string) => boolean,
): AvatarCheck {
  const limit = avatarLimit(index, team.character);
  const slots = team.slots.flatMap((slot, i) => {
    const id = itemId(slot.base);
    return id && isAvatar(id) ? [i] : [];
  });
  const notice =
    slots.length <= limit
      ? null
      : limit === 0
        ? "Deprived cannot use Avatar creatures"
        : `Avatar creatures ${slots.length}/${limit}`;
  return { limit, slots, notice };
}

export type TraitField = "base" | "fusion" | "artifact";

/**
 * The traits a creature carries, in field order: its innate trait, its Fusion parent's trait, and
 * the trait its Artifact's Trait Slot adds.
 */
export function slotTraits(index: TeamIndex, slot: Slot): { field: TraitField; trait: string }[] {
  return (["base", "fusion", "artifact"] as const).flatMap((field) => {
    const id = itemId(slot[field]);
    const trait = id && entityOf(index, id);
    return trait && index.carriers.has(trait) ? [{ field, trait }] : [];
  });
}

/**
 * Fusion and Artifact fields that give a creature a trait it already has from an earlier field.
 * A creature holds one copy of a trait, so the repeat has no effect.
 */
export function repeatedTraits(
  index: TeamIndex,
  slot: Slot,
): { field: TraitField; trait: string }[] {
  const seen = new Set<string>();
  return slotTraits(index, slot).filter(({ trait }) => {
    const again = seen.has(trait);
    seen.add(trait);
    return again;
  });
}

export const REPEATED_TRAIT = "This creature already has this Trait";

/** A trait that `after` repeats on the creature and `before` did not. */
function slotRepeat(index: TeamIndex, before: Slot, after: Slot): string | null {
  const key = (r: { field: string; trait: string }) => `${r.field}:${r.trait}`;
  const old = new Set(repeatedTraits(index, before).map(key));
  return repeatedTraits(index, after).find((r) => !old.has(key(r)))?.trait ?? null;
}

/** A trait that `after` repeats on one of its creatures and `before` did not. */
export function newRepeat(index: TeamIndex, before: Team, after: Team): string | null {
  for (const [i, slot] of after.slots.entries()) {
    const trait = slotRepeat(index, before.slots[i] ?? {}, slot);
    if (trait) return trait;
  }
  return null;
}

/**
 * Why the component `id` cannot go into `target`, or null when it can. `source` is where it comes
 * from when it is already placed.
 */
export function placementRefusal(
  index: TeamIndex,
  team: Team,
  target: Position,
  id: string,
  source?: Position,
): string | null {
  const refusal = gearRefusal(team, target, source);
  if (refusal) return refusal;
  const slot = team.slots[target.slot];
  if (!slot || target.field === "spells" || target.field === "relic") return null;
  const after: Slot = { ...slot };
  if (source?.slot === target.slot && source.field !== "spells") delete after[source.field];
  after[target.field] = id;
  return slotRepeat(index, slot, after) ? REPEATED_TRAIT : null;
}

/**
 * Traits that do not stack held by more than one creature, with those slots in order; only the
 * first creature's copy counts.
 */
export function unstackedTraits(
  index: TeamIndex,
  team: Team,
): { trait: string; slots: number[] }[] {
  const holders = new Map<string, number[]>();
  team.slots.forEach((slot, i) => {
    const traits = new Set(slotTraits(index, slot).map(({ trait }) => trait));
    for (const trait of traits)
      if (index.unstackable.has(trait)) holders.set(trait, [...(holders.get(trait) ?? []), i]);
  });
  return [...holders]
    .filter(([, slots]) => slots.length > 1)
    .map(([trait, slots]) => ({ trait, slots }));
}

/**
 * Effects in the team that can stop an event, with the team's listeners of that event they
 * silence. Perks act for every creature; a holder-only effect silences only its own creature's
 * listeners of that creature's events.
 */
export function replacementNotices(
  index: TeamIndex,
  team: Team,
): { owner: string; listeners: string[]; certain: boolean }[] {
  const slotsOf = new Map<string, number[]>();
  const relicRank = new Map<string, number>();
  const hold = (id: string | undefined, i: number) => {
    if (id) slotsOf.set(id, [...(slotsOf.get(id) ?? []), i]);
  };
  team.slots.forEach((slot, i) => {
    for (const { trait } of slotTraits(index, slot)) hold(trait, i);
    for (const gem of slot.spells ?? []) hold(itemId(gem), i);
    const relic = slot.relic && asItem(slot.relic);
    if (relic) {
      hold(relic.id, i);
      relicRank.set(relic.id, Math.max(relicRank.get(relic.id) ?? 0, relic.rank ?? 1));
    }
  });
  const perks = new Set(
    characterEffects(index, team.character)
      .effects.filter((e) => e.active)
      .map((e) => e.id),
  );
  const everywhere = [...team.slots.keys()];
  const where = (id: string) => (perks.has(id) ? everywhere : (slotsOf.get(id) ?? []));
  const notices = new Map<string, { owner: string; listeners: string[]; certain: boolean }>();
  for (const r of index.replacements) {
    const owners = where(r.owner);
    if (!owners.length || (r.rank && (relicRank.get(r.owner) ?? 0) < r.rank)) continue;
    const listeners = r.listeners
      .filter(({ id, holder }) => {
        const at = where(id);
        if (!r.holderOnly) return at.length > 0;
        return holder && at.some((slot) => owners.includes(slot));
      })
      .map(({ id }) => id);
    if (!listeners.length) continue;
    const notice = notices.get(r.owner) ?? { owner: r.owner, listeners: [], certain: true };
    notice.listeners = [...new Set([...notice.listeners, ...listeners])];
    notice.certain &&= r.certain;
    notices.set(r.owner, notice);
  }
  return [...notices.values()];
}

/**
 * Spell Gem counts above the maximum and gems of another class than their creature. Traits and
 * perks can allow the class, so it is a notice. A fused creature has its Fusion parent's class
 * unless `blended`; a Class Swap gem can take any class.
 */
export function gemNotices(
  team: Team,
  classOf: (id: string) => string | undefined,
  blended: boolean,
  limits: Pick<SpellGemRules, "most" | "any_class">,
): { slot: number; message: string }[] {
  const notices: { slot: number; message: string }[] = [];
  team.slots.forEach((slot, i) => {
    const gems = (slot.spells ?? []).map(asItem);
    if (gems.length > limits.most)
      notices.push({
        slot: i,
        message: `${gems.length} Spell Gems, above the maximum of ${limits.most}`,
      });
    const parent = slot.fusion && !blended ? slot.fusion : slot.base;
    const own = parent && classOf(itemId(parent)!);
    if (!own) return;
    const other = new Set(
      gems
        .filter((gem) => !gem.properties?.includes(limits.any_class))
        .map((gem) => classOf(gem.id))
        .filter((gemClass): gemClass is string => !!gemClass && gemClass !== own),
    );
    for (const gemClass of other)
      notices.push({ slot: i, message: `a ${gemClass} Spell Gem on a ${own} creature` });
  });
  return notices;
}
