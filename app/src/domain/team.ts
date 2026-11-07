import * as v from "valibot";
import type { CharacterDefinitions, CharacterField, SlotField } from "./assembly";
import type { Catalog, Segment } from "@/data/types";
import {
  get,
  isDict,
  isInt,
  joinSegments,
  pyStr,
  slicePoints,
  truthy,
  unique,
  type Dict,
} from "./values";

export interface ArtifactConfig {
  type?: string;
  /** Property ids. */
  stats?: string[];
  tricks?: string[];
  spell?: string | null;
}

/** An equipped or selected component; a bare id is a component with no configuration. */
export interface Equipment {
  uid: string;
  id: string;
  properties?: string[];
  property_variants?: Record<string, number>;
  artifact?: ArtifactConfig;
  rank?: number;
  /** The creature or material a tray trait was added as, which is how the tray draws it. */
  shown?: string;
}

export type EquipmentRef = string | Equipment;

export const itemId = (item: EquipmentRef | undefined) =>
  typeof item === "string" ? item : item?.id;

export const asItem = (item: EquipmentRef): Equipment =>
  typeof item === "string" ? { uid: "", id: item, properties: [] } : item;

/** Component kinds each slot field holds. */
export type SlotKinds = Record<Exclude<SlotField, "nether">, string[]>;

/** Anointments a character holds with the Perks in `active`. */
export function anointmentCapacity(
  rules: Catalog["anointments"],
  active: (perk: string) => boolean,
  allAscended: boolean,
): number {
  let capacity = rules.base;
  for (const [perk, bonus] of Object.entries(rules.perks)) {
    if (active(perk)) capacity += allAscended ? (bonus.all_ascended ?? bonus.count) : bonus.count;
  }
  return capacity;
}

export interface Slot {
  base?: EquipmentRef;
  fusion?: EquipmentRef;
  artifact?: EquipmentRef;
  /** Traits of the Nether Stone socketed in the Artifact. */
  nether?: EquipmentRef[];
  spells?: EquipmentRef[];
  relic?: EquipmentRef;
}

export interface Character {
  specialization: string | null;
  /** perk id → rank */
  perks: Record<string, number>;
  anointments: string[];
  ascended: boolean;
  all_ascended: boolean;
}

export interface Team {
  name: string;
  notes: string;
  slots: Slot[];
  inventory: Equipment[];
  character: Character;
}

export const PARTY_SIZE = 6;
export const NETHER_TRAITS = 3;

export function newTeam(): Team {
  return {
    name: "My Team",
    slots: Array.from({ length: PARTY_SIZE }, () => ({})),
    notes: "",
    inventory: [],
    character: emptyCharacter(),
  };
}

function emptyCharacter(): Character {
  return {
    specialization: null,
    perks: {},
    anointments: [],
    ascended: false,
    all_ascended: false,
  };
}

type TraitRelations<T> = Partial<Record<"innate_trait" | "grants_trait", T[]>>;

/**
 * `team-rules.json`: database facts validation and build effects need beyond the catalog. Other
 * tables name a component by its position in the component lists, taken in key order.
 */
export interface TeamRules {
  /** component kind → ids */
  components: Record<string, string[]>;
  /** [Spell Gem, the property variant ids it accepts] */
  property_compatibility: [number, number[]][];
  /** property id → its variant ids */
  property_choices: Record<string, number[]>;
  /** [creature or material, the traits it carries] */
  traits: [number, TraitRelations<number>][];
  /** Traits that count once in the whole party */
  unstackable: number[];
  slot_kinds: SlotKinds;
  spell_gems: SpellGemRules;
  artifact_slots: { stats: number; tricks: number };
  /** Property variant ids that each base Potency on a stat; a Spell Gem takes at most one */
  potency_sources: number[];
  /**
   * [owner, Relic Rank or 0, stops only its holder's events (0/1), always stops them (0/1),
   * [listener, the listener's subject is its own holder (0/1)][]]
   */
  replacements?: [number, number, number, number, [number, number][]][];
}

/** An effect that can stop an event, and the listeners of that event it silences. */
export interface Replacement {
  owner: string;
  /** Relic Rank the effect needs; 0 when it is not a Relic's */
  rank: number;
  /** Stops only events of the creature that holds it */
  holderOnly: boolean;
  certain: boolean;
  listeners: { id: string; holder: boolean }[];
}

