<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { computedAsync } from "@vueuse/core";
import {
  ListboxContent,
  ListboxFilter,
  ListboxGroup,
  ListboxGroupLabel,
  ListboxItem,
  ListboxRoot,
} from "reka-ui";
import type { Position } from "@/domain/assembly";
import { onePerTeam, placedParts, placementRefusal, type Placement } from "@/domain/placement";
import { applicable, type Attributes } from "@/domain/attributes";
import { blankCondition, type Condition, type Scope } from "@/domain/discovery";
import { itemId, type Equipment } from "@/domain/team";
import { matchesText } from "@/domain/values";
import { t } from "@/i18n";
import AttributeFilters from "./AttributeFilters.vue";
import MechanicFilters from "./MechanicFilters.vue";
import CellPlate from "./CellPlate.vue";
import { propertyCount } from "./presentation";
import ResultCard from "./ResultCard.vue";
import { useTeamStore } from "@/stores/team";
import {
  carriedInto,
  characterChoices,
  fieldKind,
  poolChoices,
  shownAs,
  type PickerField,
} from "./assembly";
import { candidates } from "./candidates";
import { component } from "./components";
import { toastError } from "./toast";
import { lineKey, useEntity } from "./tray";

const PAGE = 50;

const props = defineProps<{
  field: PickerField;
  /** Names the field in the search box. */
  label: string;
  /** The position a choice goes to, so a choice it refuses says why before it is tapped. */
  target?: Position;
  /** The component the field holds, shown above the search with `#current-actions`. */
  current?: string;
}>();
const emit = defineEmits<{
  pick: [uid: string];
  take: [id: string];
}>();

const store = useTeamStore();
const entity = useEntity();
const carriers = (id: string) => store.index?.carriers.get(id);
const kindOf = (id: string) => store.index?.kinds.get(id);
const displayed = (item: Equipment) => shownAs(store.index, item, props.field);

const q = ref("");
const attributes = ref<Attributes>({});
const conditions = ref<Condition[]>([blankCondition()]);
const scope = ref<Scope>("action");
const shown = ref(PAGE);
const filtersShown = ref(false);

const activeFilters = computed(
  () =>
    Object.keys(applicable(fieldKind[props.field], attributes.value)).length +
    conditions.value.filter((c) => c.category).length,
);
watch([q, attributes], () => {
  shown.value = PAGE;
});

const found = computedAsync(
  () =>
    candidates(
      props.field,
      q.value,
      store.index!.catalog,
      attributes.value,
      conditions.value.map((c) => ({ ...c })),
      scope.value,
    ),
  null,
  {
    lazy: false,
    onError(error) {
      console.error(error);
      toastError(t("search.loadFailed"));
    },
  },
);

const trayItems = computed(() => {
  const inventory = store.team.inventory;
  const at = store.index;
  if (!at) return [];
  if (props.field === "characterBase" || props.field === "characterAnointment")
    return characterChoices(inventory, props.field, at.catalog);
  if (props.field === "artifactTrait")
    return inventory.filter((item) => {
      const kind = kindOf(item.id);
      const carried = kind === "trait" ? carriers(item.id) : undefined;
      return kind === "material" || (!!carried && carriedInto(carried, "artifactTrait"));
    });
  return poolChoices(inventory, props.field, kindOf, at.rules.slot_kinds, carriers);
});

/** Matching tray items; identical instances are one choice with a count. */
const inTray = computed(() => {
  const matched = found.value?.matched;
  const narrowed = !!activeFilters.value;
  const lines = new Map<
    string,
    { item: Equipment; count: number; page: ReturnType<typeof component> }
  >();
  for (const item of trayItems.value) {
    const page = component(displayed(item));
    const named = !narrowed && matchesText(page?.name ?? "", q.value);
    if (matched && !matched.has(displayed(item)) && !named) continue;
    const key = lineKey(item);
    const line = lines.get(key);
    if (line) line.count++;
    else lines.set(key, { item, count: 1, page });
  }
  return [...lines.values()];
});

const more = computed(() => {
  const trayed = new Set(inTray.value.map(({ item }) => entity(item.id)));
  return (found.value?.items ?? []).filter((c) => !trayed.has(entity(c.id)) && !here(c.id));
});

