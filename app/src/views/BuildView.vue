<script setup lang="ts">
import { computed, ref, toRaw, useId, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useEventListener, useFileDialog, useMediaQuery, useSwipe } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { object, type Carrier } from "@/data";
import { useSearchStore } from "@/stores/search";
import { BLANK_ARTIFACT, useTeamStore } from "@/stores/team";
import type { Attributes } from "@/domain/attributes";
import {
  fieldLabels,
  gearRefusal,
  type CharacterField,
  type Position,
  type SlotField,
} from "@/domain/assembly";
import { buildEffects } from "@/domain/effects";
import {
  avatarCheck,
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
  carriersOf,
  characterEffects,
  isCharacterPart,
  itemId,
  type ArtifactConfig,
  type Equipment,
  type EquipmentRef,
} from "@/domain/team";
import ArtifactEditor from "@/components/ArtifactEditor.vue";
import CarrierPicker from "@/components/CarrierPicker.vue";
import CharacterEditor from "@/components/CharacterEditor.vue";
import CharacterPanel from "@/components/CharacterPanel.vue";
import DropZone from "@/components/DropZone.vue";
import EquipmentLine from "@/components/EquipmentLine.vue";
import EquipmentRow from "@/components/EquipmentRow.vue";
import FieldPicker from "@/components/FieldPicker.vue";
import FloatingMenu from "@/components/FloatingMenu.vue";
import GemEditor from "@/components/GemEditor.vue";
import ModalDialog from "@/components/ModalDialog.vue";
import ObjectCell from "@/components/ObjectCell.vue";
import PreviewDialog from "@/components/PreviewDialog.vue";
import RelicEditor from "@/components/RelicEditor.vue";
import {
  BLEND,
  carriedInto,
  fieldKinds,
  fieldKind,
  propertyLabel,
  type PickerField,
  slotIndex,
  useGemProperties,
} from "@/components/assembly";
import { component, loadComponent } from "@/components/components";
import { draggedSelection, dragged, useDragSource, type Selection } from "@/components/dragging";
import { attempt, toast, toastError } from "@/components/toast";
import { placementLabel, selected } from "@/components/tray";

type Dialog =
  | { type: "pool"; target: Position }
  | { type: "carrier"; target: Position; uid: string; kind: string; options: Carrier[] }
  | { type: "character"; field: CharacterField; position: number }
  | { type: "gem"; at: Position }
  | { type: "copy"; at: Position }
  | { type: "artifact"; slot: number }
  | { type: "relic"; slot: number }
  | { type: "perks" };

const store = useTeamStore();
const { team, index, trayCount } = storeToRefs(store);
const shareTray = ref(false);
const shareMenu = useId();
const sharing = ref(false);
const teamsMenu = useId();
const teamsOpen = ref(false);
const search = useSearchStore();
const route = useRoute();
const router = useRouter();
const drag = useDragSource();
const gemProperties = useGemProperties();
store.rules();

const openSlot = ref(0);
const phone = useMediaQuery("(max-width: 767px)");
/** On a phone a slot or the character opens as its own page, so Back closes it. */
const page = computed(() => (phone.value ? route.query.page : undefined));
const FIELDS = ["base", "fusion", "artifact", "relic"] as const;
const dialog = ref<Dialog | null>(null);
const preview = ref<Equipment | null>(null);
const notesField = ref<HTMLTextAreaElement | null>(null);
// A phone can discard a hidden page before its field loses focus.
useEventListener(document, "visibilitychange", () => {
  if (document.hidden) notesField.value?.blur();
});

watch(
  () => route.query.slot,
  (value) => {
    const n = Number(value);
    if (n >= 1 && n <= 6) openSlot.value = n - 1;
  },
  { immediate: true },
);

