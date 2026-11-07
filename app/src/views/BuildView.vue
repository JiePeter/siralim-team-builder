<script setup lang="ts">
import { computed, nextTick, ref, toRaw, useId, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useEventListener, useFileDialog, useMediaQuery, useStorage, useSwipe } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { assetUrl, object, type Carrier } from "@/data";
import { BLANK_ARTIFACT, useTeamStore } from "@/stores/team";
import {
  fieldLabels,
  isListField,
  type CharacterField,
  type Position,
  type SlotField,
} from "@/domain/assembly";
import { buildEffects } from "@/domain/effects";
import {
  avatarCheck,
  AVATAR_RACE,
  gemNotices,
  NO_CARRIER,
  placementRefusal,
  repeatedTraits,
  slotTraits,
  traitSwap,
  unstackedTraits,
  replacementNotices,
  type TraitSwap,
} from "@/domain/placement";
import {
  asItem,
  characterEffects,
  isCharacterPart,
  itemId,
  NETHER_TRAITS,
  type ArtifactConfig,
  type Equipment,
  type EquipmentRef,
} from "@/domain/team";
import ArtifactEditor from "@/components/ArtifactEditor.vue";
import CarrierPicker from "@/components/CarrierPicker.vue";
import CellPlate from "@/components/CellPlate.vue";
import CharacterEditor from "@/components/CharacterEditor.vue";
import CharacterPanel from "@/components/CharacterPanel.vue";
import DropZone from "@/components/DropZone.vue";
import EditorActions from "@/components/EditorActions.vue";
import EquipmentLine from "@/components/EquipmentLine.vue";
import EquipmentRow from "@/components/EquipmentRow.vue";
import FieldPicker from "@/components/FieldPicker.vue";
import FloatingMenu from "@/components/FloatingMenu.vue";
import GemEditor from "@/components/GemEditor.vue";
import ModalDialog from "@/components/ModalDialog.vue";
import ObjectCell from "@/components/ObjectCell.vue";
import PreviewDialog from "@/components/PreviewDialog.vue";
import RelicEditor from "@/components/RelicEditor.vue";
import TraitCell from "@/components/TraitCell.vue";
import {
  BLEND,
  fieldFits,
  fieldKinds,
  propertyLabel,
  slotIndex,
  useGemProperties,
} from "@/components/assembly";
import { component, loadComponent } from "@/components/components";
import { spriteOf } from "@/components/presentation";
import { draggedSelection, dragged, useDragSource, type Selection } from "@/components/dragging";
import { attempt, toast, toastError } from "@/components/toast";
import { t } from "@/i18n";
import { placementLabel, selected, startPlacing } from "@/components/tray";

/** `from` is the dialog to return to when this one closes without a choice. */
type Dialog = (
  | { type: "pool"; target: Position }
  | { type: "carrier"; target: Position; uid: string; kind: string; options: Carrier[] }
  | { type: "character"; field: CharacterField; position: number }
  | { type: "gem"; at: Position }
  | { type: "copy"; at: Position }
  | { type: "artifact"; slot: number }
  | { type: "relic"; slot: number }
  | { type: "perks" }
) & { from?: Dialog };

const store = useTeamStore();
const { team, index, trayCount } = storeToRefs(store);
const shareTray = ref(false);
const shareMenu = useId();
const sharing = ref(false);
const teamsMenu = useId();
const teamsOpen = ref(false);
const fileMenu = useId();
const fileOpen = ref(false);
const route = useRoute();
const router = useRouter();
const drag = useDragSource();
const gemProperties = useGemProperties();
store.rules();

const openSlot = ref(0);
/** On a wider screen, whether a slot is open below the sheet; the Traits table shows otherwise. */
const slotOpen = ref(false);
const phone = useMediaQuery("(max-width: 767px)");
/** On a phone a slot or the character opens as its own page, so Back closes it. */
const page = computed(() => (phone.value ? route.query.page : undefined));
const showNether = useStorage("siralim-planner.show-nether", false);
const fields = computed(() =>
  showNether.value
    ? (["base", "fusion", "artifact", "nether", "relic"] as const)
    : (["base", "fusion", "artifact", "relic"] as const),
);
const TRAIT_FIELDS = ["base", "fusion", "artifact"] as const;
const dialog = ref<Dialog | null>(null);
const preview = ref<Equipment | null>(null);
/** Remakes the Artifact editor after an Undo, so it shows the restored Artifact. */
const artifactVersion = ref(0);
const notesField = ref<HTMLTextAreaElement | null>(null);
// A phone can discard a hidden page before its field loses focus.
useEventListener(document, "visibilitychange", () => {
  if (document.hidden) notesField.value?.blur();
});

watch(
  () => route.query.slot,
  (value) => {
    const n = Number(value);
    if (n >= 1 && n <= 6) {
      openSlot.value = n - 1;
      slotOpen.value = !phone.value;
    }
  },
  { immediate: true },
);
const showSlot = computed(() => (phone.value ? page.value === "slot" : slotOpen.value));
const showTraits = computed(() => (phone.value ? !page.value : !slotOpen.value));

const characterModal = ref(false);
/** The Character and Notes dialog; on a phone it follows the route, so Back closes it. */
const characterOpen = computed({
  get: () => (phone.value ? page.value === "character" : characterModal.value),
  set: (value) => {
    if (phone.value) {
      if (!value && page.value === "character") closePage();
    } else characterModal.value = value;
  },
});
// Removing a focused field skips its change event, so a pending note saves first.
watch(characterOpen, (value) => {
  if (!value) notesField.value?.blur();
});

const dialogOpen = computed({
  get: () => dialog.value !== null,
  set: (value) => {
    if (!value) dialog.value = dialog.value?.from ?? null;
  },
});
const kindOf = (id: string) => index.value?.kinds.get(id);
const slot = computed(() => team.value.slots[openSlot.value]!);
const characterSummary = computed(() => {
  const at = index.value;
  if (!at) return "";
  const capacity = characterEffects(at, team.value.character).anointment_capacity;
  return `${specializationName.value || t("build.noSpecialization")} · ${team.value.character.anointments.length}/${capacity}`;
});
const avatars = computed(() =>
  index.value
    ? avatarCheck(index.value, team.value, (id) => component(id)?.attrs?.race_id === AVATAR_RACE)
    : null,
);
const unstacked = computed(() => (index.value ? unstackedTraits(index.value, team.value) : []));
const traitName = (trait: string) => component(trait)?.name ?? t("build.aTrait");
const NAMES_LISTED = 3;
const nameList = (ids: string[]) => {
  const names = ids.map(traitName);
  const separator = t("build.nameSeparator");
  if (names.length <= NAMES_LISTED) return names.join(separator);
  return t("build.nameList", {
    names: names.slice(0, NAMES_LISTED).join(separator),
    count: names.length - NAMES_LISTED,
  });
};
const replaced = computed(() =>
  index.value ? replacementNotices(index.value, toRaw(team.value)) : [],
);
/** Each notice with the slots it marks; a team-wide one marks none. */
const notices = computed<{ text: string; slots: number[] }[]>(() => [
  ...(index.value ? buildEffects(index.value, toRaw(team.value), () => undefined).notices : []).map(
    (text) => ({ text, slots: [] }),
  ),
  ...unstacked.value.map(({ trait, slots }) => ({
    text: t("build.unstacked", { trait: traitName(trait), n: slotIndex(slots[0]!) }),
    slots: slots.slice(1),
  })),
  ...replaced.value.map(({ owner, listeners, certain }) => ({
    text: t(certain ? "build.replacedCertain" : "build.replacedPossible", {
      owner: traitName(owner),
      listeners: nameList(listeners),
    }),
    slots: [],
  })),
  ...team.value.slots.flatMap((s, i) =>
    !s.base && (s.fusion || s.artifact || s.relic || s.spells?.length)
      ? [{ text: t("build.noPrimary", { n: slotIndex(i) }), slots: [i] }]
      : [],
  ),
  ...(avatars.value?.notice ? [{ text: avatars.value.notice, slots: avatars.value.slots }] : []),
  ...(index.value
    ? gemNotices(
        team.value,
        (id) => component(id)?.attrs?.class,
        blended.value,
        index.value.rules.spell_gems,
      )
    : []
  ).map(({ slot, message }) => ({
    text: t("build.slotNotice", { n: slotIndex(slot), message }),
    slots: [slot],
  })),
]);
const noticesOpen = ref(false);
const slotNotices = (i: number) => notices.value.filter((n) => n.slots.includes(i));
const overAvatar = (i: number) => !!avatars.value?.notice && avatars.value.slots.includes(i);

