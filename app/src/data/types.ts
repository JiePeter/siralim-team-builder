export type ClassName = "Nature" | "Sorcery" | "Death" | "Chaos" | "Life";

export interface Manifest {
  game_version: string;
  /** Changes whenever any pack file changes; requests carry it so caches never mix two packs. */
  pack: string;
  /** object id → path of its page, for the pages not at the default path */
  objects: Record<string, string>;
  /** object kind → path of its card shard */
  cards: Record<string, string>;
}

/**
 * A run of effect text; `id`/`kind` mark an inline reference to another object, `role` what the
 * mechanics annotation says this run states, `tag` the kind of named value it is and `icon` its
 * game icon.
 */
export interface Segment {
  text: string;
  id?: string;
  kind?: string;
  role?: "trigger" | "condition" | "effect" | "amount" | "note";
  tag?: string;
  icon?: string;
}

export interface Classification {
  class: ClassName | null;
  race: string | null;
  availability_basis: string;
}

export type Stats = Record<"attack" | "defense" | "health" | "intelligence" | "speed", string>;

export interface Attrs {
  image?: string;
  icon?: string;
  class?: ClassName;
  class_id?: string;
  class_icon?: string;
  race?: string;
  race_id?: string;
  race_icon?: string;
  rank?: number | string;
  stats?: Stats;
  [key: string]: unknown;
}

export interface Effect {
  id: string;
  name: string;
  description: string;
  segments?: Segment[];
  label: string | null;
  rank: number | null;
}

export interface Route {
  id: number;
  method: string;
  location: string;
  requirements: Record<string, string | number | boolean>;
  location_name: string;
  location_image: string | null;
  /** The inscription, Godspawn Heart or gemstone the route goes through. */
  via?: string;
}

/** An object nested inside another object's page. */
export interface ObjectSummary {
  id: string;
  kind: string;
  name: string;
  description: string;
  attrs: Attrs;
  segments: Segment[];
  effects: Effect[];
  facts: string[];
  routes: Route[];
  classification?: Classification[];
}

/** A creature or material carrying a trait. */
export interface Carrier {
  id: string;
  kind: string;
  name: string;
  image: string | null;
}

export interface FamilyMember {
  id: string;
  kind: string;
  name: string;
  image: string | null;
  classification: Classification[];
}

export interface Offer {
  id: string;
  cost: { cost: number | string; currency: string };
  requirements: Record<string, string | number>;
  item: Omit<ObjectSummary, "routes">;
  /** The inscription, Godspawn Heart or gemstone sold for the item. */
  via?: string;
}

export interface Section {
  title: string;
  items: (ObjectSummary & { matched_rules?: unknown[] })[];
}

export interface ObjectPage {
  id: string;
  kind: string;
  name: string;
  description: string;
  attrs: Attrs;
  selectable: boolean;
  classification: Classification[];
  offers: Offer[];
  routes: Route[];
  segments: Segment[];
  effects: Effect[];
  facts: string[];
  sections: Section[];
  options: Carrier[];
  products: ObjectSummary[];
  related: ObjectSummary[];
  family: FamilyMember[];
  traits: ObjectSummary[];
  materials: ObjectSummary[];
  creatures: ObjectSummary[];
  perks: ObjectSummary[];
  /** Path of the object's Synergies: its own, or those of the trait it carries. */
  synergies?: string;
  parent?: { id: string };
  god_contents?: {
    realms: ObjectSummary[];
    relics: ObjectSummary[];
    shops: (ObjectSummary & { offers: Offer[] })[];
    godspawn: ObjectSummary[];
    ultimate_spells: ObjectSummary[];
  };
}

/** A fact about a synergy rule or link, stored as its layer, name and display text. */
export type StoredFact = [layer: string, name: string, text: string];

export interface Fact {
  layer: string;
  name: string;
  text: string;
}

export interface SynergyRule {
  reference: string;
  rank: number | null;
  /** Keys of SynergyRules.facts */
  conditions: string[];
  segments: Segment[];
  /** Present only when it differs from the joined segments. */
  text?: string;
}

export interface SynergyObject {
  id: string;
  name?: string;
  kind?: string;
  image?: string;
  classification?: Pick<Classification, "class">[];
}