/** Nothing narrows the list and nothing precedes it. */
const listed = computed(() => !q.value.trim() && !activeFilters.value && !inTray.value.length);

/** A Relic is chosen by its look and name; its rank effects belong to its editor. */
const tiles = computed(() => props.field === "relic");
/** One-per-team components already placed cannot be placed again; the Specialization field swaps its sole occupant. */
const unique = computed(
  () => props.field !== "characterBase" && onePerTeam(fieldKind[props.field]),
);
/** Every placement in the team, grouped by what each component stands for. */
const placements = computed(() => {
  const groups = new Map<string, Placement[]>();
  for (const part of placedParts(store.team)) {
    const key = entity(itemId(part.ref)!);
    const group = groups.get(key);
    if (group) group.push(part.at);
    else groups.set(key, [part.at]);
  }
  return groups;
});
const placedOf = (id: string) => placements.value.get(entity(id)) ?? [];
const refusal = (id: string) =>
  props.target && store.index ? placementRefusal(store.index, store.team, props.target, id) : null;
const note = (id: string) => {
  const refused = refusal(id);
  return refused ? { text: refused, refused: true } : null;
};
/** Copies already in the team, marked on the plate. */
const placedCount = (id: string) => {
  const n = placedOf(id).length;
  return n > 1 ? n : n > 0;
};
/** The field already holds this component. */
const here = (id: string) =>
  placedOf(id).some(
    (at) =>
      "slot" in at &&
      at.slot === props.target?.slot &&
      at.field === props.target.field &&
      (props.target.index === undefined || at.index === props.target.index),
  );
const blocked = (id: string) =>
  here(id) || !!refusal(id) || (unique.value && placedOf(id).length > 0);
</script>

<template>
  <ListboxRoot class="picker" highlight-on-hover>
    <div v-if="current && component(current)" class="picker-current">
      <ResultCard :item="component(current)!" compact fixed link>
        <slot name="current-actions" />
      </ResultCard>
    </div>
    <div class="picker-search">
      <div class="picker-input">
        <i class="icon icon-search"></i>
        <ListboxFilter
          v-model="q"
          auto-focus
          :aria-label="$t('tray.picker.search', { label })"
          :placeholder="$t('tray.picker.placeholder')"
        />
        <button
          type="button"
          :class="['filter-toggle', { active: activeFilters }]"
          :aria-expanded="filtersShown"
          :aria-label="
            activeFilters
              ? $t('search.filtersCount', { count: activeFilters })
              : $t('search.filters')
          "
          :title="$t('search.filters')"
          @click="filtersShown = !filtersShown"
        >
          <i class="icon icon-filter"></i
          ><span v-if="activeFilters" class="filter-count">{{ activeFilters }}</span>
        </button>
      </div>
      <div v-if="filtersShown" class="picker-filters">
        <AttributeFilters v-if="found?.facets.length" v-model="attributes" :facets="found.facets" />
        <MechanicFilters
          v-model:conditions="conditions"
          v-model:scope="scope"
          :rows="found?.conditionFacets ?? []"
        />
      </div>
    </div>
    <ListboxContent class="picker-list">
      <ListboxGroup v-if="inTray.length" :class="{ 'tile-group': tiles }">
        <ListboxGroupLabel class="picker-label">{{ $t("tray.picker.inTray") }}</ListboxGroupLabel>
        <ListboxItem
          v-for="{ item, count, page } in inTray"
          :disabled="unique && placedOf(item.id).length > 0"
          :key="item.uid"
          :value="item.uid"
          :class="tiles ? 'picker-tile' : 'picker-choice'"
          @select.prevent="emit('pick', item.uid)"
        >
          <template v-if="tiles && page">
            <CellPlate :data="page" :added="count > 1 ? count : false" />
            <span class="tile-name">{{ page.name }}</span>
          </template>
          <ResultCard
            v-else-if="page"
            compact
            fixed
            :item="page"
            :line="page.kind === 'specialization' ? '' : undefined"
          >
            <template #plate>
              <CellPlate
                :data="page"
                :properties="propertyCount(item)"
                :added="count > 1 ? count : false"
              />
            </template>
          </ResultCard>
        </ListboxItem>
      </ListboxGroup>
      <ListboxGroup v-if="more.length" :class="{ 'tile-group': tiles }">
        <ListboxGroupLabel class="picker-label"
          >{{ $t(listed ? "tray.picker.all" : "tray.picker.moreMatches") }}
          <span class="count">{{ more.length }}</span></ListboxGroupLabel
        >
        <ListboxItem
          v-for="item in more.slice(0, shown)"
          :key="item.id"
          :value="item.id"
          :disabled="blocked(item.id)"
          :class="tiles ? 'picker-tile' : 'picker-choice'"
          :title="note(item.id)?.text"
          @select.prevent="emit('take', item.id)"
        >
          <template v-if="tiles">
            <CellPlate :data="item" :added="placedCount(item.id)" />
            <span class="tile-name">{{ item.name }}</span>
          </template>
          <ResultCard
            v-else
            compact
            fixed
            :item="item"
            :line="item.detail"
            :note="note(item.id)"
            :added="placedCount(item.id)"
          />
        </ListboxItem>
      </ListboxGroup>
    </ListboxContent>
    <button
      v-if="more.length > shown"
      type="button"
      class="choice choice-action"
      @click="shown += PAGE"
    >
      <i class="icon icon-down"></i
      >{{ $t("tray.picker.showMore", { count: Math.min(PAGE, more.length - shown) }) }}
    </button>
    <p v-if="found && !inTray.length && !more.length" class="empty">
      {{ $t("tray.picker.noMatches", { label }) }}
    </p>
  </ListboxRoot>