/** Each slot's Fusion and Artifact traits that repeat one the creature already has. */
const repeats = computed(() =>
  index.value ? team.value.slots.map((s) => repeatedTraits(index.value!, s)) : [],
);
const repeatNotice = (trait: string) =>
  t("build.repeatNotice", { trait: component(trait)?.name ?? t("build.thisTrait") });
function fieldWarning(at: number, field: SlotField) {
  return field === "base" && overAvatar(at) ? avatars.value!.notice : repeatWarning(at, field);
}
function repeatWarning(at: number, field: SlotField) {
  const found = repeats.value[at]?.find((r) => r.field === field);
  if (found) return repeatNotice(found.trait);
  const trait =
    index.value &&
    slotTraits(index.value, team.value.slots[at]!).find((t) => t.field === field)?.trait;
  const shared = unstacked.value.find((u) => u.trait === trait && u.slots[0] !== at);
  return shared
    ? t("build.unstacked", { trait: traitName(shared.trait), n: slotIndex(shared.slots[0]!) })
    : null;
}

function equipmentAt(at: Position) {
  const s = team.value.slots[at.slot];
  return isListField(at.field) ? s?.[at.field]?.[at.index ?? 0] : s?.[at.field];
}

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
  if ("uid" in s) return team.value.inventory.find((i) => i.uid === s.uid)?.id ?? null;
  if ("character" in s)
    return s.character === "characterBase"
      ? team.value.character.specialization
      : (team.value.character.anointments[s.position] ?? null);
  return itemId(equipmentAt(s)) ?? null;
});
const placingKind = computed(() => (placing.value ? component(placing.value)?.kind : undefined));
/** A configured Artifact stays an Artifact; other creatures, traits and materials move as their trait. */
const placingConfigured = computed(() => {
  const s = placingSelection.value;
  if (!s || "character" in s || "member" in s) return false;
  const item = "uid" in s ? team.value.inventory.find((i) => i.uid === s.uid) : equipmentAt(s);
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

/** A fused creature takes its Fusion parent's class unless the team carries Blend. */
const blended = computed(() => {
  const at = index.value;
  return (
    !!at && team.value.slots.some((s) => slotTraits(at, s).some(({ trait }) => trait === BLEND))
  );
});

const cells = computed(() =>
  team.value.slots.map((s, i) => {
    const base = s.base ? component(itemId(s.base)!) : undefined;
    const fusion = s.base && s.fusion && !blended.value ? component(itemId(s.fusion)!) : null;
    const others =
      (["fusion", "artifact", "relic"] as const).filter((f) => s[f]).length +
      (s.spells?.length ?? 0) +
      (s.nether?.length ?? 0);
    const first = s.fusion ?? s.artifact ?? s.relic ?? s.spells?.[0];
    const label = base ? base.name : others ? t("build.items", others) : "";
    return {
      index: i,
      label,
      notices: slotNotices(i).map((n) => n.text),
      sprite: s.base && base && spriteOf(base, 0) ? assetUrl(spriteOf(base, 0)!) : null,
      data: base ?? (first ? component(itemId(first)!) : null),
      classFrom: fusion,
      vacant: !s.base && !others,
    };
  }),
);

/** Names the slot both ways, by number and by its creature, with the field. */
function fieldTitle(at: Position) {
  const creature = component(itemId(team.value.slots[at.slot]?.base) ?? "")?.name;
  return [slotIndex(at.slot), creature, fieldLabels[at.field]].filter(Boolean).join(" · ");
}

const dialogTitle = computed(() => {
  const d = dialog.value;
  if (!d) return "";
  switch (d.type) {
    case "pool":
      return fieldTitle(d.target);
    case "carrier":
      return d.kind === "creature" ? t("build.selectCreature") : t("build.selectMaterial");
    case "character":
      return placementLabel({ character: d.field, position: d.position });
    case "gem":
      return t("build.spellGem");
    case "copy":
      return t("build.copyTo");
    case "artifact":
      return fieldTitle({ slot: d.slot, field: "artifact" });
    case "relic":
      return fieldTitle({ slot: d.slot, field: "relic" });
    case "perks":
      return t("build.specialization");
  }
  return "";
});
const specializationKey = computed(
  () =>
    index.value?.catalog.specializations.find((s) => s.id === team.value.character.specialization)
      ?.key ?? "",
);
const specializationName = computed(
  () =>
    index.value?.catalog.specializations.find((s) => s.id === team.value.character.specialization)
      ?.name ?? "",
);

async function install(uid: string, target: Position, resolvedId: string) {
  await store.install(uid, target, resolvedId);
  selected.value = null;
  dialog.value = null;
}

/** Offer to undo what ran since `mark` was taken. */
function offerUndo(mark: () => () => void, text: string, after?: () => void) {
  const undo = mark();
  toast(text, {
    label: t("build.undo"),
    run: () =>
      attempt(() => {
        undo();
        after?.();
      }),
  });
}

/** Run a placement into `target`; when that takes a filled field's occupant out, it can be undone. */
async function placingOver(target: Position, swap: boolean, run: () => unknown, next?: () => void) {
  const occupied = isListField(target.field) && target.index === undefined;
  const occupant = occupied ? undefined : itemId(equipmentAt(target));
  const mark = store.restorePoint();
  await run();
  next?.();
  // The toast joins the dialog on screen, which `next` may have just closed.
  await nextTick();
  if (!occupant || itemId(equipmentAt(target)) === occupant) return;
  const name = occupant === BLANK_ARTIFACT ? t("build.artifact") : component(occupant)?.name;
  offerUndo(mark, swap ? t("build.swapped") : t("build.wentToTray", { name }));
}

function placeWithUndo(target: Position, selection: Selection | null = selected.value) {
  const swap =
    !!selection && "slot" in selection && !!traitSwap(index.value!, team.value, selection, target);
  return placingOver(target, swap, () => place(target, selection));
}

/** What a tap on a field does: with something chosen it places it, otherwise it opens the field. */
function openField(target: Position) {
  if (selected.value) return attempt(() => placeWithUndo(target));
  const filled = !!equipmentAt(target);
  if (target.field === "artifact") dialog.value = { type: "artifact", slot: target.slot };
  else if (target.field === "relic" && filled) dialog.value = { type: "relic", slot: target.slot };
  else if (target.field === "spells" && target.index !== undefined && filled)
    dialog.value = { type: "gem", at: target };
  else dialog.value = { type: "pool", target };
}

/** Open the picker for a filled field from its editor; closing it returns to the editor. */
function replaceFrom(target: Position) {
  dialog.value = { type: "pool", target, from: dialog.value ?? undefined };
}

/** A choice in a field that has an editor continues into it. */
function afterPick(target: Position) {
  if (dialog.value?.type === "carrier") return;
  if (target.field === "relic") dialog.value = { type: "relic", slot: target.slot };
  else if (target.field === "spells")
    dialog.value = {
      type: "gem",
      at: {
        slot: target.slot,
        field: "spells",
        index: target.index ?? (team.value.slots[target.slot]!.spells?.length ?? 1) - 1,
      },
    };
  else dialog.value = null;
}

/**
 * Put the chosen or dragged item into a field, replacing what is there; placed gear exchanges
 * Traits with a filled Trait field instead.
 */
async function place(target: Position, selection: Selection | null = selected.value) {
  if (!selection) return;
  if ("character" in selection || "member" in selection) throw new Error(t("build.onlyGear"));
  const moving =
    "uid" in selection
      ? team.value.inventory.find((i) => i.uid === selection.uid)?.id
      : itemId(equipmentAt(selection));
  const refused = moving && refusal(target, selection, moving);
  if (refused) throw new Error(refused);
  if ("slot" in selection) {
    if (selection.slot === target.slot && selection.field === target.field) {
      selected.value = null;
      return;
    }
    const swap = traitSwap(index.value!, team.value, selection, target);
    if (swap) {
      await store.swapTraits(swap);
      selected.value = null;
      return;
    }
    const item = equipmentAt(selection);
    if (!item) throw new Error(t("build.componentMoved"));
    const data = await loadComponent(itemId(item)!);
    if (!fieldKinds(index.value!.rules.slot_kinds)[target.field].includes(data.kind)) {
      // A creature moving into an Artifact, or a material into a creature field, goes as its trait.
      const next = await store.unequip(selection);
      selected.value = null;
      return place(target, { uid: next.inventory.at(-1)!.uid });
    }
    await store.move(selection, target);
    selected.value = null;
    return;
  }
  const item = team.value.inventory.find((i) => i.uid === selection.uid);
  if (!item) throw new Error(t("build.componentMoved"));
  const data = await loadComponent(item.id);
  if (data.kind !== "trait" || target.field === "nether") return install(item.uid, target, data.id);
  const kind =
    target.field === "artifact"
      ? "material"
      : target.field === "base" || target.field === "fusion"
        ? "creature"
        : null;
  const options = (await object(item.id)).options.filter((o) => o.kind === kind);
  if (!options.length) throw new Error(NO_CARRIER);
  if (options.length === 1) return install(item.uid, target, options[0]!.id);
  dialog.value = { type: "carrier", target, uid: item.uid, kind: kind!, options };
}

async function placeCharacter(
  field: CharacterField,
  position: number,
  selection: Selection | null = selected.value,
) {
  if (!selection) {
    if (field === "characterBase" && team.value.character.specialization)
      dialog.value = { type: "perks" };
    else dialog.value = { type: "character", field, position };
    return;
  }
  if (!("uid" in selection)) {
    if (!("character" in selection)) throw new Error(t("build.selectCharacterPart"));
    selected.value = null;
    return;
  }
  selected.value = null;
  await overCharacter(
    field,
    position,
    () => store.placeCharacterPart(selection.uid, field, position),
    () => (dialog.value = field === "characterBase" ? { type: "perks" } : null),
  );
}

const characterAt = (field: CharacterField, position: number) =>
  field === "characterBase"
    ? team.value.character.specialization
    : team.value.character.anointments[position];

/** Run a change to a character part; when it takes a filled part out, it can be undone. */
async function overCharacter(
  field: CharacterField,
  position: number,
  run: () => unknown,
  next?: () => void,
) {
  const occupant = characterAt(field, position);
  const mark = store.restorePoint();
  await run();
  next?.();
  await nextTick();
  if (occupant && characterAt(field, position) !== occupant)
    offerUndo(mark, t("build.wentToTray", { name: component(occupant)?.name }));
}

function pickPool(uid: string) {
  const d = dialog.value;
  if (d?.type !== "pool") return;
  attempt(() =>
    placingOver(
      d.target,
      false,
      () => place(d.target, { uid }),
      () => afterPick(d.target),
    ),
  );
}

function takePool(id: string) {
  const d = dialog.value;
  if (d?.type !== "pool") return;
  attempt(() =>
    placingOver(
      d.target,
      false,
      () => store.take(id, d.target),
      () => afterPick(d.target),
    ),
  );
}

function pickCarrier(option: Carrier) {
  const d = dialog.value;
  if (d?.type !== "carrier") return;
  attempt(() =>
    placingOver(
      d.target,
      false,
      () => install(d.uid, d.target, option.id),
      () => afterPick(d.target),
    ),
  );
}

/** A Specialization goes to its field, an Anointment to the next free one. */
function dropOnCharacter() {
  const specialization = acceptsCharacter("characterBase");
  const part = dropped();
  return specialization
    ? placeCharacter("characterBase", 0, part)
    : placeCharacter("characterAnointment", team.value.character.anointments.length, part);
}

function pickCharacter(uid: string) {
  const d = dialog.value;
  if (d?.type === "character") attempt(() => placeCharacter(d.field, d.position, { uid }));
}

function takeCharacter(id: string) {
  const d = dialog.value;
  if (d?.type !== "character") return;
  attempt(() =>
    overCharacter(
      d.field,
      d.position,
      () => store.takeCharacterPart(id, d.field, d.position),
      () => (dialog.value = d.field === "characterBase" ? { type: "perks" } : null),
    ),
  );
}

async function placeOnTile(target: number) {
  const field = tileField(target);
  const selection = dragged.value ? dropped() : selected.value;
  if (!selection) return;
  if (!("member" in selection)) {
    if (!field) throw new Error(t("build.doesNotFit"));
    openSlot.value = target;
    // A Primary moving to an empty slot takes its whole slot with it.
    if ("slot" in selection && selection.field === "base" && field === "base") {
      selected.value = null;
      return store.swapSlots(selection.slot, target);
    }
    return placeWithUndo({ slot: target, field }, selection);
  }
  selected.value = null;
  if (selection.member === target) return;
  await store.swapSlots(selection.member, target);
  if (openSlot.value === selection.member) openSlot.value = target;
  else if (openSlot.value === target) openSlot.value = selection.member;
}

function tapTile(i: number) {
  const moving = selected.value && "member" in selected.value ? selected.value.member : null;
  if (moving === i) selected.value = null;
  else if (selected.value && acceptsMember(i)) attempt(() => placeOnTile(i));
  else if (phone.value) openSlotPage(i);
  else showSlotPanel(i);
}

/** Beside the sheet the open slot is in the route too, so it survives a trip to Search. */
function showSlotPanel(i: number) {
  openSlot.value = i;
  slotOpen.value = true;
  router.replace({ query: { slot: String(i + 1) } });
}

function openSlotPage(i: number) {
  router.push({ query: { slot: String(i + 1), page: "slot" } });
}

function closeSlot() {
  if (phone.value) return closePage();
  slotOpen.value = false;
  if (route.query.slot) router.replace({ query: {} });
}

/** Placing happens on the sheet; Cancel comes back to the slot page and dialog it started from. */
function placeFromHere(selection: Selection) {
  const from = dialog.value;
  const slot = page.value === "slot" ? openSlot.value : null;
  startPlacing(selection, async () => {
    if (slot !== null) await router.push({ query: { slot: String(slot + 1), page: "slot" } });
    dialog.value = from;
  });
  dialog.value = null;
  if (slot !== null) closePage();
}

async function sendToTray(at: Position) {
  if (await attempt(() => store.unequip(at))) dialog.value = null;
}

async function sendCharacterToTray(field: CharacterField, position: number) {
  if (await attempt(() => store.removeCharacterPart(field, position))) dialog.value = null;
}

const SLOT_COUNT = 6;
const SWIPE_COMMIT = 72;
const slotPage = ref<HTMLElement | null>(null);
/** The side the slot on screen came in from; empty when it was opened directly. */
const enteredFrom = ref<"left" | "right" | "">("");
const slotAfter = (delta: number) => (openSlot.value + delta + SLOT_COUNT) % SLOT_COUNT;
const {
  isSwiping,
  lengthX,
  direction: swipeDirection,
} = useSwipe(slotPage, {
  threshold: 16,
  onSwipeEnd(_, direction) {
    if (direction !== "left" && direction !== "right") return;
    if (Math.abs(lengthX.value) < SWIPE_COMMIT) return;
    const forward = direction === "left";
    enteredFrom.value = forward ? "right" : "left";
    router.replace({ query: { slot: String(slotAfter(forward ? 1 : -1) + 1), page: "slot" } });
  },
});
const swipeOffset = computed(() =>
  isSwiping.value && ["left", "right"].includes(swipeDirection.value) ? -lengthX.value * 0.6 : 0,
);

function closePage() {
  if (router.options.history.state.back) router.back();
  else router.replace({ query: {} });
}

function dropped() {
  const selection = draggedSelection();
  dragged.value = null;
  return selection;
}

/** The other slots with a Primary, which can take a copy of the gear. */
const copySlots = computed(() =>
  team.value.slots.flatMap((s, i) => (s.base && i !== openSlot.value ? [i] : [])),
);
function copyTargets(at: Position) {
  const id = itemId(equipmentAt(at));
  return copySlots.value.map((i) => {
    const target = team.value.slots[i]!;
    const occupant = !isListField(at.field) && itemId(target[at.field]);
    const gems = at.field === "spells" ? (target.spells?.length ?? 0) : 0;
    const held = occupant
      ? t("build.replaces", {
          name: occupant === BLANK_ARTIFACT ? t("build.artifact") : component(occupant)?.name,
        })
      : gems
        ? t("build.spellGemCount", gems)
        : "";
    return {
      slot: i,
      data: component(itemId(target.base)!),
      line: [t("build.slot", { n: slotIndex(i) }), held].filter(Boolean).join(" · "),
      refused:
        id && index.value
          ? placementRefusal(index.value, team.value, { slot: i, field: at.field }, id)
          : null,
    };
  });
}

async function copyGear(at: Position, slot: number, refused: string | null) {
  if (refused) return toastError(refused);
  const undo = await attempt(() => store.copyTo(at, { slot, field: at.field }));
  if (!undo) return;
  dialog.value = null;
  toast(t("build.copiedTo", { n: slotIndex(slot) }), {
    label: t("build.undo"),
    run: () => attempt(undo),
  });
}

function applyGem(properties: string[], variants: Record<string, number>) {
  const d = dialog.value;
  if (d?.type === "gem") attempt(() => store.setGem(d.at, properties, variants));
}

function applyArtifact(item: Equipment, configuration: ArtifactConfig, taken: string | null) {
  const d = dialog.value;
  if (d?.type !== "artifact") return;
  const before = itemId(team.value.slots[d.slot]?.artifact);
  const mark = store.restorePoint();
  attempt(async () => {
    await store.setArtifact(d.slot, item, configuration, taken);
    if (before && before !== BLANK_ARTIFACT && before !== item.id)
      offerUndo(
        mark,
        t("build.wentToTray", { name: component(before)?.name }),
        () => artifactVersion.value++,
      );
  });
}

function applyRelic(id: string, rank: number) {
  const d = dialog.value;
  if (d?.type === "relic") attempt(() => store.setRelic(d.slot, id, rank));
}

async function share() {
  const url = await store.shareUrl(shareTray.value && trayCount.value > 0);
  if (navigator.share) {
    await navigator.share({ title: team.value.name, url }).catch(() => {});
    return;
  }
  await navigator.clipboard.writeText(url);
  toast(t("build.linkCopied"));
}

async function copyPlannerLink() {
  await navigator.clipboard.writeText(await store.plannerLink());
  toast(t("build.linkCopied"));
}

async function importPlanner() {
  const text = prompt(t("build.plannerPrompt"));
  if (!text) return;
  const dropped = await store.importPlannerLink(text);
  if (dropped) toast(t("build.plannerDropped", { n: dropped }));
}

function clearSlot() {
  const i = openSlot.value;
  if (confirm(t("build.confirmClearSlot", { n: slotIndex(i) }))) attempt(() => store.clearSlot(i));
}

function clearCharacter() {
  if (confirm(t("build.confirmClearCharacter"))) attempt(() => store.clearCharacter());
}

function removeTeam() {
  if (confirm(t("build.confirmDeleteTeam", { name: team.value.name }))) store.deleteTeam();
}

function exportTeam() {
  const link = document.createElement("a");
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(team.value, null, 2)], { type: "application/json" }),
  );
  link.href = url;
  link.download = "siralim-team.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const {
  open: chooseImport,
  onChange: onImportChosen,
  reset: resetImport,
} = useFileDialog({ accept: "application/json,.json", multiple: false });
onImportChosen(async (files) => {
  const file = files?.[0];
  if (!file) return;
  await attempt(async () => {
    if (file.size > 100000) throw new Error(t("build.fileTooLarge"));
    const imported: unknown = JSON.parse(await file.text());
    if (confirm(t("build.confirmImport", { name: team.value.name, file: file.name })))
      await store.replace(imported);
  });
  resetImport();
});

