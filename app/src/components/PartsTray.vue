<script setup lang="ts">
import { computed, inject, nextTick, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import { useEventListener, useTimeoutFn } from "@vueuse/core";
import { useTeamStore } from "@/stores/team";
import { t } from "@/i18n";
import { MAX_TRAIT_COPIES, placedParts, whereIs } from "@/domain/placement";
import { asItem, asTrait, BLANK_ARTIFACT, type Equipment, type Team } from "@/domain/team";
import DropZone from "./DropZone.vue";
import CellPlate from "./CellPlate.vue";
import PreviewDialog from "./PreviewDialog.vue";
import PropertyPills from "./PropertyPills.vue";
import { canPlace, shownAs } from "./assembly";
import { component } from "./components";
import { kindGroup, kindGroups, useShowNether } from "./presentation";
import { dragged, draggedSelection, useDragSource } from "./dragging";
import { attempt, toast } from "./toast";
import { flashed, lineKey, selected, startPlacing, trayOpen, useEntity } from "./tray";
import { DIALOG_ACTIONS } from "./dialog";

defineProps<{ sheet?: boolean }>();
const dialogActions = inject(DIALOG_ACTIONS, null);

const store = useTeamStore();
const { team, index } = storeToRefs(store);
const route = useRoute();
const router = useRouter();
const entity = useEntity();
const drag = useDragSource();
const preview = ref<Equipment | null>(null);
const list = ref<HTMLElement | null>(null);
const showNether = useShowNether();
const kindOf = (id: string) => index.value?.kinds.get(id);

/** One per team, so the tray never holds two of them. */
const single = new Set(["relic", "specialization", "perk"]);

interface Line {
  key: string;
  item: Equipment;
  /** Instances not yet placed in the team. */
  uids: string[];
  placed: number;
  /** The component the line shows: a trait as its creature or material. */
  shown: string;
  kind: string;
}

/** Components in the team, keyed as the tray keys them: an unconfigured creature as its trait. */
function placedItems(value: Team): Equipment[] {
  return placedParts(value)
    .map((part) => asItem(part.ref))
    .filter((item) => item.id !== BLANK_ARTIFACT)
    .map((item) => (index.value ? asTrait(index.value, item) : item));
}

/**
 * The whole workspace, tray and team together. Identical instances share a line with a
 * quantity; configured copies stay apart.
 */
const groups = computed(() => {
  const lines = new Map<string, Line>();
  const add = (item: Equipment, placed: boolean) => {
    const key = lineKey(item);
    let line = lines.get(key);
    if (!line) {
      const shown = shownAs(index.value, item);
      const kind = component(shown)?.kind ?? "";
      line = { key, item, uids: [], placed: 0, shown, kind };
      lines.set(key, line);
    }
    if (placed) line.placed++;
    else line.uids.push(item.uid);
  };
  for (const item of team.value.inventory) add(item, false);
  for (const item of placedItems(team.value)) add(item, true);
  const all = [...lines.values()];
  return [
    ...kindGroups.map(({ value, label }) => ({
      value,
      label,
      lines: all.filter((line) => kindGroup(line.kind) === value),
    })),
    { value: "other", label: t("tray.other"), lines: all.filter((line) => !kindGroup(line.kind)) },
  ].filter((group) => group.lines.length);
});

/** Equipped gear or a whole team slot being dragged can go back to the tray. */
const returning = computed(() => {
  const selection = dragged.value ? draggedSelection() : null;
  return selection && !("uid" in selection) ? true : null;
});
const building = computed(() => route.name === "build");
const isSelected = (line: Line) =>
  !!selected.value && "uid" in selected.value && line.uids.includes(selected.value.uid);
const name = (line: Line) => component(line.shown)?.name ?? "";
/** The trait a creature or material line carries, named after it. */
const traitName = (line: Line) => {
  const data = component(line.shown);
  return data && ["creature", "material"].includes(data.kind) ? data.effects[0]?.name : undefined;
};
const inBuild = (line: Line) =>
  line.placed > 1
    ? t("tray.inBuildCount", { count: line.placed })
    : line.placed
      ? t("tray.inBuild")
      : "";
const trashLabel = t("tray.clear");
const atLimit = (line: Line) => {
  const where = whereIs(team.value, line.item.id, entity);
  return (
    entity(line.item.id).startsWith("trait:") &&
    where.placed.length + where.tray.length >= MAX_TRAIT_COPIES
  );
};

/** The line whose last copy waits for a second tap before leaving the tray. */
const arming = ref<string | null>(null);
const { start: disarmSoon } = useTimeoutFn(() => (arming.value = null), 3000, { immediate: false });
useEventListener(document, "pointerdown", (event) => {
  if (!(event.target as Element).closest?.(".tray-remove")) arming.value = null;
});

function decrease(line: Line) {
  if (line.uids.length > 1) {
    attempt(() => store.removeFromTray(line.uids.at(-1)!));
    return;
  }
  arming.value = line.key;
  disarmSoon();
}

async function remove(line: Line) {
  const label = name(line);
  arming.value = null;
  const undo = await attempt(() => store.removeFromTray(line.uids[0]!));
  if (undo)
    toast(t("tray.removed", { name: label }), { label: t("tray.undo"), run: () => attempt(undo) });
}

/** A line that no position takes opens its look-up, so placing never starts with nowhere to go. */
function placeable(line: Line) {
  return (
    building.value &&
    line.uids.length > 0 &&
    !!index.value &&
    canPlace(index.value, team.value, line.item, kindOf(line.item.id), showNether.value)
  );
}

function choose(line: Line) {
  if (isSelected(line)) {
    selected.value = null;
    return;
  }
  if (!placeable(line)) {
    preview.value = line.item;
    return;
  }
  const sheet = trayOpen.value;
  startPlacing({ uid: line.uids[0]! }, sheet ? () => (trayOpen.value = true) : null);
  trayOpen.value = false;
}

/** Gear dragged onto the tray leaves its field; a team slot dragged onto it is dismissed. */
function received() {
  const selection = draggedSelection();
  dragged.value = null;
  if (!selection || "uid" in selection) return;
  if ("member" in selection) attempt(() => store.clearSlot(selection.member));
  else if ("character" in selection)
    attempt(() => store.removeCharacterPart(selection.character, selection.position));
  else attempt(() => store.unequip(selection));
}

function clear() {
  if (confirm(t("tray.confirmClear", { team: team.value.name })))
    attempt(() => store.clearWorkspace());
}

watch(flashed, async (uid) => {
  if (!uid) return;
  await nextTick();
  list.value?.querySelector(`[data-uids~="${uid}"]`)?.scrollIntoView({ block: "nearest" });
});
</script>

<template>
  <section class="parts-tray" :aria-label="$t('tray.title')">
    <h2 v-if="!sheet" class="tray-head">
      {{ $t("tray.title") }}
      <button
        v-if="groups.length"
        type="button"
        class="clear"
        :aria-label="trashLabel"
        :title="trashLabel"
        @click="clear"
      >
        <i class="icon icon-trash"></i>
      </button>
    </h2>
    <Teleport v-else-if="groups.length && dialogActions" defer :to="`#${dialogActions}`">
      <button
        type="button"
        class="clear"
        :aria-label="trashLabel"
        :title="trashLabel"
        @click="clear"
      >
        <i class="icon icon-trash"></i>
      </button>
    </Teleport>
    <DropZone class="tray-drop" :accepts="returning" @drop="received">
      <div ref="list" class="tray-list">
        <section
          v-for="group in groups"
          :key="group.value"
          :class="['tray-group', `group-${group.value}`]"
        >
          <h3>{{ group.label }}</h3>
          <div
            v-for="line in group.lines"
            :key="line.key"
            :class="[
              'tray-item',
              { flash: line.uids.includes(flashed ?? ''), selected: isSelected(line) },
            ]"
            :data-uids="line.uids.join(' ')"
            v-bind="building && line.uids.length ? drag({ uid: line.uids[0]! }) : {}"
          >
            <button
              type="button"
              class="tray-look"
              :aria-label="[$t('tray.lookUp', { name: name(line) }), inBuild(line)].join('. ')"
              :title="inBuild(line) || undefined"
              @click="preview = line.item"
            >
              <CellPlate
                v-if="component(line.shown)"
                compact
                :data="component(line.shown)!"
                :added="line.placed > 1 ? line.placed : line.placed > 0"
              />
            </button>
            <div class="tray-text">
              <span class="tray-line"
                ><button
                  type="button"
                  class="tray-name"
                  :aria-pressed="building && line.uids.length ? isSelected(line) : undefined"
                  @click="choose(line)"
                >
                  {{ name(line) }}</button
                ><small
                  v-if="line.item.rank"
                  class="tray-rank"
                  :aria-label="$t('tray.rank', { rank: line.item.rank })"
                  >Lv.{{ line.item.rank }}</small
                ><small v-if="traitName(line)" class="tray-trait">{{
                  traitName(line)
                }}</small></span
              >
              <PropertyPills :item="line.item" />
            </div>
            <div class="tray-actions">
              <button
                v-if="arming === line.key"
                type="button"
                class="tray-remove"
                @click="remove(line)"
              >
                {{ $t("tray.remove") }}
              </button>
              <span v-else-if="line.uids.length" class="stepper">
                <button
                  type="button"
                  class="icon-button"
                  :aria-label="
                    $t(line.uids.length > 1 ? 'tray.removeOne' : 'tray.removeNamed', {
                      name: name(line),
                    })
                  "
                  @click="decrease(line)"
                >
                  <i :class="['icon', line.uids.length > 1 ? 'icon-minus' : 'icon-trash']"></i>
                </button>
                <template v-if="!single.has(line.kind)">
                  <span class="tray-quantity">{{ line.uids.length }}</span>
                  <button
                    type="button"
                    class="icon-button"
                    :aria-label="$t('tray.addOne', { name: name(line) })"
                    :aria-disabled="atLimit(line) || undefined"
                    @click="attempt(() => store.copyPoolItem(line.uids[0]!))"
                  >
                    <i class="icon icon-plus"></i>
                  </button>
                </template>
              </span>
            </div>
          </div>
        </section>
        <div v-if="!groups.length" class="tray-empty">
          <p class="muted">{{ $t("tray.empty") }}</p>
          <RouterLink v-if="sheet" class="link" to="/search">{{
            $t("tray.searchComponents")
          }}</RouterLink>
        </div>
      </div>
    </DropZone>
    <button
      v-if="sheet && !building && team.inventory.length"
      type="button"
      class="primary tray-next"
      @click="router.push({ name: 'build' })"
    >
      {{ $t("tray.goToBuild") }}
    </button>
    <PreviewDialog v-model:item="preview" />
  </section>
