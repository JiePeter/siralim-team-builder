<script setup lang="ts">
import { computed, inject, nextTick, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import { useEventListener, useTimeoutFn } from "@vueuse/core";
import { BLANK_ARTIFACT, useTeamStore } from "@/stores/team";
import { MAX_TRAIT_COPIES, placedParts, whereIs } from "@/domain/placement";
import { asItem, asTrait, type Equipment, type Team } from "@/domain/team";
import DropZone from "./DropZone.vue";
import ObjectCell from "./ObjectCell.vue";
import PreviewDialog from "./PreviewDialog.vue";
import PropertyPills from "./PropertyPills.vue";
import { shownAs } from "./assembly";
import { component } from "./components";
import { kindGroup, kindGroups } from "./presentation";
import { dragged, draggedSelection, useDragSource } from "./dragging";
import { attempt, toast } from "./toast";
import { flashed, lineKey, selected, trayOpen, useEntity } from "./tray";
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
    { value: "other", label: "Other", lines: all.filter((line) => !kindGroup(line.kind)) },
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
const trashLabel = "Clear tray";
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
  if (undo) toast(`${label} removed`, { label: "Undo", run: () => attempt(undo) });
}

function choose(line: Line) {
  if (!building.value || !line.uids.length) {
    preview.value = line.item;
    return;
  }
  selected.value = isSelected(line) ? null : { uid: line.uids[0]! };
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
  if (confirm(`Remove every component from “${team.value.name}” and its tray?`))
    attempt(() => store.clearWorkspace());
}

watch(flashed, async (uid) => {
  if (!uid) return;
  await nextTick();
  list.value?.querySelector(`[data-uids~="${uid}"]`)?.scrollIntoView({ block: "nearest" });
});
</script>

<template>
  <section class="parts-tray" aria-label="Tray">
    <h2 v-if="!sheet" class="tray-head">
      Tray
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
          <ObjectCell
            v-for="line in group.lines"
            :key="line.key"
            :class="['tray-item', { flash: line.uids.includes(flashed ?? '') }]"
            :data="component(line.shown)"
            :selected="isSelected(line)"
            :data-uids="line.uids.join(' ')"
            v-bind="building && line.uids.length ? drag({ uid: line.uids[0]! }) : {}"
          >
            <template v-if="building" #index>
              <button
                type="button"
                class="tray-look"
                :aria-label="`Look up ${name(line)}`"
                @click="preview = line.item"
              ></button>
            </template>
            <template #label>
              <button
                type="button"
                class="tray-name"
                :aria-pressed="building && line.uids.length ? isSelected(line) : undefined"
                @click="choose(line)"
              >
                {{ name(line) }}
              </button>
            </template>
            <template #detail>
              <small v-if="traitName(line) || line.item.rank" class="tray-trait">
                <template v-if="line.item.rank">Rank {{ line.item.rank }}</template
                >{{ traitName(line) }}
              </small>
              <small v-if="line.placed" class="tray-in-build"
                >In build<template v-if="line.placed > 1"> ×{{ line.placed }}</template></small
              >
              <PropertyPills :item="line.item" />
            </template>
            <template #aside>
              <div class="tray-actions">
                <button
                  v-if="building"
                  type="button"
                  class="icon-button tray-eye"
                  :aria-label="`Look up ${name(line)}`"
                  :title="`Look up ${name(line)}`"
                  @click="preview = line.item"
                >
                  <i class="icon icon-eye"></i>
                </button>
                <button
                  v-if="arming === line.key"
                  type="button"
                  class="tray-remove"
                  @click="remove(line)"
                >
                  Remove
                </button>
                <span v-else-if="line.uids.length" class="stepper">
                  <button
                    type="button"
                    class="icon-button"
                    :aria-label="`Remove ${line.uids.length > 1 ? 'one ' : ''}${name(line)}`"
                    @click="decrease(line)"
                  >
                    <i :class="['icon', line.uids.length > 1 ? 'icon-minus' : 'icon-trash']"></i>
                  </button>
                  <template v-if="!single.has(line.kind)">
                    <span class="tray-quantity">{{ line.uids.length }}</span>
                    <button
                      type="button"
                      class="icon-button"
                      :aria-label="`Add one ${name(line)}`"
                      :aria-disabled="atLimit(line) || undefined"
                      @click="attempt(() => store.copyPoolItem(line.uids[0]!))"
                    >
                      <i class="icon icon-plus"></i>
                    </button>
                  </template>
                </span>
              </div>
            </template>
          </ObjectCell>
        </section>
        <div v-if="!groups.length" class="tray-empty">
          <p class="muted">Tray is empty</p>
          <RouterLink v-if="sheet" class="link" to="/search">Search components</RouterLink>
        </div>
      </div>
    </DropZone>
    <button
      v-if="sheet && !building && team.inventory.length"
      type="button"
      class="primary tray-next"
      @click="router.push({ name: 'build' })"
    >
      Go to Build
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
  padding: 8px 12px 8px 16px;
  transition: background-color 0.3s;
}
.tray-look {
  position: absolute;
  top: 8px;
  left: 16px;
  z-index: 1;
  width: 68px;
  min-height: 68px;
  padding: 0;
  background: none;
  clip-path: none;
}
.tray-look:hover,
.tray-look:active:not(:disabled) {
  background: none;
  border-color: transparent;
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
  border-color: var(--text);
}
.tray-name {
  min-height: 0;
  padding: 0;
  background: none;
  border: 0;
  color: var(--text);
  font-weight: 700;
  text-align: left;
  overflow-wrap: anywhere;
}
.tray-name:hover {
  background: none;
  text-decoration: underline;
  text-decoration-color: var(--strong);
  text-underline-offset: 3px;
}
.tray-quantity {
  align-self: center;
  min-width: 28px;
  color: var(--placed);
  font: 400 16px / 1 var(--pixel-font);
  font-variant-numeric: tabular-nums;
  text-align: center;
}
.tray-trait {
  display: block;
  margin-top: 2px;
  color: var(--muted);
  font-size: var(--fs-13);
  overflow-wrap: anywhere;
}
.tray-in-build {
  display: block;
  margin-top: 2px;
  color: var(--placed);
  font-size: var(--fs-13);
  font-weight: 700;
}
.tray-remove {
  min-height: var(--control-compact);
  padding: 0 var(--space-12);
  background: var(--danger-mark);
  color: var(--ground);
  font-weight: 700;
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
  justify-content: flex-end;
  gap: 4px;
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
.tray-eye {
  display: none;
}
/* The narrow sidebar has no room beside the name, so its actions take their own row. */
@media (min-width: 1100px) {
  .tray-look {
    display: none;
  }
  .tray-eye {
    display: inline-flex;
  }
  .tray-item :deep(> .cell-aside) {
    grid-column: 2;
    grid-row: auto;
  }
  .parts-tray .tray-item.object-cell-row:has(> .cell-aside) {
    grid-template-columns: 68px minmax(0, 1fr);
  }
}
@media (max-width: 1099px) {
  .tray-item :deep(> .cell-aside) {
    align-self: center;
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
