import { shallowRef } from "vue";
import { gemProperties, joinSegments, type Catalog, type GemProperty } from "@/data";
import { artifactValueText } from "@/domain/artifact";
import { t } from "@/i18n";
import type { CharacterField, SlotField } from "@/domain/assembly";
import {
  isCharacterPart,
  type ArtifactConfig,
  type Carriers,
  type Equipment,
  type SlotKinds,
  type TeamIndex,
} from "@/domain/team";

/** Component kinds a field accepts from the pool; a trait installs as one of its carriers. */
export function fieldKinds(slotKinds: SlotKinds): Record<SlotField, string[]> {
  return {
    base: [...slotKinds.base, "trait"],
    fusion: [...slotKinds.fusion, "trait"],
    artifact: [...slotKinds.artifact, "trait"],
    nether: ["trait"],
    relic: slotKinds.relic,
    spells: slotKinds.spells,
  };
}

/** A field the picker fills: a slot field, a character field, or the Artifact's trait slot. */
export type PickerField = SlotField | CharacterField | "artifactTrait";

/** The component kind a picker offers for a field, and the kind its Open in Search filters by. */
export const fieldKind: Record<PickerField, string> = {
  base: "creature",
  fusion: "creature",
  artifact: "material",
  nether: "trait",
  relic: "relic",
  spells: "spell",
  characterBase: "specialization",
  characterAnointment: "perk",
  artifactTrait: "material",
};

/** When an Artifact casts its Spell Slot gem, with the game's fixed chance. */
const ARTIFACT_TYPES = ["Sword", "Staff", "Helmet", "Shield", "Boots"];

export const artifactTrigger: Record<string, string> = Object.fromEntries(
  ARTIFACT_TYPES.map((type) => [type, t(`editors.artifact.triggers.${type}`)]),
);

/** The name an Artifact type is shown under. */
export const artifactTypeName = (type: string): string =>
  ARTIFACT_TYPES.includes(type) ? t(`editors.artifact.types.${type}`) : type;

/** Blend: "your Fused creatures' classes change to match that of their primary parent". */
export const BLEND = "trait:899";

export const slotIndex = (i: number) => String(i + 1).padStart(2, "0");

/** Whether a trait has a carrier the field takes: a creature for Primary and Fusion, a material for Artifact. */
export function carriedInto(carriers: Carriers, field: PickerField): boolean {
  if (field === "nether") return true;
  if (field === "base" || field === "fusion") return !!carriers.creature;
  if (field === "artifact" || field === "artifactTrait") return carriers.materials.length > 0;
  return false;
}

/** Pool items a field can take, by the kind each component has in the team rules. */
export function poolChoices(
  inventory: Equipment[],
  field: SlotField,
  kindOf: (id: string) => string | undefined,
  slotKinds: SlotKinds,
  carriers?: (id: string) => Carriers | undefined,
): Equipment[] {
  const accepted = fieldKinds(slotKinds)[field];
  return inventory.filter((item) => {
    const kind = kindOf(item.id) ?? "";
    const carried = kind === "trait" ? carriers?.(item.id) : undefined;
    return accepted.includes(kind) && (!carried || carriedInto(carried, field));
  });
}

/**
 * The component a tray item shows as: a trait as what it was added as, otherwise as its creature,
 * or as its material when no creature carries it; for a field, as the carrier that field takes.
 */
export function shownAs(index: TeamIndex | null, item: Equipment, field?: PickerField): string {
  const carried = !item.artifact ? index?.carriers.get(item.id) : undefined;
  if (!carried) return item.id;
  const material = carried.materials[0];
  if (field === "artifact" || field === "artifactTrait") return material ?? item.id;
  if (field) return carried.creature ?? material ?? item.id;
  return item.shown ?? carried.creature ?? material ?? item.id;
}

/** Pool items that can be the character base or an Anointment. */
export function characterChoices(
  inventory: Equipment[],
  field: CharacterField,
  definitions: Pick<Catalog, "specializations" | "perks">,
): Equipment[] {
  return inventory.filter((item) => isCharacterPart(definitions, item.id, field));
}

const properties = shallowRef<GemProperty[]>([]);
let request: Promise<GemProperty[]> | null = null;

/** Spell Gem properties, loaded on first use. */
export function useGemProperties() {
  request ??= gemProperties().then((value) => (properties.value = value));
  request.catch(() => (request = null));
  return properties;
}

/** The label a gem property shows with its chosen variant. */
export function propertyLabel(list: GemProperty[], item: Equipment, id: string): string {
  const property = list.find((p) => p.id === id);
  const variant = property?.variants.find((v) => v.id === item.property_variants?.[id]);
  return variant?.label || property?.name || t("editors.properties");
}

export interface ArtifactEffect {
  id: string;
  name: string;
  description: string;
  segments: { text: string }[];
  label: string | null;
  rank: null;
}

/** The Trick and Spell Slot effects of an Artifact, labelled with value or cast chance. */
export function artifactEffects(config: ArtifactConfig, catalog: Catalog): ArtifactEffect[] {
  const described = (
    definition: { id: string; name: string; segments: { text: string }[] } | undefined,
    label: string | null,
  ): ArtifactEffect | null =>
    definition
      ? {
          id: definition.id,
          name: definition.name,
          segments: definition.segments,
          description: joinSegments(definition.segments),
          label,
          rank: null,
        }
      : null;
  return [
    ...(config.tricks ?? []).map((id) => {
      const property = catalog.artifact_properties.find((d) => d.id === id);
      return described(property, property ? artifactValueText(property.formula) : null);
    }),
    ...(config.spell
      ? [
          described(
            catalog.spells.find((s) => s.id === config.spell),
            artifactTrigger[config.type || "Sword"] ?? null,
          ),
        ]
      : []),
  ].filter((e): e is ArtifactEffect => !!e?.description);
}