</template>

<style scoped>
.parts-tray {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.tray-head {
  display: flex;
  align-items: center;
  flex: none;
  min-height: var(--row);
  padding: 0 12px 0 16px;
  font-size: var(--fs-15);
}
.tray-drop {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
.tray-list {
  min-height: 100%;
  padding-bottom: 8px;
}
.tray-group > h3 {
  padding: 12px 16px 4px;
  color: var(--muted);
  font-size: var(--fs-12);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.group-creature > h3 {
  color: var(--kind-creature);
}
.group-trait > h3 {
  color: var(--kind-trait);
}
.group-material > h3 {
  color: var(--kind-material);
}
.group-relic > h3 {
  color: var(--kind-relic);
}
.group-character > h3 {
  color: var(--kind-character);
}
.tray-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-12);
  min-width: 0;
  padding: var(--space-8) var(--space-12) var(--space-8) var(--space-16);
  border: 1px solid transparent;
  transition: background-color 0.3s;
}
.tray-look {
  flex: none;
  width: auto;
  min-width: 0;
  min-height: 0;
  padding: 0;
  background: none;
  border: 0;
  clip-path: none;
}
.tray-look:hover,
.tray-look:active:not(:disabled) {
  background: none;
}
.tray-item[draggable="true"]::before {
  content: "";
  position: absolute;
  top: 50%;
  left: 2px;
  width: 12px;
  height: 16px;
  margin-top: -8px;
  background-color: var(--drop-line);
  -webkit-mask: var(--icon-grip) center / 16px 16px no-repeat;
  mask: var(--icon-grip) center / 16px 16px no-repeat;
}
@media (hover: hover) {
  .tray-item[draggable="true"]:hover {
    background: var(--raised);
  }
  .tray-item[draggable="true"]:hover::before {
    background-color: var(--muted);
  }
}
.tray-item.flash {
  background: var(--placed-ground);
  border-color: var(--placed);
}
.tray-item.selected {
  background: var(--raised);
  border-color: var(--accent);
}
.tray-text {
  display: grid;
  flex: 1;
  gap: var(--space-4);
  min-width: 0;
}
.tray-line {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0 var(--space-8);
}
.tray-name {
  min-height: 0;
  padding: 0;
  background: none;
  border: 0;
  clip-path: none;
  color: var(--text);
  font-size: var(--fs-15);
  font-weight: 700;
  line-height: 20px;
  text-align: left;
  overflow-wrap: anywhere;
}
.tray-name:hover {
  background: none;
  text-decoration: underline;
  text-decoration-color: var(--strong);
  text-underline-offset: 3px;
}
.tray-trait {
  color: var(--muted);
  font-size: var(--fs-12);
  overflow-wrap: anywhere;
}
.tray-rank {
  color: var(--accent);
  font: 400 10px / 1 var(--pixel-font);
}
.tray-quantity {
  align-self: center;
  min-width: 24px;
  color: var(--text);
  font: 400 13px / 1 var(--pixel-font);
  font-variant-numeric: tabular-nums;
  text-align: center;
}
.tray-remove {
  min-height: var(--control-compact);
  padding: 0 var(--space-12);
  background: var(--danger-mark);
  color: var(--ground);
  font-weight: 700;
  --key-line: var(--danger-mark);
}
.tray-next {
  position: sticky;
  bottom: 0;
  flex: none;
  width: 100%;
  min-height: var(--field);
}
.tray-actions {
  display: flex;
  flex: none;
  justify-content: flex-end;
}
.tray-actions [aria-disabled="true"] {
  opacity: 0.4;
}
.tray-actions .icon-button {
  width: var(--control-compact);
  min-width: var(--control-compact);
  height: var(--control-compact);
  min-height: var(--control-compact);
}
.stepper > button + button {
  margin-left: 0;
}
/* Tray rows share the tray's ground, so only a rule can separate them. */
@media (min-width: 768px) {
  .tray-head {
    border-bottom: 1px solid var(--line);
  }
  .tray-item:not(.selected, .flash) {
    border-bottom-color: var(--line);
  }
}
.tray-empty {
  display: grid;
  justify-items: start;
  gap: var(--space-8);
  padding: 16px;
}
.tray-empty > p {
  margin: 0;
}
</style>