export interface SpellGemRules {
  /** Spell Gems a creature can equip at most, whatever raises its slots */
  most: number;
  /** Properties one Spell Gem holds */
  properties: number;
  /** The property that lets a Spell Gem take any class */
  any_class: string;
}

/** Team rules with component positions resolved to ids. */
export interface RuleFacts extends Pick<
  TeamRules,
  "slot_kinds" | "spell_gems" | "artifact_slots" | "potency_sources"
> {
  /** Spell Gem id → the property variant ids it accepts */
  property_compatibility: Record<string, number[]>;
  /** property id → its variant ids */
  property_choices: Record<string, number[]>;
  /** creature or material id → the traits it carries */
  traits: Record<string, TraitRelations<string>>;
}

export type Perk = Catalog["perks"][number] & { description: string };
export type Relic = Catalog["relics"][number] & {
  effects: { rank: number; description: string; segments: Segment[] }[];
};

/** Catalog and rules indexed for lookups; build once per data pack. */
export interface TeamIndex {
  catalog: Catalog;
  rules: RuleFacts;
  kinds: Map<string, string>;
  specializations: Map<string, string>;
  perks: Perk[];
  perksById: Map<string, Perk>;
  artifactProperties: Map<string, string>;
  relics: Map<string, Relic>;
  /** creature or material id → the trait it carries */
  traitOf: Map<string, string>;
  /** trait id → the creature and materials that carry it */
  carriers: Map<string, Carriers>;
  /** Traits that count once in the whole party */
  unstackable: Set<string>;
  replacements: Replacement[];
}

export interface Carriers {
  creature?: string;
  materials: string[];
}

function described<T extends { segments: Segment[] }>(item: T): T & { description: string } {
  const own = (item as { description?: string }).description;
  return { ...item, description: own ?? joinSegments(item.segments) };
}

export function teamIndex(catalog: Catalog, rules: TeamRules): TeamIndex {
  const kinds = new Map<string, string>();
  for (const [kind, ids] of Object.entries(rules.components)) {
    for (const id of ids) kinds.set(id, kind);
  }
  const ids = Object.values(rules.components).flat();
  const facts: RuleFacts = {
    slot_kinds: rules.slot_kinds,
    spell_gems: rules.spell_gems,
    artifact_slots: rules.artifact_slots,
    potency_sources: rules.potency_sources,
    property_compatibility: Object.fromEntries(
      rules.property_compatibility.map(([spell, variants]) => [ids[spell], variants]),
    ),
    property_choices: rules.property_choices,
    traits: Object.fromEntries(
      rules.traits.map(([carrier, carried]) => [
        ids[carrier],
        Object.fromEntries(
          Object.entries(carried).map(([rel, at]) => [rel, at.map((i) => ids[i])]),
        ),
      ]),
    ),
  };
  const perks = catalog.perks.map(described);
  const traitOf = new Map<string, string>();
  const carriers = new Map<string, Carriers>();
  for (const [id, carried] of Object.entries(facts.traits)) {
    for (const [rel, traits] of Object.entries(carried)) {
      for (const trait of traits ?? []) {
        traitOf.set(id, trait);
        const entry = carriers.get(trait) ?? { materials: [] };
        if (rel === "innate_trait") entry.creature = id;
        else entry.materials.push(id);
        carriers.set(trait, entry);
      }
    }
  }
  return {
    traitOf,
    carriers,
    unstackable: new Set((rules.unstackable ?? []).map((i) => ids[i]!)),
    replacements: (rules.replacements ?? []).map(([owner, rank, holderOnly, certain, heard]) => ({
      owner: ids[owner]!,
      rank,
      holderOnly: !!holderOnly,
      certain: !!certain,
      listeners: heard.map(([id, holder]) => ({ id: ids[id]!, holder: !!holder })),
    })),
    catalog,
    rules: facts,
    kinds,
    specializations: new Map(catalog.specializations.map((s) => [s.id, s.name])),
    perks,
    perksById: new Map(perks.map((p) => [p.id, p])),
    artifactProperties: new Map(catalog.artifact_properties.map((p) => [p.id, p.slot])),
    relics: new Map(catalog.relics.map((r) => [r.id, { ...r, effects: r.effects.map(described) }])),
  };
}