const gemAt = (d: Dialog) => (d.type === "gem" ? asItem(equipmentAt(d.at)!) : null);
const relicOf = (s: number) => {
  const relic = team.value.slots[s]?.relic;
  return { id: itemId(relic) ?? "", rank: (relic && asItem(relic).rank) || 1 };
};
const artifactOf = (s: number) => {
  const artifact = team.value.slots[s]?.artifact;
  return artifact ? asItem(artifact) : null;
};
const propertyCount = (gem: EquipmentRef) => asItem(gem).properties?.length ?? 0;
const gemLine = (gem: EquipmentRef) =>
  (asItem(gem).properties ?? [])
    .map((id) => propertyLabel(gemProperties.value, asItem(gem), id))
    .join(" · ") || null;
const netherAt = (slot: number, position: number) => ({
  slot,
  field: "nether" as const,
  index: position,
});
const gemPosition = (position: number): Position => ({
  slot: openSlot.value,
  field: "spells",
  index: position,
});
const gemAtSlot = (slot: number, position: number): Position => ({
  slot,
  field: "spells",
  index: position,
});
/** Two rows of two keys on a card: the Relic, then Spell Gems up to the usual three. */
const GEM_KEYS = 3;
const gearGems = (slot: number) => {
  const gems = team.value.slots[slot]!.spells ?? [];
  return gems.length > GEM_KEYS
    ? { shown: gems.slice(0, GEM_KEYS - 1), hidden: gems.length - GEM_KEYS + 1 }
    : { shown: gems, hidden: 0 };
};
const relicRank = (relic: EquipmentRef) => String(asItem(relic).rank || 1);
const specialization = computed(() => team.value.character.specialization);
/** Anointments the Character row has room for; the rest are on the Character page. */
const ANOINTMENT_KEYS = 5;
const anointmentCapacity = computed(() =>
  index.value ? characterEffects(index.value, team.value.character).anointment_capacity : 0,
);
function openCharacter(field: CharacterField, position: number) {
  attempt(() => placeCharacter(field, position));
}