const dialogOpen = computed({
  get: () => dialog.value !== null,
  set: (value) => {
    if (!value) dialog.value = null;
  },
});
const kindOf = (id: string) => index.value?.kinds.get(id);
const slot = computed(() => team.value.slots[openSlot.value]!);
/** A slot without a Primary holds nothing else, so only filled fields stay beside it. */
const shownFields = computed(() =>
  FIELDS.filter((f) => f === "base" || slot.value.base || slot.value[f]),
);
const characterSummary = computed(() => {
  const at = index.value;
  if (!at) return "";
  const capacity = characterEffects(at, team.value.character).anointment_capacity;
  return `${specializationName.value || "No Specialization"} · ${team.value.character.anointments.length}/${capacity}`;
});
const avatars = computed(() =>
  index.value
    ? avatarCheck(index.value, team.value, (id) => component(id)?.attrs?.race === "Avatar")
    : null,
);
const unstacked = computed(() => (index.value ? unstackedTraits(index.value, team.value) : []));
const traitName = (trait: string) => component(trait)?.name ?? "A Trait";
const NAMES_LISTED = 3;
const nameList = (ids: string[]) => {
  const names = ids.map(traitName);
  if (names.length <= NAMES_LISTED) return names.join(", ");
  return `${names.slice(0, NAMES_LISTED).join(", ")} and ${names.length - NAMES_LISTED} more`;
};
const replaced = computed(() =>
  index.value ? replacementNotices(index.value, toRaw(team.value)) : [],
);
const notices = computed(() => [
  ...(index.value ? buildEffects(index.value, toRaw(team.value), () => undefined).notices : []),
  ...unstacked.value.map(
    ({ trait, slots }) =>
      `${traitName(trait)} does not stack: only Slot ${slotIndex(slots[0]!)} counts`,
  ),
  ...replaced.value.map(
    ({ owner, listeners, certain }) =>
      `${traitName(owner)} ${certain ? "stops" : "can stop"} ${nameList(listeners)}`,
  ),
  ...(avatars.value?.notice ? [avatars.value.notice] : []),
  ...(index.value
    ? gemNotices(
        team.value,
        (id) => component(id)?.attrs?.class,
        blended.value,
        index.value.rules.spell_gems,
      )
    : []
  ).map(({ slot, message }) => `Slot ${slotIndex(slot)}: ${message}`),
]);
const NOTICES_SHOWN = 3;
const allNotices = ref(false);
const shownNotices = computed(() =>
  allNotices.value ? notices.value : notices.value.slice(0, NOTICES_SHOWN),
);
const overAvatar = (i: number) => !!avatars.value?.notice && avatars.value.slots.includes(i);

/** Each slot's Fusion and Artifact traits that repeat one the creature already has. */
const repeats = computed(() =>
  index.value ? team.value.slots.map((s) => repeatedTraits(index.value!, s)) : [],
);
const repeatNotice = (trait: string) =>
  `${component(trait)?.name ?? "This trait"} is already on this creature, so this copy has no effect`;
function repeatWarning(at: number, field: SlotField) {
  const found = repeats.value[at]?.find((r) => r.field === field);
  if (found) return repeatNotice(found.trait);
  const trait =
    index.value &&
    slotTraits(index.value, team.value.slots[at]!).find((t) => t.field === field)?.trait;
  const shared = unstacked.value.find((u) => u.trait === trait && u.slots[0] !== at);
  return shared
    ? `${traitName(shared.trait)} does not stack: only Slot ${slotIndex(shared.slots[0]!)} counts`
    : null;
}