/** The trait a creature, material or trait id stands for; other ids stand for themselves. */
export function entityOf(index: TeamIndex, id: string): string {
  return index.traitOf.get(id) ?? id;
}

/** The creature and materials that carry the trait `id` stands for. */
export function carriersOf(index: TeamIndex, id: string): Carriers {
  return index.carriers.get(entityOf(index, id)) ?? { materials: [] };
}

/**
 * A creature or plain material in the tray is kept as its trait, so it fits any field one of the
 * trait's carriers fits. A configured Artifact keeps its material.
 */
export function asTrait(index: TeamIndex, item: Equipment): Equipment {
  const trait = index.traitOf.get(item.id);
  return trait && !item.artifact && !item.properties?.length
    ? { ...item, id: trait, shown: item.id }
    : item;
}

export function trayTraits(index: TeamIndex, team: Team): Team {
  return { ...team, inventory: team.inventory.map((item) => asTrait(index, item)) };
}

export class TeamError extends Error {}

function fail(message: string): never {
  throw new TeamError(message);
}

const any = v.optional(v.unknown());

/** A JSON object with no keys beyond `keys`; Valibot's object schemas also accept arrays. */
function shape<const K extends string>(...keys: K[]) {
  return v.pipe(
    v.custom<Dict>(isDict),
    v.strictObject(Object.fromEntries(keys.map((key) => [key, any])) as Record<K, typeof any>),
  );
}

const SlotShape = shape("base", "fusion", "artifact", "nether", "spells", "relic");
const EquipmentShape = shape(
  "uid",
  "id",
  "properties",
  "property_variants",
  "artifact",
  "rank",
  "shown",
);
const CharacterShape = shape("specialization", "perks", "anointments", "ascended", "all_ascended");
const ArtifactShape = shape("type", "stats", "tricks", "spell");
const Uid = v.pipe(v.string(), v.regex(/^[A-Za-z0-9_-]{1,100}$/));
const Flag = v.boolean();
const RelicRank = v.pipe(v.number(), v.integer(), v.minValue(1), v.maxValue(100));

export interface CharacterEffect extends Perk {
  rank: number;
  mode: "Specialization" | "Anointment";
  active: boolean;
  inactive_reason: string;
}

export interface CharacterEffects {
  effects: CharacterEffect[];
  anointment_capacity: number;
  specialization: string | null;
}

/** Active Perks and the Anointment capacity they give. */
export function characterEffects(index: TeamIndex, value: unknown): CharacterEffects {
  const character = isDict(value) ? value : {};
  const spec = index.specializations.get(character.specialization as string) ?? null;
  const perks = get(character, "perks", {});
  const ranks = isDict(perks) ? perks : {};
  const anointments = get(character, "anointments", []) as unknown[];
  const effects: CharacterEffect[] = [];
  for (const perk of index.perks) {
    const native = perk.specialization === spec;
    const always = native && perk.always_active;
    let rank = native ? (get(ranks, perk.id, 0) as number) : 0;
    if (native && perk.ascension && truthy(character.ascended)) rank = perk.ranks;
    if (always) rank = perk.ranks;
    const anointed = anointments.includes(perk.id);
    const ignored = spec === "Pariah" && perk.specialization === "Druid" && anointed;
    if (truthy(rank) || anointed) {
      effects.push({
        ...perk,
        rank: truthy(rank) ? rank : perk.ranks,
        mode: truthy(rank) ? "Specialization" : "Anointment",
        active: !ignored,
        inactive_reason: ignored ? "Pariah: Druid Anointments are inactive" : "",
      });
    }
  }
  return {
    effects,
    anointment_capacity: anointmentCapacity(
      index.catalog.anointments,
      (id) => effects.some((e) => e.id === id && e.active),
      truthy(character.all_ascended),
    ),
    specialization: spec,
  };
}

/** Whether `id` can be the character base, or an Anointment. */
export function isCharacterPart(
  definitions: Pick<CharacterDefinitions, "specializations" | "perks">,
  id: string,
  field: CharacterField,
): boolean {
  return field === "characterBase"
    ? definitions.specializations.some((s) => s.id === id)
    : definitions.perks.some((p) => p.id === id && p.anointment === true);
}