/** The field a dialog is about and what is in it, to lead the page with. */
const dialogField = computed<Position | null>(() =>
  dialog.value?.type === "pool" ? dialog.value.target : null,
);
const currentItem = computed(() => {
  const at = dialogField.value;
  const item = at && equipmentAt(at);
  return item ? asItem(item) : null;
});
const currentCharacter = computed(() => {
  const d = dialog.value;
  if (d?.type !== "character") return null;
  return characterAt(d.field, d.position) ?? null;
});
/** A field can swap with another that holds a Trait. */
const canSwap = (at: Position) => ["base", "fusion"].includes(at.field) && !!equipmentAt(at);
const dialogWarning = computed(() => {
  const d = dialog.value;
  if (d?.type === "pool" && !isListField(d.target.field))
    return fieldWarning(d.target.slot, d.target.field);
  return d?.type === "artifact" ? fieldWarning(d.slot, "artifact") : null;
});
</script>

<template>
  <section class="team" :aria-label="$t('build.title')">
    <div class="team-head">
      <input
        class="team-title"
        :aria-label="$t('build.teamName')"
        maxlength="200"
        :value="team.name"
        @change="attempt(() => store.rename(($event.target as HTMLInputElement).value))"
      />
      <button
        type="button"
        class="icon-button teams-key"
        :aria-label="$t('build.teams')"
        :title="$t('build.teams')"
        aria-haspopup="menu"
        :aria-expanded="teamsOpen"
        :popovertarget="teamsMenu"
      >
        <i class="icon icon-down"></i>
      </button>
      <FloatingMenu
        :id="teamsMenu"
        v-slot="{ close }"
        v-model:open="teamsOpen"
        :label="$t('build.teams')"
      >
        <button
          v-for="(name, i) in store.teams"
          :key="i"
          type="button"
          role="menuitemradio"
          :aria-checked="i === store.activeTeam"
          @click="
            close();
            store.openTeam(i);
          "
        >
          <span>{{ name }}</span
          ><i v-if="i === store.activeTeam" class="icon icon-check menu-mark"></i>
        </button>
        <hr />
        <button
          type="button"
          role="menuitem"
          @click="
            close();
            store.createTeam();
          "
        >
          <i class="icon icon-plus"></i>{{ $t("build.newTeam") }}
        </button>
        <button
          type="button"
          role="menuitem"
          @click="
            close();
            removeTeam();
          "
        >
          <i class="icon icon-trash"></i>{{ $t("build.deleteTeam") }}
        </button>
      </FloatingMenu>
      <div v-if="!phone" class="view-tabs" role="tablist" :aria-label="$t('build.view')">
        <button
          type="button"
          class="view-tab"
          role="tab"
          :aria-selected="!slotOpen"
          @click="closeSlot"
        >
          {{ $t("build.traits") }}
        </button>
        <button
          type="button"
          class="view-tab"
          role="tab"
          :aria-selected="slotOpen"
          @click="showSlotPanel(openSlot)"
        >
          {{ $t("build.slots") }}
        </button>
      </div>
      <button
        v-if="notices.length && !(phone && selected)"
        type="button"
        class="notices-toggle"
        :aria-expanded="noticesOpen"
        @click="noticesOpen = !noticesOpen"
      >
        {{
          notices.length === 1
            ? $t("build.noticeOne")
            : $t("build.noticeMany", { count: notices.length })
        }}
        <i :class="['icon', noticesOpen ? 'icon-up' : 'icon-down']"></i>
      </button>
      <DropZone
        v-if="!phone"
        :accepts="acceptsCharacter('characterBase') || acceptsCharacter('characterAnointment')"
        @drop="attempt(() => dropOnCharacter())"
      >
        <button
          type="button"
          class="character-key"
          :title="$t('build.characterAndNotes')"
          @click="characterModal = true"
        >
          <i class="icon icon-character"></i>{{ $t("build.character") }}
        </button>
      </DropZone>
      <button
        type="button"
        class="icon-button share-key"
        :aria-label="$t('build.shareLink')"
        :title="$t('build.shareLink')"
        :aria-haspopup="trayCount ? 'dialog' : undefined"
        :aria-expanded="trayCount ? sharing : undefined"
        :popovertarget="trayCount ? shareMenu : undefined"
        @click="trayCount || attempt(share)"
      >
        <i class="icon icon-share"></i>
      </button>
      <FloatingMenu
        v-if="trayCount"
        :id="shareMenu"
        v-slot="{ close }"
        v-model:open="sharing"
        role="dialog"
        :label="$t('build.shareLink')"
      >
        <label><input v-model="shareTray" type="checkbox" />{{ $t("build.includeTray") }}</label>
        <button
          type="button"
          class="primary"
          @click="
            close();
            attempt(share);
          "
        >
          {{ $t("build.share") }}
        </button>
      </FloatingMenu>
      <button
        type="button"
        class="icon-button more-key"
        :aria-label="$t('build.more')"
        :title="$t('build.more')"
        aria-haspopup="menu"
        :aria-expanded="fileOpen"
        :popovertarget="fileMenu"
      >
        <i class="icon icon-more"></i>
      </button>
      <FloatingMenu
        :id="fileMenu"
        v-slot="{ close }"
        v-model:open="fileOpen"
        :label="$t('build.more')"
      >
        <button
          type="button"
          role="menuitemcheckbox"
          :aria-checked="showNether"
          @click="
            close();
            showNether = !showNether;
          "
        >
          <span>{{ $t("build.netherStones") }}</span
          ><i v-if="showNether" class="icon icon-check menu-mark"></i>
        </button>
        <hr />
        <button
          type="button"
          role="menuitem"
          @click="
            close();
            exportTeam();
          "
        >
          {{ $t("build.exportTeam") }}
        </button>
        <button
          type="button"
          role="menuitem"
          @click="
            close();
            chooseImport();
          "
        >
          {{ $t("build.importTeam") }}
        </button>
        <hr />
        <button
          type="button"
          role="menuitem"
          @click="
            close();
            attempt(copyPlannerLink);
          "
        >
          {{ $t("build.copyPlannerLink") }}
        </button>
        <button
          type="button"
          role="menuitem"
          @click="
            close();
            attempt(importPlanner);
          "
        >
          {{ $t("build.importPlannerLink") }}
        </button>
      </FloatingMenu>
    </div>
    <div v-if="noticesOpen && notices.length" class="build-notices">
      <ul>
        <li v-for="notice in notices" :key="notice.text">{{ notice.text }}</li>
      </ul>
    </div>
    <div :class="['slots', { 'traits-shown': showTraits, 'nether-shown': showNether }]">
      <div class="creature-slots">
        <div class="slot-sheet" role="group" :aria-label="$t('build.teamSlots')">
          <div v-for="cell in cells" :key="cell.index" class="slot-column">
            <DropZone
              class="slot-drop"
              :accepts="acceptsMember(cell.index)"
              :hint="tileHint(cell.index)"
              @drop="attempt(() => placeOnTile(cell.index))"
            >
              <ObjectCell
                tag="button"
                layout="tile"
                :class="[
                  'slot-cell',
                  {
                    vacant: cell.vacant,
                    next: cell.index === cells.findIndex((c) => c.vacant),
                    'over-limit': overAvatar(cell.index),
                    noticed: cell.notices.length,
                  },
                ]"
                :data="showTraits ? null : cell.data"
                :class-from="cell.classFrom"
                :aria-pressed="phone ? undefined : slotOpen && cell.index === openSlot"
                :aria-label="
                  [
                    cell.label
                      ? $t('build.slotNamed', { n: slotIndex(cell.index), label: cell.label })
                      : $t('build.slot', { n: slotIndex(cell.index) }),
                    ...cell.notices,
                  ].join('. ')
                "
                :title="[cell.label, ...cell.notices].filter(Boolean).join('\n') || undefined"
                type="button"
                v-bind="cell.vacant ? {} : drag({ member: cell.index })"
                @click="tapTile(cell.index)"
              >
                <template #index
                  ><span class="cell-index">{{ slotIndex(cell.index) }}</span></template
                >
                <template v-if="cell.label" #label>{{ cell.label }}</template>
              </ObjectCell>
            </DropZone>
            <template v-if="showTraits">
              <img
                v-if="cell.sprite"
                class="slot-backdrop"
                :src="cell.sprite"
                alt=""
                aria-hidden="true"
              />
              <TraitCell
                v-for="field in TRAIT_FIELDS"
                :key="field"
                :at="{ slot: cell.index, field }"
                :value="team.slots[cell.index]![field]"
                :next="field === 'base' && cell.index === cells.findIndex((c) => c.vacant)"
                :accepts="accepts({ slot: cell.index, field })"
                :hint="fieldHint({ slot: cell.index, field })"
                :warning="fieldWarning(cell.index, field)"
                @place="openField({ slot: cell.index, field })"
                @drop="attempt(() => placeWithUndo({ slot: cell.index, field }, dropped()))"
                @inspect="openField({ slot: cell.index, field })"
              />
              <div v-if="showNether" class="nether-band">
                <TraitCell
                  v-for="(trait, position) in team.slots[cell.index]!.nether ?? []"
                  :key="asItem(trait).uid || position"
                  :at="netherAt(cell.index, position)"
                  :value="trait"
                  :next="false"
                  :accepts="accepts(netherAt(cell.index, position))"
                  :hint="null"
                  :warning="null"
                  @place="openField(netherAt(cell.index, position))"
                  @drop="attempt(() => placeWithUndo(netherAt(cell.index, position), dropped()))"
                  @inspect="openField(netherAt(cell.index, position))"
                />
                <TraitCell
                  v-if="(team.slots[cell.index]!.nether?.length ?? 0) < NETHER_TRAITS"
                  :at="netherAt(cell.index, team.slots[cell.index]!.nether?.length ?? 0)"
                  :value="undefined"
                  :next="false"
                  :accepts="accepts({ slot: cell.index, field: 'nether' })"
                  :hint="null"
                  :warning="null"
                  @place="openField({ slot: cell.index, field: 'nether' })"
                  @drop="
                    attempt(() => placeWithUndo({ slot: cell.index, field: 'nether' }, dropped()))
                  "
                  @inspect="() => {}"
                />
              </div>
              <div v-if="phone" class="gear-keys">
                <DropZone :accepts="accepts({ slot: cell.index, field: 'relic' })">
                  <button
                    type="button"
                    class="gear-key"
                    :aria-label="
                      [
                        $t('build.relic'),
                        team.slots[cell.index]!.relic &&
                          component(itemId(team.slots[cell.index]!.relic)!)?.name,
                      ]
                        .filter(Boolean)
                        .join(': ')
                    "
                    @click="openField({ slot: cell.index, field: 'relic' })"
                  >
                    <CellPlate
                      v-if="
                        team.slots[cell.index]!.relic &&
                        component(itemId(team.slots[cell.index]!.relic)!)
                      "
                      compact
                      :data="component(itemId(team.slots[cell.index]!.relic)!)!"
                      :corner="relicRank(team.slots[cell.index]!.relic!)"
                    />
                    <template v-else
                      ><i class="icon icon-plus"></i>{{ $t("build.relic") }}</template
                    >
                  </button>
                </DropZone>
                <DropZone
                  v-for="(gem, position) in gearGems(cell.index).shown"
                  :key="asItem(gem).uid || position"
                  :accepts="accepts({ slot: cell.index, field: 'spells' })"
                >
                  <button
                    type="button"
                    class="gear-key"
                    :aria-label="
                      [$t('build.spellGem'), component(itemId(gem)!)?.name]
                        .filter(Boolean)
                        .join(': ')
                    "
                    @click="openField(gemAtSlot(cell.index, position))"
                  >
                    <CellPlate
                      v-if="component(itemId(gem)!)"
                      compact
                      :data="component(itemId(gem)!)!"
                      :properties="propertyCount(gem)"
                    />
                  </button>
                </DropZone>
                <button
                  v-if="gearGems(cell.index).hidden"
                  type="button"
                  class="gear-key gear-more"
                  :aria-label="$t('build.gemsMore', { count: gearGems(cell.index).hidden })"
                  @click="openSlotPage(cell.index)"
                >
                  +{{ gearGems(cell.index).hidden }}
                </button>
                <DropZone
                  v-else-if="gearGems(cell.index).shown.length < GEM_KEYS"
                  :accepts="accepts({ slot: cell.index, field: 'spells' })"
                >
                  <button
                    type="button"
                    class="gear-key"
                    :aria-label="$t('build.spellGem')"
                    @click="openField({ slot: cell.index, field: 'spells' })"
                  >
                    <i class="icon icon-plus"></i>{{ $t("build.spellGem") }}
                  </button>
                </DropZone>
              </div>
            </template>
          </div>
        </div>
        <div v-if="phone" class="character-row">
          <button
            type="button"
            class="character-entry"
            @click="router.push({ query: { page: 'character' } })"
          >
            <strong>{{ $t("build.character") }}</strong>
            <span>{{ characterSummary }}</span>
          </button>
          <DropZone :accepts="acceptsCharacter('characterBase')">
            <button
              type="button"
              class="gear-key"
              :aria-label="$t('build.specialization')"
              @click="openCharacter('characterBase', 0)"
            >
              <CellPlate
                v-if="specialization && component(specialization)"
                compact
                :data="component(specialization)!"
              />
              <i v-else class="icon icon-plus"></i>
            </button>
          </DropZone>
          <DropZone
            v-for="position in Math.min(anointmentCapacity, ANOINTMENT_KEYS)"
            :key="position"
            :accepts="acceptsCharacter('characterAnointment')"
          >
            <button
              type="button"
              class="gear-key"
              :aria-label="$t('editors.anointment', { position })"
              @click="openCharacter('characterAnointment', position - 1)"
            >
              <CellPlate
                v-if="
                  team.character.anointments[position - 1] &&
                  component(team.character.anointments[position - 1]!)
                "
                compact
                :data="component(team.character.anointments[position - 1]!)!"
              />
              <i v-else class="icon icon-plus"></i>
            </button>
          </DropZone>
        </div>
        <section
          v-if="showSlot"
          :ref="(el) => (slotPage = phone ? (el as HTMLElement | null) : null)"
          :class="['slot', 'open-slot', { 'phone-page': phone }]"
          :aria-label="$t('build.slot', { n: openSlot + 1 })"
        >
          <h2>
            <button
              v-if="phone"
              type="button"
              class="page-back"
              :aria-label="$t('build.backToTeam')"
              @click="closeSlot"
            >
              <i class="icon icon-left"></i>
            </button>
            <span class="slot-name">{{
              phone ? slotIndex(openSlot) : $t("build.slot", { n: slotIndex(openSlot) })
            }}</span>
            <span v-if="cells[openSlot]!.label" class="slot-creature">
              <strong>{{ cells[openSlot]!.label }}</strong>
              <small v-if="slot.base">{{
                traitName(slotTraits(index!, slot)[0]?.trait ?? "")
              }}</small>
            </span>
            <span v-if="phone" class="slot-pips" aria-hidden="true">
              <i
                v-for="cell in cells"
                :key="cell.index"
                :class="{ current: cell.index === openSlot, vacant: cell.vacant }"
              ></i>
            </span>
            <button
              v-if="phone && !cells[openSlot]!.vacant"
              type="button"
              class="labelled-key"
              @click="placeFromHere({ member: openSlot })"
            >
              <i class="icon icon-move"></i>{{ $t("editors.keys.move") }}
            </button>
            <button
              v-if="!cells[openSlot]!.vacant"
              type="button"
              class="clear"
              :aria-label="$t('build.clearSlot')"
              :title="$t('build.clearSlot')"
              @click="clearSlot"
            >
              <i class="icon icon-trash"></i>
            </button>
          </h2>
          <div v-if="slotNotices(openSlot).length" class="build-notices slot-notices">
            <ul>
              <li v-for="notice in slotNotices(openSlot)" :key="notice.text">{{ notice.text }}</li>
            </ul>
          </div>
          <span v-if="swipeOffset" :class="['swipe-peek', swipeOffset < 0 ? 'right' : 'left']">
            {{ $t("build.slot", { n: slotIndex(slotAfter(swipeOffset < 0 ? 1 : -1)) }) }}
          </span>
          <div
            :key="openSlot"
            :class="['slot-body', enteredFrom && `from-${enteredFrom}`]"
            :style="swipeOffset ? { transform: `translateX(${swipeOffset}px)` } : undefined"
          >
            <template v-for="field in fields" :key="field">
              <DropZone
                v-if="field === 'nether'"
                class="gem-area nether-area"
                :accepts="accepts({ slot: openSlot, field })"
                @drop="attempt(() => placeWithUndo({ slot: openSlot, field }, dropped()))"
              >
                <small>{{ $t("build.nether") }}</small>
                <div
                  v-for="(trait, position) in slot.nether ?? []"
                  :key="asItem(trait).uid || position"
                  v-bind="drag(netherAt(openSlot, position))"
                  class="gem equipped"
                  @click="openField(netherAt(openSlot, position))"
                >
                  <EquipmentLine :data="component(itemId(trait)!)">
                    <template #menu>
                      <button
                        type="button"
                        class="icon-button"
                        :aria-label="$t('build.backToTrayNamed', { item: $t('build.nether') })"
                        :title="$t('build.backToTray')"
                        @click="attempt(() => store.unequip(netherAt(openSlot, position)))"
                      >
                        <i class="icon icon-undo"></i>
                      </button>
                    </template>
                  </EquipmentLine>
                </div>
                <button
                  v-if="(slot.nether?.length ?? 0) < NETHER_TRAITS"
                  type="button"
                  class="drop-target"
                  @click="openField({ slot: openSlot, field })"
                >
                  <i class="icon icon-plus"></i>{{ $t("build.nether") }}
                </button>
              </DropZone>
              <EquipmentRow
                v-else
                :at="{ slot: openSlot, field }"
                :value="slot[field]"
                :accepts="accepts({ slot: openSlot, field })"
                :hint="fieldHint({ slot: openSlot, field })"
                :next="field === 'base' && !slot.base"
                :copyable="copySlots.length > 0"
                :warning="fieldWarning(openSlot, field)"
                @place="openField({ slot: openSlot, field })"
                @drop="attempt(() => placeWithUndo({ slot: openSlot, field }, dropped()))"
                @inspect="openField({ slot: openSlot, field })"
                @copy="dialog = { type: 'copy', at: { slot: openSlot, field } }"
                @remove="attempt(() => store.unequip({ slot: openSlot, field }))"
              />
            </template>
            <DropZone
              class="gem-area"
              :accepts="accepts({ slot: openSlot, field: 'spells' })"
              @drop="attempt(() => placeWithUndo({ slot: openSlot, field: 'spells' }, dropped()))"
            >
              <small>{{ $t("build.spellGems") }}</small>
              <div
                v-for="(gem, position) in slot.spells ?? []"
                :key="asItem(gem).uid || position"
                v-bind="drag(gemPosition(position))"
                class="gem equipped"
                @click="
                  selected
                    ? attempt(() => placeWithUndo({ slot: openSlot, field: 'spells' }))
                    : openField(gemPosition(position))
                "
              >
                <EquipmentLine
                  :data="component(itemId(gem)!)"
                  :line="gemLine(gem)"
                  :properties="propertyCount(gem)"
                >
                  <template #menu>
                    <button
                      v-if="copySlots.length"
                      type="button"
                      class="icon-button"
                      :aria-label="$t('build.copyNamed', { item: $t('build.spellGem') })"
                      :title="$t('build.copy')"
                      @click="dialog = { type: 'copy', at: gemPosition(position) }"
                    >
                      <i class="icon icon-copy"></i>
                    </button>
                    <button
                      type="button"
                      class="icon-button"
                      :aria-label="$t('build.backToTrayNamed', { item: $t('build.spellGem') })"
                      :title="$t('build.backToTray')"
                      @click="attempt(() => store.unequip(gemPosition(position)))"
                    >
                      <i class="icon icon-undo"></i>
                    </button>
                  </template>
                </EquipmentLine>
              </div>
              <button
                type="button"
                class="drop-target"
                @click="openField({ slot: openSlot, field: 'spells' })"
              >
                <i class="icon icon-plus"></i>{{ $t("build.spellGem") }}
              </button>
            </DropZone>
          </div>
        </section>
      </div>
    </div>

    <ModalDialog
      v-if="index"
      v-model:open="characterOpen"
      class="character-dialog"
      :title="$t('build.character')"
      routed
    >
      <CharacterPanel
        :character="team.character"
        :index="index"
        :accepts="acceptsCharacter"
        @place="(field, position) => attempt(() => placeCharacter(field, position))"
        @drop="(field, position) => attempt(() => placeCharacter(field, position, dropped()))"
        @remove="(field, position) => attempt(() => store.removeCharacterPart(field, position))"
        @perks="dialog = { type: 'perks' }"
        @clear="clearCharacter"
      />
      <section class="notes-panel" :aria-label="$t('build.notes')">
        <h3>{{ $t("build.notes") }}</h3>
        <textarea
          ref="notesField"
          :aria-label="$t('build.teamNotes')"
          maxlength="10000"
          rows="6"
          :value="team.notes"
          @change="attempt(() => store.setNotes(($event.target as HTMLTextAreaElement).value))"
        ></textarea>
      </section>
    </ModalDialog>

    <ModalDialog
      v-model:open="dialogOpen"
      :title="dialogTitle"
      :sheet="dialog?.type === 'carrier' || dialog?.type === 'copy'"
    >
      <div v-if="dialogWarning" class="build-notices field-notice">
        <ul>
          <li>{{ dialogWarning }}</li>
        </ul>
      </div>
      <div v-if="dialog?.type === 'pool' && index" class="choices">
        <FieldPicker
          :field="dialog.target.field"
          :label="fieldLabels[dialog.target.field]"
          :team="team"
          :catalog="index.catalog"
          :kind-of="kindOf"
          :target="dialog.target"
          :replacing="!!currentItem"
          @pick="pickPool"
          @take="takePool"
        >
          <template #current>
            <div v-if="currentItem" class="picker-current">
              <EquipmentLine :data="component(currentItem.id)">
                <template #menu>
                  <button type="button" class="labelled-key" @click="preview = currentItem">
                    <i class="icon icon-eye"></i>{{ $t("editors.keys.details") }}
                  </button>
                  <button
                    v-if="canSwap(dialog.target)"
                    type="button"
                    class="labelled-key"
                    @click="placeFromHere(dialogField!)"
                  >
                    <i class="icon icon-replace"></i>{{ $t("editors.keys.swap") }}
                  </button>
                  <button type="button" class="labelled-key" @click="sendToTray(dialogField!)">
                    <i class="icon icon-undo"></i>{{ $t("editors.keys.tray") }}
                  </button>
                </template>
              </EquipmentLine>
            </div>
          </template>
        </FieldPicker>
      </div>
      <CarrierPicker
        v-else-if="dialog?.type === 'carrier'"
        :options="dialog.options"
        @pick="pickCarrier"
      />
      <div v-else-if="dialog?.type === 'character' && index" class="choices">
        <FieldPicker
          :field="dialog.field"
          :label="
            dialog.field === 'characterBase' ? $t('build.specialization') : $t('build.anointment')
          "
          :team="team"
          :catalog="index.catalog"
          :kind-of="kindOf"
          :replacing="!!currentCharacter"
          @pick="pickCharacter"
          @take="takeCharacter"
        >
          <template #current>
            <div v-if="currentCharacter" class="picker-current">
              <EquipmentLine :data="component(currentCharacter)">
                <template #menu>
                  <button
                    type="button"
                    class="labelled-key"
                    @click="preview = { uid: '', id: currentCharacter! }"
                  >
                    <i class="icon icon-eye"></i>{{ $t("editors.keys.details") }}
                  </button>
                  <button
                    type="button"
                    class="labelled-key"
                    @click="
                      dialog?.type === 'character' &&
                      sendCharacterToTray(dialog.field, dialog.position)
                    "
                  >
                    <i class="icon icon-undo"></i>{{ $t("editors.keys.tray") }}
                  </button>
                </template>
              </EquipmentLine>
            </div>
          </template>
        </FieldPicker>
      </div>
      <div v-else-if="dialog?.type === 'copy'" class="choices">
        <button
          v-for="target in copyTargets(dialog.at)"
          :key="target.slot"
          type="button"
          class="choice copy-target"
          :aria-disabled="!!target.refused"
          @click="dialog?.type === 'copy' && copyGear(dialog.at, target.slot, target.refused)"
        >
          <EquipmentLine :data="target.data" :line="target.line" />
        </button>
      </div>
      <template v-else-if="dialog?.type === 'gem' && gemAt(dialog)">
        <EditorActions
          replace
          tray
          @replace="dialog?.type === 'gem' && replaceFrom(dialog.at)"
          @tray="dialog?.type === 'gem' && sendToTray(dialog.at)"
        />
        <GemEditor
          :item="gemAt(dialog)!"
          :properties="gemProperties"
          :compatible="index?.rules.property_compatibility[gemAt(dialog)!.id]"
          @apply="applyGem"
        />
      </template>
      <template v-else-if="dialog?.type === 'artifact' && index">
        <EditorActions
          :tray="!!artifactOf(dialog.slot)"
          @tray="
            dialog?.type === 'artifact' && sendToTray({ slot: dialog.slot, field: 'artifact' })
          "
        />
        <ArtifactEditor
          :key="artifactVersion"
          :item="artifactOf(dialog.slot)"
          :catalog="index.catalog"
          :team="team"
          :at-slot="dialog.slot"
          :kind-of="kindOf"
          @apply="applyArtifact"
        />
      </template>
      <template v-else-if="dialog?.type === 'relic' && index">
        <EditorActions
          replace
          tray
          @replace="dialog?.type === 'relic' && replaceFrom({ slot: dialog.slot, field: 'relic' })"
          @tray="dialog?.type === 'relic' && sendToTray({ slot: dialog.slot, field: 'relic' })"
        />
        <RelicEditor
          :id="relicOf(dialog.slot).id"
          :relics="[...index.relics.values()]"
          :rank="relicOf(dialog.slot).rank"
          @apply="applyRelic"
        />
      </template>
      <template v-else-if="dialog?.type === 'perks' && index">
        <EditorActions
          replace
          tray
          @replace="
            dialog = { type: 'character', field: 'characterBase', position: 0, from: dialog! }
          "
          @tray="sendCharacterToTray('characterBase', 0)"
        />
        <CharacterEditor
          :character="team.character"
          :specialization="specializationName"
          :royal="specializationKey === 'Royal'"
          :perks="index.perks"
          @apply="(character) => attempt(() => store.setCharacter(character))"
        />
      </template>
    </ModalDialog>
    <PreviewDialog v-model:item="preview" />
  </section>