export interface SynergyRules {
  relations: string[];
  strengths: string[];
  objects: Record<string, SynergyObject>;
  perks: Record<string, string>;
  rules: Record<string, SynergyRule>;
  facts: Record<string, StoredFact>;
}

/** Keys and positions into SynergyRules, without trailing blanks. */
export type StoredSynergy = [
  object: string,
  relation: number,
  strength: number,
  rule: string,
  constraints?: string[],
  requirements?: string[],
  side?: string | null,
  rank?: number | null,
  perk?: string,
];

export interface SynergyFile {
  items: StoredSynergy[];
}

export interface SynergyItem extends SynergyObject {
  relation: string;
  strength: string;
  /** The owner's rank whose rule makes the connection, for an owner with ranks. */
  source_rank?: number;
  /** The Perk whose rule makes the connection, for a Character base. */
  source_perk?: string;
  shared_constraints: Fact[];
  witness: { requires_target_side?: string | null; requirements?: Fact[] };
  target_rule: Omit<SynergyRule, "conditions"> & { text: string; conditions: Fact[] };
}

export interface Synergies {
  items: SynergyItem[];
}

/** An Artifact property value at a tier: `floor(base + mult × (tier − 1))`, or `base + floor(tier / div)`. */
export interface ArtifactFormula {
  base: number;
  mult?: number;
  div?: number;
  cap?: number;
  unit: string;
}

export interface Catalog {
  specializations: {
    id: string;
    name: string;
    description: string;
    game_id: number;
    image: string;
  }[];
  perks: {
    id: string;
    name: string;
    specialization: string;
    ranks: number;
    costPerRank: number;
    anointment: boolean;
    ascension: boolean;
    /** Counts at full rank whenever its specialization is the character base */
    always_active?: true;
    short_name: string;
    game_id: number;
    image: string;
    segments: Segment[];
  }[];
  /** Anointments every character holds, and those each Perk adds while active. */
  anointments: {
    base: number;
    perks: Record<string, { count: number; all_ascended?: number }>;
  };
  /** Class name → its icon. */
  class_icons: Record<string, string>;
  artifact_properties: {
    id: string;
    name: string;
    slot: string;
    segments: Segment[];
    formula: ArtifactFormula;
  }[];
  /** Artifact type → its primary stat. */
  artifact_primary: Record<string, ArtifactFormula & { stat: string }>;
  statuses: { name: string; kind: "buff" | "debuff" }[];
  relics: { id: string; name: string; effects: { rank: number; segments: Segment[] }[] }[];
  materials: { id: string; name: string }[];
  spells: { id: string; name: string; segments: Segment[] }[];
}

/** [category, relation, value] */
export type Feature = [string, string, string];

export interface DiscoveryMember {
  id: string;
  kind: string;
  name: string;
  description: string;
  image: string | null;
  aliases?: string[];
}

export interface DiscoveryGroup {
  id: string;
  members: DiscoveryMember[];
  /** Where the group's members are found, sorted; part of the text the search matches. */
  locations: string[];
  kinds: string[];
  /** Each unit is a list of indices into Discovery.features. */
  action: number[][];
  rule: number[][];
  component: number[][];
  /** descriptors[i] describes action[i]. */
  descriptors: {
    entity_id: string;
    rank: number | null;
    reference: string;
    rule: number;
    action: number;
  }[];
}

export interface Discovery {
  features: Feature[];
  groups: DiscoveryGroup[];
  references: {
    id: string;
    kind: string;
    name: string;
    description: string;
    image: string | null;
  }[];
  /** Class, race and Character base by component id, for components that have them. */
  attributes: Record<string, Partial<Record<"class" | "race" | "base", string>>>;
  status_kinds: Record<string, "buff" | "debuff">;
  labels: {
    categories: Record<string, string>;
    relations: Record<string, Record<string, string>>;
    types: Record<string, string>;
    values: Record<string, Record<string, string>>;
    unoffered_relations: [string, string][];
    unoffered_values: [string, string][];
    value_aliases: [string, string, string][];
  };
}

export interface SearchDocument {
  id: string;
  name: string;
  kind: string;
  members: string;
  text: string;
  locations: string;
}

/** A Spell Gem property from `gem-properties.json`. */
export interface GemProperty {
  id: string;
  name: string;
  game_property_ids: number[];
  variants: { id: number; label: string; image?: string }[];
  image: string;
  routes: Route[];
}
