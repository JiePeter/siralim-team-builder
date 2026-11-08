import { computed } from "vue";
import { createSharedComposable } from "@vueuse/core";
import { storeToRefs } from "pinia";
import {
  equipmentAt as equipmentIn,
  fieldLabels,
  type CharacterField,
  type Position,
  type SlotField,
} from "@/domain/assembly";
import { placementRefusal, traitSwap, type TraitSwap } from "@/domain/placement";
import { isCharacterPart, itemId } from "@/domain/team";
import { t } from "@/i18n";
import { useTeamStore } from "@/stores/team";
import { fieldFits } from "./assembly";
import { component } from "./components";
import { dragged, draggedSelection, type Selection } from "./dragging";
import { selected } from "./tray";

/** What the item being dragged or chosen for placing may do on each field and tile of the team. */
export const usePlacing = createSharedComposable(() => {
  const { team, index } = storeToRefs(useTeamStore());

  const equipmentAt = (at: Position) => equipmentIn(team.value, at.slot, at.field, at.index);

  const characterAt = (field: CharacterField, position: number) =>
    field === "characterBase"
      ? team.value.character.specialization
      : team.value.character.anointments[position];

  /** What a tray item or placed gear selection holds. */
  const selectionItem = (selection: { uid: string } | Position) =>
    "uid" in selection
      ? team.value.inventory.find((i) => i.uid === selection.uid)
      : equipmentAt(selection);

  /** The component being dragged, or else the one chosen for placing. */
  const placingSelection = computed(() => (dragged.value ? draggedSelection() : selected.value));
  /** The team slot being dragged to another position. */
  const movingMember = computed(() => {
    const s = placingSelection.value;
    return s && "member" in s ? s.member : null;
  });
  const placing = computed(() => {
    const s = placingSelection.value;
    if (!s || "member" in s) return null;
    if ("character" in s) return characterAt(s.character, s.position) ?? null;
    return itemId(selectionItem(s)) ?? null;
  });
  const placingKind = computed(() => (placing.value ? component(placing.value)?.kind : undefined));
  /** A configured Artifact stays an Artifact; other creatures, traits and materials move as their trait. */
  const placingConfigured = computed(() => {
    const s = placingSelection.value;
    if (!s || "character" in s || "member" in s) return false;
    const item = selectionItem(s);
    return typeof item === "object" && !!item.artifact;
  });

  /** Whether the item being placed is the kind a field holds. */
  function fits(field: SlotField): boolean {
    if (!placing.value || !index.value) return false;
    const from = placingSelection.value;
    if (from && "slot" in from && from.field === "nether" && field !== "nether") return false;
    return fieldFits(index.value, placing.value, placingKind.value, placingConfigured.value, field);
  }
  /** Why the selection cannot go into `target`, or null when it can. */
  function refusal(target: Position, selection: Selection, id: string): string | null {
    const source = "slot" in selection ? selection : undefined;
    return index.value ? placementRefusal(index.value, team.value, target, id, source) : null;
  }
  /** Whether the item being placed may go into `target`. */
  function allowed(target: Position): boolean {
    const s = placingSelection.value;
    return !!s && !!placing.value && refusal(target, s, placing.value) === null;
  }
  /** The Trait exchange a drop of the placed gear on `target` makes. */
  function swapping(target: Position): TraitSwap | null {
    const s = placingSelection.value;
    return s && "slot" in s && index.value ? traitSwap(index.value, team.value, s, target) : null;
  }
  function accepts(target: Position): boolean | null {
    if (movingMember.value !== null) return false;
    if (!placing.value) return null;
    return allowed(target) && (fits(target.field) || !!swapping(target));
  }
  function fieldHint(target: Position): string | null {
    return swapping(target) && allowed(target) ? t("build.swap") : null;
  }
  /** The field of a creature's slot that the item being placed goes to when dropped on its tile. */
  function tileField(slot: number): SlotField | null {
    if (!placing.value) return null;
    if (!team.value.slots[slot]!.base && fits("base")) return "base";
    if (fits("fusion")) return allowed({ slot, field: "fusion" }) ? "fusion" : null;
    return (
      (["artifact", "spells", "relic"] as const).find(
        (f) => fits(f) && allowed({ slot, field: f }),
      ) ?? null
    );
  }
  /** What dropping on a tile does, shown over the tile while a drag is held over it. */
  function tileHint(i: number): string | null {
    if (!acceptsMember(i)) return null;
    if (movingMember.value !== null) return t("build.swap");
    const field = tileField(i);
    if (field && swapping({ slot: i, field })) return t("build.swap");
    return field === "fusion" ? t("build.fuse") : field && fieldLabels[field];
  }
  /**
   * A tile takes another team slot to swap with, a creature as its Primary when it has none, and
   * gear for its creature when it has one.
   */
  function acceptsMember(i: number): boolean | null {
    if (movingMember.value !== null) return movingMember.value !== i;
    if (!placing.value) return null;
    const s = placingSelection.value;
    if (s && "slot" in s && s.slot === i) return false;
    return tileField(i) !== null;
  }
  function acceptsCharacter(field: CharacterField): boolean | null {
    if (movingMember.value !== null) return false;
    if (!placing.value) return null;
    return !!index.value && isCharacterPart(index.value.catalog, placing.value, field);
  }

  return {
    accepts,
    acceptsCharacter,
    acceptsMember,
    characterAt,
    equipmentAt,
    fieldHint,
    refusal,
    selectionItem,
    tileField,
    tileHint,
  };
});