</template>

<style scoped>
.team {
  display: grid;
  gap: var(--space-16);
  margin: 0 auto;
  padding: var(--gutter);
}
.team-head {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.team-title {
  flex: 0 1 auto;
  width: auto;
  min-width: 4ch;
  field-sizing: content;
  min-height: var(--row);
  padding: 0;
  background: transparent;
  border-color: transparent;
  box-shadow: none;
  font-size: var(--fs-24);
  font-weight: 700;
  text-overflow: ellipsis;
}
.team-title:hover {
  border-color: var(--line);
}
.teams-key {
  --key-line: transparent;
}
.teams-key:not(:hover, :active, [aria-expanded="true"]) {
  background-color: transparent;
}
.share-key,
.more-key {
  width: var(--field);
  min-width: var(--field);
  height: var(--field);
}
.character-key {
  min-height: var(--field);
}
.view-tabs {
  display: flex;
  gap: var(--space-8);
  margin-right: auto;
  margin-left: var(--space-8);
}
.view-tab {
  min-height: var(--field);
  padding: 0 var(--space-8);
  background: none;
  border: 0;
  border-bottom: 2px solid transparent;
  clip-path: none;
  color: var(--muted);
}
.view-tab:hover {
  background: none;
  color: var(--text);
}
.view-tab[aria-selected="true"] {
  border-bottom-color: var(--accent);
  color: var(--text);
  font-weight: 700;
}
.character-dialog :deep(.character-slot) {
  border: 0;
}
.notes-panel {
  padding: var(--space-8) var(--space-12) var(--space-12);
}
.notes-panel > h3 {
  margin: 0 0 var(--space-8);
}
.notes-panel > textarea {
  display: block;
  width: 100%;
  resize: vertical;
}
.build-notices {
  background: var(--danger-ground);
  border: 1px solid var(--danger-line);
  color: var(--danger-text);
  font-size: var(--fs-13);
}
.build-notices ul {
  margin: 0;
  padding: 0;
  list-style: none;
}
.build-notices li {
  padding: 8px 12px;
}
.build-notices li + li {
  border-top: 1px solid var(--danger-rule);
}
.notices-toggle {
  display: flex;
  flex: none;
  align-items: center;
  gap: var(--space-8);
  min-height: var(--field);
  padding: 0 var(--space-4) 0 var(--space-8);
  clip-path: none;
  background: none;
  border: 0;
  color: var(--danger-text);
  font-size: var(--fs-13);
  font-weight: 700;
}
.notices-toggle::after {
  content: "";
  order: 1;
  flex: none;
  width: 8px;
  height: 8px;
  background: var(--danger-mark);
}
.notices-toggle > .icon {
  order: 2;
}
.notices-toggle:hover {
  background: var(--danger-hover);
}
.slot-notices {
  border-width: 1px 0 0;
}
.slots {
  display: grid;
  gap: var(--space-16);
  align-content: start;
  min-width: 0;
}
.creature-slots {
  display: grid;
  align-content: start;
  gap: 8px;
  min-width: 0;
}
.slot-sheet {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.slot-cell {
  min-height: 120px;
}
.slot-cell .cell-index {
  position: absolute;
  top: 6px;
  left: 6px;
}
.slot-cell :deep(> .cell-label) {
  min-height: 16px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.slot-cell.vacant {
  justify-content: center;
  background: var(--cell);
}
.slot-cell.vacant:hover {
  background: var(--raised);
}
.slot-cell.vacant::after {
  content: "";
  width: 24px;
  height: 24px;
  background-color: var(--muted);
  -webkit-mask: var(--icon-plus) center / 24px 24px no-repeat;
  mask: var(--icon-plus) center / 24px 24px no-repeat;
}
.slot-cell.next::after {
  background-color: var(--accent);
}
.slot-cell[aria-pressed="true"] .cell-index {
  color: var(--text);
}
.slot-cell.over-limit {
  border-color: var(--danger-line);
}
.slot-cell.over-limit::before,
.slot-cell.noticed::before {
  content: "";
  position: absolute;
  top: 8px;
  right: 8px;
  width: 8px;
  height: 8px;
  background: var(--danger-mark);
}
.slot-drop {
  display: grid;
}
.slot-column {
  display: contents;
}
/* Each card spans the sheet's rows, so one field's Traits line up across the slots. */
.traits-shown .slot-column {
  position: relative;
  isolation: isolate;
  display: grid;
  grid-row: span 4;
  grid-template-rows: subgrid;
  row-gap: 0;
  min-width: 0;
  padding-bottom: var(--space-8);
  overflow: hidden;
  background: var(--cell);
}
/* The name shares the left edge of the Traits below. */
.traits-shown .slot-cell {
  flex-direction: row;
  align-items: baseline;
  justify-content: flex-start;
  gap: var(--space-8);
  min-height: var(--row);
  padding: 14px 7px 14px 11px;
  text-align: left;
}
.traits-shown .slot-cell :deep(> .cell-label) {
  flex: 0 1 auto;
  order: 1;
  min-width: 0;
  min-height: 0;
  font-size: var(--fs-15);
}
.traits-shown .slot-cell.noticed::before,
.traits-shown .slot-cell.over-limit::before {
  position: static;
  order: 2;
  flex: none;
  align-self: center;
}
.traits-shown .slot-cell .cell-index {
  position: static;
  order: 3;
  flex: none;
  margin-left: auto;
}
.traits-shown .slot-cell::after,
.traits-shown .slot-cell.vacant::after {
  content: "";
  order: 4;
  flex: none;
  align-self: center;
  width: 24px;
  height: 24px;
  background-color: var(--muted);
  -webkit-mask: var(--icon-right) center / 24px 24px no-repeat;
  mask: var(--icon-right) center / 24px 24px no-repeat;
}
/* 64px sprites at a whole 4x, faint enough that even a white pixel keeps the text over it readable. */
.slot-backdrop {
  position: absolute;
  z-index: -1;
  top: 50%;
  left: 50%;
  width: 256px;
  height: 256px;
  image-rendering: pixelated;
  opacity: 0.14;
  pointer-events: none;
  transform: translate(-50%, -50%);
}
.slot-column:nth-child(3n + 1) {
  --trait-label: block;
}
.nether-shown.traits-shown .slot-column {
  grid-row: span 5;
}
.nether-band {
  display: grid;
  align-content: start;
  min-width: 0;
  border-top: 1px dashed var(--strong);
}
.slot-name {
  font: 400 24px / 1 var(--pixel-font);
}
.copy-target {
  font-weight: 400;
}
.copy-target > :deep(.equipment-line) {
  flex: 1;
  min-width: 0;
}
.copy-target[aria-disabled="true"] {
  opacity: 0.45;
}
.slot-pips {
  display: flex;
  gap: var(--space-4);
}
.slot-pips > i {
  width: 6px;
  height: 6px;
  background: var(--muted);
}
.slot-pips > .vacant {
  background: transparent;
  box-shadow: inset 0 0 0 1px var(--muted);
}
.slot-pips > .current {
  background: var(--accent);
  box-shadow: none;
}
.open-slot.phone-page {
  overflow-x: hidden;
  touch-action: pan-y;
}
.swipe-peek {
  position: fixed;
  top: 40%;
  z-index: 3;
  color: var(--muted);
  font: 400 16px / 1 var(--pixel-font);
}
.swipe-peek.left {
  left: var(--space-8);
}
.swipe-peek.right {
  right: var(--space-8);
}
.slot-body.from-left {
  animation: slot-from-left 160ms var(--ease-out);
}
.slot-body.from-right {
  animation: slot-from-right 160ms var(--ease-out);
}
@keyframes slot-from-left {
  from {
    opacity: 0;
    transform: translateX(-32px);
  }
}
@keyframes slot-from-right {
  from {
    opacity: 0;
    transform: translateX(32px);
  }
}
.gem-area {
  row-gap: var(--space-16);
}
.gem-area > small {
  color: var(--text);
}
.character-row {
  display: flex;
  align-items: stretch;
  min-height: var(--row);
  background: var(--cell);
}
.character-entry {
  display: grid;
  flex: 1;
  align-content: center;
  justify-content: stretch;
  min-width: 0;
  padding: 0 var(--space-8);
  background: none;
  clip-path: none;
  text-align: left;
}
.character-entry > strong {
  color: var(--kind-character);
  font-size: var(--fs-13);
  line-height: 18px;
}
.gear-keys {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-top: 1px solid var(--line);
}
.gear-key {
  display: grid;
  width: 100%;
  min-width: 44px;
  height: 100%;
  min-height: 44px;
  padding: 2px;
  place-items: center;
  background: none;
  clip-path: none;
  font-size: var(--fs-12);
  line-height: 14px;
  --key-line: transparent;
}
.gear-more {
  color: var(--muted);
  font: 400 16px / 1 var(--pixel-font);
}
.slot-creature {
  display: grid;
  flex: 1;
  min-width: 0;
}
.slot-creature > * {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.slot-creature > small {
  color: var(--muted);
  font-size: var(--fs-13);
  font-weight: 400;
}
.picker-current {
  padding-bottom: var(--space-12);
}
.field-notice {
  border-width: 0 0 1px;
}
.character-entry > span {
  overflow: hidden;
  color: var(--muted);
  font-size: var(--fs-13);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.gem-area .over-limit {
  background: var(--danger-ground);
  border-color: var(--danger-line);
  color: var(--danger-text);
}

@media (min-width: 1100px) {
  .slot-sheet {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }
  .traits-shown .slot-sheet {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
/* Six cards in a row only where each still holds a readable measure. */
@media (min-width: 1900px) {
  .traits-shown .slot-sheet {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }
  .slot-column:nth-child(3n + 1) {
    --trait-label: none;
  }
  .slot-column:nth-child(6n + 1) {
    --trait-label: block;
  }
}
@media (max-width: 767px) {
  .team {
    gap: var(--space-8);
    padding: var(--space-4) var(--gutter) var(--space-24);
  }
  /* The four card rows and the gear keys, so the whole team fits one screen with its Character. */
  .traits-shown .slot-column {
    grid-row: span 5;
    padding-bottom: 0;
  }
  .nether-shown.traits-shown .slot-column {
    grid-row: span 6;
  }
  .traits-shown .slot-cell {
    align-items: center;
    gap: var(--space-4);
    min-height: 44px;
    padding: var(--space-4) 7px var(--space-4) 11px;
  }
  /* A long team name shortens before the keys move; the notices fill the second row. */
  .team-head {
    display: grid;
    grid-template-columns: minmax(0, max-content) auto minmax(0, 1fr) auto auto;
  }
  .share-key {
    grid-column: 4;
  }
  .more-key {
    grid-column: 5;
  }
  .notices-toggle {
    grid-column: 1 / -1;
    grid-row: 2;
    min-height: var(--control-compact);
    padding: 0 1px 0 11px;
    background: var(--danger-ground);
    border: 1px solid var(--danger-line);
  }
  .notices-toggle > .icon {
    margin-left: auto;
  }
  .traits-shown .slot-cell .cell-index {
    display: none;
  }
  .traits-shown .slot-cell::after,
  .traits-shown .slot-cell.vacant::after {
    width: 12px;
    height: 12px;
    margin-left: auto;
    -webkit-mask-size: 12px 12px;
    mask-size: 12px 12px;
  }
  .traits-shown .slot-cell :deep(> .cell-label) {
    font-size: var(--fs-13);
    white-space: normal;
  }
  .slot-backdrop {
    width: 128px;
    height: 128px;
    opacity: 0.22;
  }
}
</style>