</template>

<style scoped>
.picker-current {
  padding-bottom: var(--space-12);
}
.picker-current :deep(.result-action) {
  display: flex;
  gap: var(--space-4);
}
.picker-search {
  position: sticky;
  top: 0;
  z-index: 1;
  margin: 0 calc(-1 * var(--space-16));
  padding: var(--space-12) var(--space-16);
  background: var(--cell);
  border-bottom: 1px solid var(--line);
}
.picker-search:first-child {
  margin-top: calc(-1 * var(--space-16));
}
.picker-input {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-8);
}
.picker-input > .icon {
  position: absolute;
  z-index: 1;
  left: var(--space-12);
  color: var(--muted);
  pointer-events: none;
}
.picker-input > input {
  flex: 1;
  min-width: 0;
  padding-left: 36px;
}
.filter-toggle {
  flex: none;
  min-height: var(--field);
  padding: 0 var(--space-12);
}
.filter-count {
  margin-left: var(--space-8);
  font: 400 16px / 1 var(--pixel-font);
}
.picker-filters {
  max-height: 50dvh;
  margin-top: var(--space-8);
  overflow: auto;
}
.picker-label {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  min-height: var(--control-compact);
  margin-top: var(--space-4);
  color: var(--muted);
  font-size: var(--fs-12);
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.count {
  color: var(--muted);
  font: 400 11px / 1 var(--pixel-font);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
}
.picker-choice {
  margin-bottom: 2px;
}
.tile-group {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
  gap: var(--space-8);
}
.tile-group > .picker-label {
  grid-column: 1 / -1;
}
.picker-tile {
  display: grid;
  justify-items: center;
  align-content: start;
  gap: var(--space-6);
  padding: var(--space-8) var(--space-4);
  cursor: pointer;
  font-size: var(--fs-12);
  line-height: 15px;
  text-align: center;
}
.picker-tile[data-highlighted] {
  background: var(--raised);
}
.picker-tile[data-disabled] {
  cursor: default;
  opacity: 0.4;
}
.picker-choice:has(> .result-card)[data-highlighted] > .result-card {
  background: var(--raised);
}
.picker-choice[data-disabled] > .result-card {
  cursor: default;
}
.picker-choice[data-disabled] :deep(.cell-plate) {
  opacity: 0.4;
}
/* Inside the dialog the empty line needs no box of its own. */
.empty {
  padding: var(--space-16) 0 0;
  background: none;
  border: 0;
}
</style>