export function validateCharacter(index: TeamIndex, value: unknown): Character {
  if (!v.is(CharacterShape, value)) fail("Invalid character configuration");
  const spec = get(value, "specialization");
  const specName = index.specializations.get(spec as string);
  if (truthy(spec) && !isCharacterPart(index.catalog, spec as string, "characterBase"))
    fail("Specialization not found");
  for (const flag of ["ascended", "all_ascended"]) {
    if (!v.is(Flag, get(value, flag, false))) fail("Invalid Ascension flag");
  }
  const ranks = get(value, "perks", {});
  if (!isDict(ranks)) fail("Invalid Perk rank");
  for (const [key, rank] of Object.entries(ranks)) {
    const perk = index.perksById.get(key);
    if (
      !perk ||
      perk.specialization !== specName ||
      perk.ascension ||
      !isInt(rank) ||
      rank < 0 ||
      rank > perk.ranks
    ) {
      fail("Perk rank or specialization does not match");
    }
  }
  const anointments = get(value, "anointments", []);
  if (
    !Array.isArray(anointments) ||
    !anointments.every((a) => typeof a === "string") ||
    new Set(anointments).size !== anointments.length
  ) {
    fail("Anointment duplicate or invalid");
  }
  for (const key of anointments as string[]) {
    if (!isCharacterPart(index.catalog, key, "characterAnointment")) {
      fail("This Perk cannot be used as an Anointment");
    }
  }
  if (anointments.length > characterEffects(index, value).anointment_capacity) {
    fail("Anointment Count exceeds character capacity");
  }
  return value as unknown as Character;
}

export function validateArtifact(index: TeamIndex, value: unknown): void {
  if (!v.is(ArtifactShape, value)) fail("Invalid Artifact configuration");
  const type = get(value, "type", "Sword");
  if (typeof type !== "string" || !Object.hasOwn(index.catalog.artifact_primary, type)) {
    fail("Invalid Artifact type");
  }
  for (const [field, kind] of [
    ["stats", "stat"],
    ["tricks", "trick"],
  ] as const) {
    const entries = get(value, field, []);
    const slots = index.rules.artifact_slots;
    if (!Array.isArray(entries) || entries.length > slots[field]) {
      fail(`An Artifact holds at most ${slots.stats} Stats and ${slots.tricks} Tricks`);
    }
    for (const entry of entries) {
      if (typeof entry !== "string") fail("Invalid Artifact property");
      if (index.artifactProperties.get(entry) !== kind) fail("Property type does not match");
    }
  }
  const spell = get(value, "spell");
  if (truthy(spell) && index.kinds.get(spell as string) !== "spell") {
    fail("The Spell Slot takes a Spell Gem");
  }
}

function stableJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (isDict(value)) {
    const keys = Object.keys(value).sort();
    return `{${keys.map((k) => `${JSON.stringify(k)}:${stableJson(value[k])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

/** Identifies a gem configuration, so one saved before a rule tightened stays valid until edited. */
function signature(item: Dict): string {
  const properties = get(item, "properties", []);
  return stableJson([
    item.id,
    Array.isArray(properties) ? [...properties].sort() : properties,
    get(item, "property_variants", {}),
  ]);
}

/**
 * Check a whole team against the data pack and return its stored form.
 * `previous` is the team before this edit; gem configurations it already held are kept.
 * Throws TeamError with the message to show.
 */
export function validateTeam(index: TeamIndex, input: unknown, previous?: unknown): Team {
  if (!isDict(input) || !(previous == null || isDict(previous))) fail("Invalid team");
  const plan = input;
  const held = new Set<string>();
  if (previous) {
    const slots = (get(previous, "slots", []) ?? []) as Dict[];
    for (const item of [
      ...((get(previous, "inventory", []) ?? []) as unknown[]),
      ...slots.flatMap((s) => (get(s, "spells", []) as unknown[]) ?? []),
    ]) {
      if (isDict(item)) held.add(signature(item));
    }
  }
  const slots = plan.slots;
  if (!Array.isArray(slots) || slots.length !== PARTY_SIZE) fail("A team must contain six slots");
  const seen = new Set<string>();

  function component(key: unknown, kinds?: string[]): string {
    if (typeof key !== "string") fail("Invalid component");
    const kind = index.kinds.get(key);
    if (!kind || (kinds && !kinds.includes(kind))) {
      fail("Component type is incompatible with this slot");
    }
    return kind;
  }

  function instance(value: unknown, kinds?: string[]): void {
    if (typeof value === "string") {
      component(value, kinds);
      return;
    }
    if (!v.is(EquipmentShape, value)) fail("Invalid equipment");
    const kind = component(value.id, kinds);
    const uid = value.uid;
    if (!v.is(Uid, uid) || seen.has(uid)) fail("Invalid or duplicate equipment instance");
    seen.add(uid);
    if (
      Object.hasOwn(value, "shown") &&
      entityOf(index, value.shown as string) !== entityOf(index, value.id as string)
    ) {
      fail("Invalid equipment");
    }
    const properties = get(value, "properties", []);
    if (!Array.isArray(properties) || new Set(properties).size !== properties.length) {
      fail("Invalid properties");
    }
    if (properties.length && kind !== "spell") fail("Properties require a Spell Gem");
    for (const key of properties) component(key, ["enchantment"]);
    const variants = get(value, "property_variants", {});
    if (!isDict(variants) || Object.keys(variants).some((k) => !properties.includes(k))) {
      fail("Invalid property variant");
    }
    if ((properties.length || truthy(variants)) && !held.has(signature(value))) {
      const most = index.rules.spell_gems.properties;
      if (properties.length > most) fail(`A Spell Gem can have at most ${most} properties`);
      const compatible = index.rules.property_compatibility[value.id as string];
      const selected: number[] = [];
      for (const key of properties as string[]) {
        const choices = index.rules.property_choices[key] ?? [];
        if (!choices.length) continue;
        const id = get(variants, key, choices.length === 1 ? choices[0] : null);
        if (!isInt(id) || !choices.includes(id)) fail("Choose the specific property variant");
        if (compatible && !compatible.includes(id)) {
          fail("Property is incompatible with this Spell");
        }
        selected.push(id);
      }
      if (unique(selected).filter((id) => index.rules.potency_sources.includes(id)).length > 1) {
        fail("Choose only one alternative potency stat");
      }
    }
    if (Object.hasOwn(value, "artifact")) {
      if (kind !== "material" && kind !== "artifact") fail("Requires an Artifact");
      validateArtifact(index, value.artifact);
    }
    if (Object.hasOwn(value, "rank") && (kind !== "relic" || !v.is(RelicRank, value.rank))) {
      fail("Invalid Relic rank");
    }
  }

  for (const slot of slots) {
    if (!v.is(SlotShape, slot)) fail("Invalid slot");
    for (const field of ["base", "fusion", "artifact", "relic"] as const) {
      if (truthy(slot[field])) instance(slot[field], index.rules.slot_kinds[field]);
    }
    const nether = get(slot, "nether", []);
    if (!Array.isArray(nether) || nether.length > NETHER_TRAITS) fail("Invalid Nether Stone");
    for (const trait of nether) instance(trait, ["trait"]);
    const spells = get(slot, "spells", []);
    if (!Array.isArray(spells)) fail("Invalid Spell list");
    for (const gem of spells) instance(gem, index.rules.slot_kinds.spells);
    const spellIds = spells.map((gem) => itemId(gem as EquipmentRef));
    if (new Set(spellIds).size !== spellIds.length)
      fail("A creature cannot equip the same Spell Gem twice");
  }
  const items = plan.inventory;
  if (!Array.isArray(items) || items.length > 500) fail("Invalid selection");
  for (const item of items) {
    if (!isDict(item)) fail("Invalid selection item");
    instance(item);
  }
  const relics = (slots as Dict[])
    .filter((s) => truthy(s.relic))
    .map((s) => (typeof s.relic === "string" ? s.relic : (s.relic as Dict).id));
  if (new Set(relics).size !== relics.length) fail("The same Relic cannot be equipped twice");
  const character = validateCharacter(index, plan.character);
  return {
    character,
    name: slicePoints(pyStr(get(plan, "name", "My Team")), 200),
    notes: slicePoints(pyStr(get(plan, "notes", "")), 10000),
    slots: slots as Slot[],
    inventory: items as Equipment[],
  };
}
