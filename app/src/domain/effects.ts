import { artifactValueText } from "./artifact";
import { slotTraits } from "./placement";
import { fieldLabels } from "./assembly";
import {
  characterEffects,
  itemId,
  type CharacterEffects,
  type EquipmentRef,
  type Slot,
  type TeamIndex,
} from "./team";
import { get, isDict, truthy, unique, type Dict } from "./values";

export interface EffectText {
  name: string;
  description: string;
}

/** Name and effect text of an object, from its page in the data pack; undefined when not loaded. */
export type EffectTexts = (id: string) => EffectText | undefined;

export interface ActiveEffect extends EffectText {
  id: string;
  context: string;
  rank?: number;
}

export interface BuildEffects extends CharacterEffects {
  active_effects: ActiveEffect[];
  notices: string[];
}

/** Effects active in a team: character Perks, then per slot traits, artifact, Relic and Spell Gems. */
export function buildEffects(index: TeamIndex, team: unknown, texts: EffectTexts): BuildEffects {
  const plan = team as Dict;
  const character = characterEffects(index, get(plan, "character", {}));
  const effects: ActiveEffect[] = character.effects
    .filter((e) => e.active)
    .map((e) => ({
      id: e.id,
      name: e.name,
      description: e.description,
      context: "Character · " + e.mode,
      rank: e.rank,
    }));
  const notices = character.effects.filter((e) => !e.active).map((e) => e.inactive_reason);

  function add(key: unknown, context: string) {
    const text = typeof key === "string" ? texts(key) : undefined;
    if (text) effects.push({ id: key as string, ...text, context });
  }

  const properties = new Map(index.catalog.artifact_properties.map((p) => [p.id, p.formula]));
  const slots = plan.slots as Dict[];
  slots.forEach((slot, i) => {
    const at = `Slot ${i + 1} · `;
    for (const { field, trait } of slotTraits(index, slot as Slot))
      add(trait, at + fieldLabels[field]);
    const artifact = get(slot, "artifact");
    if (isDict(artifact)) {
      const configuration = get(artifact, "artifact", {}) as Dict;
      if (truthy(configuration.spell)) add(configuration.spell, at + "Artifact Spell Slot");
      const entries = [
        ...(get(configuration, "stats", []) as string[]),
        ...(get(configuration, "tricks", []) as string[]),
      ];
      for (const entry of entries) {
        const formula = properties.get(entry);
        add(entry, `${at}Artifact${formula ? " " + artifactValueText(formula) : ""}`);
      }
    }
    const relic = get(slot, "relic");
    if (truthy(relic)) {
      const rank = isDict(relic) ? (get(relic, "rank", 1) as number) : 1;
      const definition = index.relics.get(itemId(relic as EquipmentRef)!);
      for (const effect of definition?.effects ?? []) {
        if (effect.rank <= rank) {
          effects.push({
            id: definition!.id,
            name: definition!.name,
            description: effect.description,
            context: `${at}Relic Rank ${effect.rank}`,
          });
        }
      }
    }
    for (const gem of get(slot, "spells", []) as unknown[])
      add(itemId(gem as EquipmentRef), at + fieldLabels.spells);
  });
  if (character.specialization === "Pariah" && slots.filter((s) => truthy(s.base)).length > 3) {
    notices.push("Pariah: at most three creatures");
  }
  return { ...character, active_effects: effects, notices: unique(notices) };
}