function equipmentAt(at: Position) {
  const s = team.value.slots[at.slot];
  return at.field === "spells" ? s?.spells?.[at.index ?? 0] : s?.[at.field];
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
  if (!placing.value) return false;
  const carried =
    index.value && !placingConfigured.value ? carriersOf(index.value, placing.value) : null;
  if (carried && (carried.creature || carried.materials.length)) return carriedInto(carried, field);
  return (
    !!index.value &&
    fieldKinds(index.value.rules.slot_kinds)[field].includes(placingKind.value ?? "")
  );
}
/** Why the selection cannot go into `target`, or null when it can. */
function refusal(target: Position, selection: Selection, id: string): string | null {
  const source = "slot" in selection ? selection : undefined;
  return index.value
    ? placementRefusal(index.value, team.value, target, id, source)
    : gearRefusal(team.value, target, source);
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
function accepts(field: SlotField): boolean | null {
  if (movingMember.value !== null) return false;
  if (!placing.value) return null;
  const target = { slot: openSlot.value, field };
  return allowed(target) && (fits(field) || !!swapping(target));
}
function fieldHint(field: SlotField): string | null {
  const target = { slot: openSlot.value, field };
  return swapping(target) && allowed(target) ? "Swap" : null;
}
/** The field of a creature's slot that the item being placed goes to when dropped on its tile. */
function tileField(slot: number): SlotField | null {
  if (!placing.value) return null;
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
  if (movingMember.value !== null) return "Swap";
  const field = team.value.slots[i]!.base ? tileField(i) : "base";
  if (field && swapping({ slot: i, field })) return "Swap";
  return field === "fusion" ? "Fuse" : field && fieldLabels[field];
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
  return team.value.slots[i]!.base ? tileField(i) !== null : fits("base");
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
      (s.spells?.length ?? 0);
    const first = s.fusion ?? s.artifact ?? s.relic ?? s.spells?.[0];
    const label = base ? base.name : others ? `${others} ${others === 1 ? "item" : "items"}` : "";
    return {
      index: i,
      label,
      data: base ?? (first ? component(itemId(first)!) : null),
      classFrom: fusion,
      vacant: !s.base && !others,
    };
  }),
);

const dialogTitle = computed(() => {
  const d = dialog.value;
  if (!d) return "";
  switch (d.type) {
    case "pool":
      return placementLabel(d.target);
    case "carrier":
      return d.kind === "creature" ? "Select Creature" : "Select Material";
    case "character":
      return placementLabel({ character: d.field, position: d.position });
    case "gem":
      return "Spell Gem";
    case "copy":
      return "Copy to";
    case "artifact":
      return "Artifact";
    case "relic":
      return "Relic";
    case "perks":
      return "Specialization";
  }
  return "";
});
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

/**
 * Put the chosen or dragged item into a field, replacing what is there; placed gear exchanges
 * Traits with a filled Trait field instead. With nothing chosen an empty field opens its picker;
 * an occupied one is left alone.
 */
async function place(target: Position, selection: Selection | null = selected.value) {
  if (!selection) {
    if (target.field === "spells" || !equipmentAt(target)) dialog.value = { type: "pool", target };
    return;
  }
  if ("character" in selection || "member" in selection)
    throw new Error("Only gear goes in a slot field");
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
    if (!item) throw new Error("Component has moved");
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
  if (!item) throw new Error("Component has moved");
  const data = await loadComponent(item.id);
  if (data.kind !== "trait") return install(item.uid, target, data.id);
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
    const filled =
      field === "characterBase"
        ? team.value.character.specialization
        : team.value.character.anointments[position];
    if (!filled) dialog.value = { type: "character", field, position };
    return;
  }
  if (!("uid" in selection)) {
    if (!("character" in selection)) throw new Error("Select a Specialization or Anointment");
    selected.value = null;
    return;
  }
  await store.placeCharacterPart(selection.uid, field, position);
  selected.value = null;
  dialog.value = null;
}

function pickPool(uid: string) {
  const d = dialog.value;
  if (d?.type === "pool") attempt(() => place(d.target, { uid }));
}

async function takePool(id: string) {
  const d = dialog.value;
  if (d?.type !== "pool") return;
  if ((await attempt(() => store.take(id, d.target))) !== undefined) dialog.value = null;
}

function pickCarrier(option: Carrier) {
  const d = dialog.value;
  if (d?.type === "carrier") attempt(() => install(d.uid, d.target, option.id));
}

function pickCharacter(uid: string) {
  const d = dialog.value;
  if (d?.type === "character") attempt(() => placeCharacter(d.field, d.position, { uid }));
}

async function takeCharacter(id: string) {
  const d = dialog.value;
  if (d?.type !== "character") return;
  if ((await attempt(() => store.takeCharacterPart(id, d.field))) !== undefined)
    dialog.value = null;
}

