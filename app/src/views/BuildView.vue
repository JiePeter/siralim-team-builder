<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useEventListener } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { object, type Carrier } from "@/data";
import AssetImage from "@/components/AssetImage.vue";
import { useTeamStore } from "@/stores/team";
import { fieldLabels, isListField, type CharacterField, type Position } from "@/domain/assembly";
import { NO_CARRIER, placementRefusal, traitSwap } from "@/domain/placement";
import {
  asItem,
  BLANK_ARTIFACT,
  itemId,
  NETHER_TRAITS,
  PARTY_SIZE,
  TRAIT_FIELDS,
  type ArtifactConfig,
  type Equipment,
} from "@/domain/team";
import ArtifactEditor from "@/components/ArtifactEditor.vue";
import CarrierPicker from "@/components/CarrierPicker.vue";
import CharacterEditor from "@/components/CharacterEditor.vue";
import CharacterPanel from "@/components/CharacterPanel.vue";
import CharacterRow from "@/components/CharacterRow.vue";
import DropZone from "@/components/DropZone.vue";
import EditorActions from "@/components/EditorActions.vue";
import EquipmentLine from "@/components/EquipmentLine.vue";
import FieldPicker from "@/components/FieldPicker.vue";
import GemEditor from "@/components/GemEditor.vue";
import ModalDialog from "@/components/ModalDialog.vue";
import ObjectCell from "@/components/ObjectCell.vue";
import RelicEditor from "@/components/RelicEditor.vue";
import ShareMenu from "@/components/ShareMenu.vue";
import SlotPage from "@/components/SlotPage.vue";
import TeamFileMenu from "@/components/TeamFileMenu.vue";
import TeamSwitcher from "@/components/TeamSwitcher.vue";
import TraitCell from "@/components/TraitCell.vue";
import { fieldKinds, slotIndex, useGemProperties } from "@/components/assembly";
import { isVacant, slotGear, useBuildNotices } from "@/components/buildNotices";
import { component, loadComponent } from "@/components/components";
import { usePlacing } from "@/components/placing";
import { spriteOf, usePhone, useShowNether } from "@/components/presentation";
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
const { team, index } = storeToRefs(store);
const route = useRoute();
const router = useRouter();
const drag = useDragSource();
const gemProperties = useGemProperties();
const {
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
} = usePlacing();
const { blended, fieldWarning, notices, overAvatar, slotNotices } = useBuildNotices();
store.rules();

const openSlot = ref(0);
/** On a wider screen, whether a slot is open below the sheet; the Traits table shows otherwise. */
const slotOpen = ref(false);
const phone = usePhone();
/** On a phone a slot or the character opens as its own page, so Back closes it. */
const page = computed(() => (phone.value ? route.query.page : undefined));
const showNether = useShowNether();
const dialog = ref<Dialog | null>(null);
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
const showTraits = computed(() => !phone.value && !slotOpen.value);

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
const noticesOpen = ref(false);

/** The component a placement into `target` takes out; a list field with no position adds to the list. */
const occupantAt = (target: Position) =>
  isListField(target.field) && target.index === undefined ? undefined : itemId(equipmentAt(target));

const gearName = (id: string) =>
  id === BLANK_ARTIFACT ? t("build.artifact") : component(id)?.name;

const cells = computed(() =>
  team.value.slots.map((s, i) => {
    const base = s.base ? component(itemId(s.base)!) : undefined;
    const fusion = s.base && s.fusion && !blended.value ? component(itemId(s.fusion)!) : null;
    const first = slotGear(s)[0];
    const label = base?.name ?? "";
    return {
      index: i,
      label,
      notices: slotNotices(i).map((n) => n.text),
      sprite: base ? spriteOf(base, 0) : null,
      data: base ?? (first ? component(itemId(first)!) : null),
      classFrom: fusion,
      vacant: isVacant(s),
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
    case "carrier":
      return d.kind === "creature" ? t("build.selectCreature") : t("build.selectMaterial");
    case "character":
      return placementLabel({ character: d.field, position: d.position });
    case "gem":
      return t("build.spellGem");
    case "copy":
      return t("build.copyTo");
    case "perks":
      return t("build.specialization");
  }
  return dialogAt.value ? fieldTitle(dialogAt.value) : "";
});
const chosenSpecialization = computed(() =>
  index.value?.catalog.specializations.find((s) => s.id === team.value.character.specialization),
);

async function install(uid: string, target: Position, resolvedId: string) {
  await store.install(uid, target, resolvedId);
  selected.value = null;
  dialog.value = null;
}

/** Run a change; when it takes out the component `read` finds, offer to undo it. */
async function withUndo({
  read,
  run,
  next,
  after,
  swapped,
}: {
  read: () => string | null | undefined;
  run: () => unknown;
  next?: () => void;
  /** Runs once an Undo has restored the team. */
  after?: () => void;
  /** The component changed places instead of going to the tray. */
  swapped?: boolean;
}) {
  const occupant = read();
  const mark = store.restorePoint();
  await run();
  next?.();
  // The toast joins the dialog on screen, which `next` may have just closed.
  await nextTick();
  if (!occupant || read() === occupant) return;
  const undo = mark();
  toast(swapped ? t("build.swapped") : t("build.wentToTray", { name: gearName(occupant) }), {
    label: t("build.undo"),
    run: () =>
      attempt(() => {
        undo();
        after?.();
      }),
  });
}

function placeWithUndo(target: Position, selection: Selection | null = selected.value) {
  const swapped =
    !!selection && "slot" in selection && !!traitSwap(index.value!, team.value, selection, target);
  return withUndo({
    read: () => occupantAt(target),
    run: () => place(target, selection),
    swapped,
  });
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

/** On the Traits view a field is its Trait: a tap places the chosen item or opens the picker that replaces it. */
function openTrait(target: Position) {
  if (selected.value) return attempt(() => placeWithUndo(target));
  dialog.value = { type: "pool", target };
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
  const moving = itemId(selectionItem(selection));
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
  await overCharacter(field, position, () =>
    store.placeCharacterPart(selection.uid, field, position),
  );
}

/** Run a change to a character part; a Specialization continues into its Perks. */
function overCharacter(field: CharacterField, position: number, run: () => unknown) {
  return withUndo({
    read: () => characterAt(field, position),
    run,
    next: () => (dialog.value = field === "characterBase" ? { type: "perks" } : null),
  });
}

/** Run the choice a picker made for `target`, then continue past the picker. */
function fillFromPicker(target: Position, run: () => unknown) {
  attempt(() => withUndo({ read: () => occupantAt(target), run, next: () => afterPick(target) }));
}

function pickPool(uid: string) {
  const d = dialog.value;
  if (d?.type !== "pool") return;
  fillFromPicker(d.target, () => place(d.target, { uid }));
}

function takePool(id: string) {
  const d = dialog.value;
  if (d?.type !== "pool") return;
  fillFromPicker(d.target, () => store.take(id, d.target));
}

function pickCarrier(option: Carrier) {
  const d = dialog.value;
  if (d?.type !== "carrier") return;
  fillFromPicker(d.target, () => install(d.uid, d.target, option.id));
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
    overCharacter(d.field, d.position, () => store.takeCharacterPart(id, d.field, d.position)),
  );
}

async function placeOnTile(target: number) {
  const field = tileField(target);
  const selection = dragged.value ? dropped() : selected.value;
  if (!selection) return;
  if (!("member" in selection)) {
    if (!field) throw new Error(t("build.doesNotFit"));
    setOpenSlot(target);
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
  if (openSlot.value === selection.member) setOpenSlot(target);
  else if (openSlot.value === target) setOpenSlot(selection.member);
}

function tapTile(i: number) {
  const moving = selected.value && "member" in selected.value ? selected.value.member : null;
  if (moving === i) selected.value = null;
  else if (selected.value && acceptsMember(i)) attempt(() => placeOnTile(i));
  else if (phone.value) openSlotPage(i);
  else showSlotPanel(i);
}

/** One listener per tile, so a re-render of the sheet hands each tile the same function. */
const tileTaps = Array.from({ length: PARTY_SIZE }, (_, i) => () => tapTile(i));

/** A slot open beside the sheet is in the route too, so it survives a trip to Search. */
function setOpenSlot(i: number) {
  openSlot.value = i;
  if (slotOpen.value && !phone.value) router.replace({ query: { slot: String(i + 1) } });
}

function showSlotPanel(i: number) {
  slotOpen.value = true;
  setOpenSlot(i);
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

function sendToTray(at: Position) {
  return attempt(() =>
    withUndo({
      read: () => occupantAt(at),
      run: () => store.unequip(at),
      next: () => (dialog.value = null),
    }),
  );
}

async function sendCharacterToTray(field: CharacterField, position: number) {
  if (await attempt(() => store.removeCharacterPart(field, position))) dialog.value = null;
}

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
      ? t("build.replaces", { name: gearName(occupant) })
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
  // A blank Artifact has no Trait to send to the tray.
  const trait = () => {
    const id = itemId(team.value.slots[d.slot]?.artifact);
    return id === BLANK_ARTIFACT ? undefined : id;
  };
  attempt(() =>
    withUndo({
      read: trait,
      run: () => store.setArtifact(d.slot, item, configuration, taken),
      after: () => artifactVersion.value++,
    }),
  );
}

function applyRelic(id: string, rank: number) {
  const d = dialog.value;
  if (d?.type === "relic") attempt(() => store.setRelic(d.slot, id, rank));
}

function clearCharacter() {
  if (confirm(t("build.confirmClearCharacter"))) attempt(() => store.clearCharacter());
}

const gemAt = (d: Dialog) => (d.type === "gem" ? asItem(equipmentAt(d.at)!) : null);
const relicOf = (s: number) => {
  const relic = team.value.slots[s]?.relic;
  return { id: itemId(relic) ?? "", rank: (relic && asItem(relic).rank) || 1 };
};
const artifactOf = (s: number) => {
  const artifact = team.value.slots[s]?.artifact;
  return artifact ? asItem(artifact) : null;
};
const netherAt = (slot: number, position: number) => ({
  slot,
  field: "nether" as const,
  index: position,
});
function openCharacter(field: CharacterField, position: number) {
  attempt(() => placeCharacter(field, position));
}

/** The field a picker or editor dialog is about. */
const dialogAt = computed<Position | null>(() => {
  const d = dialog.value;
  switch (d?.type) {
    case "pool":
      return d.target;
    case "gem":
      return d.at;
    case "artifact":
    case "relic":
      return { slot: d.slot, field: d.type };
  }
  return null;
});
const currentCharacter = computed(() => {
  const d = dialog.value;
  if (d?.type !== "character") return undefined;
  return characterAt(d.field, d.position) ?? undefined;
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
    <div class="team-head" :inert="phone && showSlot">
      <input
        class="team-title"
        :aria-label="$t('build.teamName')"
        maxlength="200"
        :value="team.name"
        @change="attempt(() => store.rename(($event.target as HTMLInputElement).value))"
      />
      <TeamSwitcher />
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
      <ShareMenu />
      <TeamFileMenu />
    </div>
    <div v-if="noticesOpen && notices.length" class="build-notices">
      <ul>
        <li v-for="notice in notices" :key="notice.text">{{ notice.text }}</li>
      </ul>
    </div>
    <div :class="['slots', { 'traits-shown': showTraits, 'nether-shown': showNether }]">
      <div class="creature-slots">
        <div
          class="slot-sheet"
          role="group"
          :aria-label="$t('build.teamSlots')"
          :inert="phone && showSlot"
        >
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
                @click="tileTaps[cell.index]"
              >
                <template #index
                  ><span class="cell-index">{{ slotIndex(cell.index) }}</span></template
                >
                <template v-if="cell.label" #label>{{ cell.label }}</template>
              </ObjectCell>
            </DropZone>
            <template v-if="showTraits">
              <AssetImage
                v-if="cell.sprite"
                class="slot-backdrop"
                :src="cell.sprite"
                alt=""
                aria-hidden="true"
              />
              <TraitCell
                v-for="field in TRAIT_FIELDS"
                :key="field"
                :at-slot="cell.index"
                :field="field"
                :value="team.slots[cell.index]![field]"
                :next="field === 'base' && cell.index === cells.findIndex((c) => c.vacant)"
                :accepts="accepts({ slot: cell.index, field })"
                :hint="fieldHint({ slot: cell.index, field })"
                :warning="fieldWarning(cell.index, field)"
                @place="openTrait({ slot: cell.index, field })"
                @drop="attempt(() => placeWithUndo({ slot: cell.index, field }, dropped()))"
              />
              <div v-if="showNether" class="nether-band">
                <TraitCell
                  v-for="(trait, position) in team.slots[cell.index]!.nether ?? []"
                  :key="asItem(trait).uid || position"
                  :at-slot="cell.index"
                  field="nether"
                  :at-index="position"
                  :value="trait"
                  :accepts="accepts(netherAt(cell.index, position))"
                  @place="openField(netherAt(cell.index, position))"
                  @drop="attempt(() => placeWithUndo(netherAt(cell.index, position), dropped()))"
                />
                <TraitCell
                  v-if="(team.slots[cell.index]!.nether?.length ?? 0) < NETHER_TRAITS"
                  :at-slot="cell.index"
                  field="nether"
                  :at-index="team.slots[cell.index]!.nether?.length ?? 0"
                  :value="undefined"
                  :accepts="accepts({ slot: cell.index, field: 'nether' })"
                  @place="openField({ slot: cell.index, field: 'nether' })"
                  @drop="
                    attempt(() => placeWithUndo({ slot: cell.index, field: 'nether' }, dropped()))
                  "
                />
              </div>
            </template>
          </div>
        </div>
        <CharacterRow
          v-if="phone"
          :inert="showSlot"
          :accepts="acceptsCharacter"
          @open="openCharacter"
        />
        <SlotPage
          v-if="showSlot"
          :at-slot="openSlot"
          @open="openField"
          @drop="(target) => attempt(() => placeWithUndo(target, dropped()))"
          @copy="(at) => (dialog = { type: 'copy', at })"
          @tray="sendToTray"
          @move="placeFromHere({ member: openSlot })"
          @close="closeSlot"
        />
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
          :target="dialog.target"
          :current="occupantAt(dialog.target)"
          @pick="pickPool"
          @take="takePool"
        >
          <template #current-actions>
            <button
              v-if="canSwap(dialog.target)"
              type="button"
              class="icon-button"
              :aria-label="$t('editors.keys.swap')"
              :title="$t('editors.keys.swap')"
              @click="placeFromHere(dialogAt!)"
            >
              <i class="icon icon-replace"></i>
            </button>
            <button
              type="button"
              class="icon-button"
              :aria-label="$t('editors.keys.tray')"
              :title="$t('editors.keys.tray')"
              @click="sendToTray(dialogAt!)"
            >
              <i class="icon icon-undo"></i>
            </button>
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
          :current="currentCharacter"
          @pick="pickCharacter"
          @take="takeCharacter"
        >
          <template #current-actions>
            <button
              type="button"
              class="icon-button"
              :aria-label="$t('editors.keys.tray')"
              :title="$t('editors.keys.tray')"
              @click="
                dialog?.type === 'character' && sendCharacterToTray(dialog.field, dialog.position)
              "
            >
              <i class="icon icon-undo"></i>
            </button>
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
      <template v-else-if="dialogAt && index">
        <EditorActions
          :replace="dialogAt.field !== 'artifact' && !!equipmentAt(dialogAt)"
          :tray="!!equipmentAt(dialogAt)"
          @replace="replaceFrom(dialogAt!)"
          @tray="sendToTray(dialogAt!)"
        />
        <GemEditor
          v-if="dialog?.type === 'gem' && gemAt(dialog)"
          :item="gemAt(dialog)!"
          :properties="gemProperties"
          :compatible="index?.rules.property_compatibility[gemAt(dialog)!.id]"
          @apply="applyGem"
        />
        <ArtifactEditor
          v-else-if="dialog?.type === 'artifact'"
          :key="artifactVersion"
          :item="artifactOf(dialog.slot)"
          :catalog="index.catalog"
          :team="team"
          :at-slot="dialog.slot"
          @apply="applyArtifact"
        />
        <RelicEditor
          v-else-if="dialog?.type === 'relic'"
          :id="relicOf(dialog.slot).id"
          :relic="index.relics.get(relicOf(dialog.slot).id)"
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
          :specialization="chosenSpecialization?.name ?? ''"
          :royal="chosenSpecialization?.key === 'Royal'"
          :perks="index.perks"
          @apply="(character) => attempt(() => store.setCharacter(character))"
        />
      </template>
    </ModalDialog>
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
  background: color-mix(in srgb, var(--raised) 55%, transparent);
  text-align: left;
}
.traits-shown .slot-cell:hover {
  background: color-mix(in srgb, var(--raised-hover) 70%, transparent);
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
.nether-shown.traits-shown .slot-column {
  grid-row: span 5;
}
.nether-band {
  display: grid;
  align-content: start;
  min-width: 0;
  border-top: 1px dashed var(--strong);
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
.field-notice {
  border-width: 0 0 1px;
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
}
@media (max-width: 767px) {
  .team {
    gap: var(--space-8);
    padding: var(--space-4) var(--gutter) var(--space-24);
  }
  /* A long team name shortens before the keys move; the notices fill the second row. */
  .team-head {
    display: grid;
    grid-template-columns: minmax(0, max-content) auto minmax(0, 1fr) auto auto;
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
  /* The height of a named tile, so a row of vacant tiles matches it. */
  .slot-cell {
    min-height: 122px;
  }
}
</style>