async function placeOnTile(target: number) {
  const field = team.value.slots[target]!.base ? tileField(target) : "base";
  const selection = dragged.value ? dropped() : selected.value;
  if (!selection) return;
  if (!("member" in selection)) {
    if (!field) throw new Error("This does not fit the creature in this slot");
    openSlot.value = target;
    // A Primary moving to an empty slot takes its whole slot with it.
    if ("slot" in selection && selection.field === "base" && field === "base") {
      selected.value = null;
      return store.swapSlots(selection.slot, target);
    }
    return place({ slot: target, field }, selection);
  }
  if (selection.member === target) return;
  await store.swapSlots(selection.member, target);
  if (openSlot.value === selection.member) openSlot.value = target;
  else if (openSlot.value === target) openSlot.value = selection.member;
}

function tapTile(i: number) {
  if (selected.value && acceptsMember(i)) attempt(() => placeOnTile(i));
  else if (phone.value) router.push({ query: { slot: String(i + 1), page: "slot" } });
  else openSlot.value = i;
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

function configure(target: Position) {
  dialog.value = { type: target.field === "artifact" ? "artifact" : "relic", slot: target.slot };
}

function dropped() {
  const selection = draggedSelection();
  dragged.value = null;
  return selection;
}

function searchFor(field: PickerField, q = "", attributes: Attributes = {}) {
  dialog.value = null;
  search.browse(fieldKind[field], q, attributes);
  router.push({ name: "search" });
}

/** The other slots with a Primary, which can take a copy of the gear. */
const copySlots = computed(() =>
  team.value.slots.flatMap((s, i) => (s.base && i !== openSlot.value ? [i] : [])),
);
function copyTargets(at: Position) {
  const id = itemId(equipmentAt(at));
  return copySlots.value.map((i) => {
    const target = team.value.slots[i]!;
    const occupant = at.field !== "spells" && itemId(target[at.field]);
    const gems = at.field === "spells" ? (target.spells?.length ?? 0) : 0;
    const held = occupant
      ? `Replaces ${occupant === BLANK_ARTIFACT ? "Artifact" : component(occupant)?.name}`
      : gems
        ? `${gems} Spell ${gems === 1 ? "Gem" : "Gems"}`
        : "";
    return {
      slot: i,
      data: component(itemId(target.base)!),
      line: [`Slot ${slotIndex(i)}`, held].filter(Boolean).join(" · "),
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
  toast(`Copied to Slot ${slotIndex(slot)}`, { label: "Undo", run: () => attempt(undo) });
}

function applyGem(properties: string[], variants: Record<string, number>) {
  const d = dialog.value;
  if (d?.type === "gem") attempt(() => store.setGem(d.at, properties, variants));
}

function applyArtifact(item: Equipment, configuration: ArtifactConfig, taken: string | null) {
  const d = dialog.value;
  if (d?.type === "artifact") attempt(() => store.setArtifact(d.slot, item, configuration, taken));
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
  toast("Link copied");
}

function clearSlot() {
  const i = openSlot.value;
  if (confirm(`Send everything in Slot ${slotIndex(i)} to the tray?`))
    attempt(() => store.clearSlot(i));
}

function clearCharacter() {
  if (confirm("Send the Specialization and Anointments to the tray?"))
    attempt(() => store.clearCharacter());
}

function removeTeam() {
  if (confirm(`Delete “${team.value.name}” and its tray?`)) store.deleteTeam();
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
    if (file.size > 100000) throw new Error("File exceeds 100KB");
    const imported: unknown = JSON.parse(await file.text());
    if (confirm(`Replace everything in “${team.value.name}” with “${file.name}”?`))
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
const gemPosition = (position: number): Position => ({
  slot: openSlot.value,
  field: "spells",
  index: position,
});
</script>

<template>
  <section class="team" aria-label="Build">
    <div class="team-head">
      <input
        class="team-title"
        aria-label="Team name"
        maxlength="200"
        :value="team.name"
        @change="attempt(() => store.rename(($event.target as HTMLInputElement).value))"
      />
      <button
        type="button"
        class="teams-key"
        aria-haspopup="menu"
        :aria-expanded="teamsOpen"
        :popovertarget="teamsMenu"
      >
        Teams<i class="icon icon-down"></i>
      </button>
      <FloatingMenu :id="teamsMenu" v-slot="{ close }" v-model:open="teamsOpen" label="Teams">
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
          <i class="icon icon-plus"></i>New team
        </button>
        <button
          type="button"
          role="menuitem"
          @click="
            close();
            removeTeam();
          "
        >
          <i class="icon icon-trash"></i>Delete team
        </button>
      </FloatingMenu>
      <button
        type="button"
        class="icon-button share-key"
        aria-label="Share link"
        title="Share link"
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
        label="Share link"
      >
        <label><input v-model="shareTray" type="checkbox" />Include tray</label>
        <button
          type="button"
          class="primary"
          @click="
            close();
            attempt(share);
          "
        >
          Share
        </button>
      </FloatingMenu>
    </div>
    <div v-if="notices.length" class="build-notices">
      <ul>
        <li v-for="notice in shownNotices" :key="notice">{{ notice }}</li>
      </ul>
      <button
        v-if="notices.length > NOTICES_SHOWN"
        type="button"
        class="notices-toggle"
        :aria-expanded="allNotices"
        @click="allNotices = !allNotices"
      >
        {{ allNotices ? "Show fewer" : `Show all ${notices.length}` }}
      </button>
    </div>
    <div class="slots">
      <div class="creature-slots">
        <div class="slot-sheet" role="group" aria-label="Team slots">
          <DropZone
            v-for="cell in cells"
            :key="cell.index"
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
                },
              ]"
              :data="cell.data"
              :class-from="cell.classFrom"
              :aria-pressed="phone ? undefined : cell.index === openSlot"
              :aria-label="`Slot ${slotIndex(cell.index)}${cell.label ? ': ' + cell.label : ''}`"
              :title="cell.label || undefined"
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
        </div>
        <DropZone
          v-if="phone"
          class="character-entry-drop"
          :accepts="acceptsCharacter('characterBase') || acceptsCharacter('characterAnointment')"
          @drop="() => {}"
        >
          <button
            type="button"
            class="character-entry"
            @click="router.push({ query: { page: 'character' } })"
          >
            <strong>Character</strong>
            <span>{{ characterSummary }}</span>
            <i class="icon icon-right"></i>
          </button>
        </DropZone>
        <section
          v-if="!phone || page === 'slot'"
          :ref="(el) => (slotPage = phone ? (el as HTMLElement | null) : null)"
          :class="['slot', 'open-slot', { 'phone-page': phone }]"
          :aria-label="`Slot ${openSlot + 1}`"
        >
          <h2>
            <button
              v-if="phone"
              type="button"
              class="page-back"
              aria-label="Back to team"
              @click="closePage"
            >
              <i class="icon icon-left"></i>
            </button>
            <span class="slot-name">Slot {{ slotIndex(openSlot) }}</span>
            <span v-if="phone" class="slot-pips" aria-hidden="true">
              <i
                v-for="cell in cells"
                :key="cell.index"
                :class="{ current: cell.index === openSlot, vacant: cell.vacant }"
              ></i>
            </span>
            <button
              v-if="!cells[openSlot]!.vacant"
              type="button"
              class="clear"
              aria-label="Clear slot"
              title="Clear slot"
              @click="clearSlot"
            >
              <i class="icon icon-trash"></i>
            </button>
          </h2>
          <span v-if="swipeOffset" :class="['swipe-peek', swipeOffset < 0 ? 'right' : 'left']">
            Slot {{ slotIndex(slotAfter(swipeOffset < 0 ? 1 : -1)) }}
          </span>
          <div
            :key="openSlot"
            :class="['slot-body', enteredFrom && `from-${enteredFrom}`]"
            :style="swipeOffset ? { transform: `translateX(${swipeOffset}px)` } : undefined"
          >
            <EquipmentRow
              v-for="field in shownFields"
              :key="field"
              :at="{ slot: openSlot, field }"
              :value="slot[field]"
              :accepts="accepts(field)"
              :hint="fieldHint(field)"
              :next="field === 'base' && !slot.base"
              :copyable="copySlots.length > 0"
              :warning="
                field === 'base' && overAvatar(openSlot)
                  ? avatars!.notice
                  : repeatWarning(openSlot, field)
              "
              @place="attempt(() => place({ slot: openSlot, field }))"
              @drop="attempt(() => place({ slot: openSlot, field }, dropped()))"
              @inspect="
                field === 'artifact'
                  ? (dialog = { type: 'artifact', slot: openSlot })
                  : field === 'relic'
                    ? (dialog = { type: 'relic', slot: openSlot })
                    : (preview = asItem(slot[field]!))
              "
              @copy="dialog = { type: 'copy', at: { slot: openSlot, field } }"
              @remove="attempt(() => store.unequip({ slot: openSlot, field }))"
            />
            <p v-if="!slot.base" class="locked-hint">Add a Primary to equip the rest</p>
            <DropZone
              v-if="slot.base || slot.spells?.length"
              class="gem-area"
              :accepts="accepts('spells')"
              @drop="attempt(() => place({ slot: openSlot, field: 'spells' }, dropped()))"
            >
              <small>Spell Gems</small>
              <div
                v-for="(gem, position) in slot.spells ?? []"
                :key="asItem(gem).uid || position"
                v-bind="drag(gemPosition(position))"
                class="gem equipped"
                @click="
                  selected
                    ? attempt(() => place({ slot: openSlot, field: 'spells' }))
                    : (dialog = { type: 'gem', at: gemPosition(position) })
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
                      aria-label="Copy: Spell Gem"
                      title="Copy"
                      @click="dialog = { type: 'copy', at: gemPosition(position) }"
                    >
                      <i class="icon icon-copy"></i>
                    </button>
                    <button
                      type="button"
                      class="icon-button"
                      aria-label="Back to tray: Spell Gem"
                      title="Back to tray"
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
                @click="attempt(() => place({ slot: openSlot, field: 'spells' }))"
              >
                <i class="icon icon-plus"></i>Spell Gem
              </button>
            </DropZone>
          </div>
        </section>
      </div>
      <CharacterPanel
        v-if="index && (!phone || page === 'character')"
        :class="{ 'phone-page': phone }"
        :character="team.character"
        :index="index"
        :accepts="acceptsCharacter"
        @place="(field, position) => attempt(() => placeCharacter(field, position))"
        @drop="(field, position) => attempt(() => placeCharacter(field, position, dropped()))"
        @remove="(field, position) => attempt(() => store.removeCharacterPart(field, position))"
        @perks="dialog = { type: 'perks' }"
        @inspect="(id) => (preview = { uid: '', id })"
        @clear="clearCharacter"
      >
        <template v-if="phone" #lead>
          <button type="button" class="page-back" aria-label="Back to team" @click="closePage">
            <i class="icon icon-left"></i>
          </button>
        </template>
      </CharacterPanel>
      <section v-if="!page" class="slot notes-panel" aria-label="Notes">
        <h2>
          Notes
          <span class="notes-actions">
            <button type="button" aria-label="Export team" @click="exportTeam">Export</button>
            <button type="button" aria-label="Import team" @click="chooseImport()">Import</button>
          </span>
        </h2>
        <textarea
          ref="notesField"
          aria-label="Team notes"
          maxlength="10000"
          rows="6"
          :value="team.notes"
          @change="attempt(() => store.setNotes(($event.target as HTMLTextAreaElement).value))"
        ></textarea>
      </section>
    </div>

    <ModalDialog
      v-model:open="dialogOpen"
      :title="dialogTitle"
      :sheet="dialog?.type === 'carrier' || dialog?.type === 'copy'"
    >
      <div v-if="dialog?.type === 'pool' && index" class="choices">
        <FieldPicker
          :field="dialog.target.field"
          :label="fieldLabels[dialog.target.field]"
          :team="team"
          :catalog="index.catalog"
          :kind-of="kindOf"
          @pick="pickPool"
          @take="takePool"
          @search="
            (q, a) => searchFor(dialog!.type === 'pool' ? dialog!.target.field : 'base', q, a)
          "
        >
          <button
            v-if="dialog.target.field === 'artifact'"
            type="button"
            class="choice choice-action"
            @click="configure(dialog.target)"
          >
            <i class="icon icon-plus"></i>Configure an Artifact
          </button>
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
          :label="dialog.field === 'characterBase' ? 'Specialization' : 'Anointment'"
          :team="team"
          :catalog="index.catalog"
          :kind-of="kindOf"
          @pick="pickCharacter"
          @take="takeCharacter"
          @search="(q, a) => searchFor(dialog!.type === 'character' ? dialog!.field : 'base', q, a)"
        />
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
      <GemEditor
        v-else-if="dialog?.type === 'gem' && gemAt(dialog)"
        :item="gemAt(dialog)!"
        :properties="gemProperties"
        :compatible="index?.rules.property_compatibility[gemAt(dialog)!.id]"
        @apply="applyGem"
      />
      <ArtifactEditor
        v-else-if="dialog?.type === 'artifact' && index"
        :item="artifactOf(dialog.slot)"
        :catalog="index.catalog"
        :team="team"
        :kind-of="kindOf"
        @apply="applyArtifact"
        @search="(_, q) => searchFor('artifactTrait', q)"
      />
      <RelicEditor
        v-else-if="dialog?.type === 'relic' && index"
        :id="relicOf(dialog.slot).id"
        :relics="[...index.relics.values()]"
        :rank="relicOf(dialog.slot).rank"
        @apply="applyRelic"
      />
      <CharacterEditor
        v-else-if="dialog?.type === 'perks' && index"
        :character="team.character"
        :specialization="specializationName"
        :perks="index.perks"
        @apply="(character) => attempt(() => store.setCharacter(character))"
      />
    </ModalDialog>
    <PreviewDialog v-model:item="preview" />
  </section>
</template>

<style scoped>
.team {
  display: grid;
  gap: var(--space-16);
  max-width: 1280px;
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
  flex: none;
  gap: var(--space-4);
  min-height: var(--field);
  padding: 0 var(--space-8) 0 var(--space-12);
}
.share-key {
  width: var(--field);
  min-width: var(--field);
  height: var(--field);
  margin-left: auto;
}
.notes-panel {
  align-self: start;
}
.notes-actions {
  display: flex;
  gap: 4px;
  margin-left: auto;
}
.notes-actions > button {
  min-height: var(--control-compact);
  padding: 0 10px;
  font-size: var(--fs-13);
}
.notes-panel > textarea {
  display: block;
  width: calc(100% - 24px);
  margin: 12px;
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
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 8px 12px;
}
.build-notices li + li {
  border-top: 1px solid var(--danger-rule);
}
.build-notices li::before {
  content: "";
  flex: none;
  width: 8px;
  height: 8px;
  background: var(--danger-mark);
}
.notices-toggle {
  width: 100%;
  min-height: var(--control-compact);
  justify-content: flex-start;
  padding: 0 12px 0 28px;
  clip-path: none;
  background: none;
  border: 0;
  border-top: 1px solid var(--danger-line);
  color: var(--danger-text);
  font-size: var(--fs-13);
  font-weight: 700;
}
.notices-toggle:hover {
  background: var(--danger-hover);
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
.slot-cell.over-limit::before {
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
.character-entry {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: var(--space-12);
  width: 100%;
  min-height: var(--row);
  padding: 0 var(--space-8) 0 var(--space-12);
  background: var(--cell);
  clip-path: none;
  text-align: left;
}
.character-entry > strong {
  color: var(--kind-character);
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
  .slots {
    grid-template-columns: minmax(0, 1fr) 320px;
    grid-template-rows: auto 1fr;
  }
  .creature-slots {
    grid-column: 1;
    grid-row: 1 / span 2;
  }
  .slots > :deep(.character-slot) {
    grid-column: 2;
    grid-row: 1;
    align-self: start;
  }
  .notes-panel {
    grid-column: 2;
    grid-row: 2;
  }
  .slot-sheet {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }
}
@media (max-width: 767px) {
  .team {
    padding: var(--space-12) var(--gutter) var(--space-24);
  }
}
</style>
