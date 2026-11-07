<script setup lang="ts">
import { computed, provide, ref, watch } from "vue";
import { computedAsync } from "@vueuse/core";
import {
  ListboxContent,
  ListboxFilter,
  ListboxGroup,
  ListboxGroupLabel,
  ListboxItem,
  ListboxRoot,
} from "reka-ui";
import { storeToRefs } from "pinia";
import type { Catalog } from "@/data";
import type { Position } from "@/domain/assembly";
import { placementRefusal, whereIs } from "@/domain/placement";
import { applicable, type Attributes } from "@/domain/attributes";
import { blankCondition } from "@/domain/discovery";
import type { Equipment, Team } from "@/domain/team";
import { matchesText } from "@/domain/values";
import { MECHANIC_SEARCH, usePickerSearchStore, useSearchStore } from "@/stores/search";
import { t } from "@/i18n";
import AttributeFilters from "./AttributeFilters.vue";
import MechanicFilters from "./MechanicFilters.vue";
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
import { lineKey, placementLabel, useEntity } from "./tray";

const PAGE = 50;

const props = defineProps<{
  field: PickerField;
  /** Names the field in the search box. */
  label: string;
  team: Team;
  catalog: Catalog;
  kindOf: (id: string) => string | undefined;
  /** The position a choice goes to, so a choice it refuses says why before it is tapped. */
  target?: Position;
  /** The field holds something, so a choice replaces it. */
  replacing?: boolean;
}>();
const emit = defineEmits<{
  pick: [uid: string];
  take: [id: string];
}>();

const store = useTeamStore();
const entity = useEntity();
const carriers = (id: string) => store.index?.carriers.get(id);
const displayed = (item: Equipment) => shownAs(store.index, item, props.field);

const q = ref("");
const attributes = ref<Attributes>({});
const shown = ref(PAGE);
const filtersShown = ref(false);

const search = usePickerSearchStore();
provide(MECHANIC_SEARCH, usePickerSearchStore as unknown as typeof useSearchStore);
const { conditions, scope } = storeToRefs(search);
conditions.value = [blankCondition()];
scope.value = "action";
search.filtersOpened = false;
search.kind = fieldKind[props.field];
const activeFilters = computed(
  () =>
    Object.keys(applicable(fieldKind[props.field], attributes.value)).length +
    conditions.value.filter((c) => c.category).length,
);
watch(
  [q, attributes],
  () => {
    shown.value = PAGE;
    search.q = q.value;
    search.attributes = attributes.value;
    search.run();
  },
  { immediate: true },
);

const found = computedAsync(
  () =>
    candidates(
      props.field,
      q.value,
      props.catalog,
      attributes.value,
      conditions.value.map((c) => ({ ...c })),
      scope.value,
    ),
  null,
  { lazy: false },
);

const trayItems = computed(() => {
  const inventory = props.team.inventory;
  if (props.field === "characterBase" || props.field === "characterAnointment")
    return characterChoices(inventory, props.field, props.catalog);
  if (props.field === "artifactTrait")
    return inventory.filter((item) => {
      const kind = props.kindOf(item.id);
      const carried = kind === "trait" ? carriers(item.id) : undefined;
      return kind === "material" || (!!carried && carriedInto(carried, "artifactTrait"));
    });
  if (!store.index) return [];
  return poolChoices(inventory, props.field, props.kindOf, store.index.rules.slot_kinds, carriers);
});

/** Matching tray items; identical instances are one choice with a count. */
const inTray = computed(() => {
  const matched = found.value?.matched;
  const narrowed = !!activeFilters.value;
  const lines = new Map<string, { item: Equipment; count: number }>();
  for (const item of trayItems.value) {
    const name = component(displayed(item))?.name ?? "";
    const named = !narrowed && matchesText(name, q.value);
    if (matched && !matched.has(displayed(item)) && !named) continue;
    const key = lineKey(item);
    const line = lines.get(key);
    if (line) line.count++;
    else lines.set(key, { item, count: 1 });
  }
  return [...lines.values()];
});

const more = computed(() => {
  const trayed = new Set(inTray.value.map(({ item }) => entity(item.id)));
  return (found.value?.items ?? []).filter((c) => !trayed.has(entity(c.id)));
});

/** One-per-team components already placed cannot be placed again. */
const unique = computed(() => props.field === "relic" || props.field === "characterAnointment");
const placedAt = (id: string) =>
  whereIs(props.team, id, entity).placed.map(placementLabel).join(", ");
const refusal = (id: string) =>
  props.target && store.index ? placementRefusal(store.index, props.team, props.target, id) : null;
const note = (id: string) => {
  const refused = refusal(id);
  if (refused) return { text: refused, refused: true };
  const placed = placedAt(id);
  return placed ? { text: placed } : null;
};
/** The field already holds this component. */
const here = (id: string) =>
  whereIs(props.team, id, entity).placed.some(
    (at) =>
      "slot" in at &&
      at.slot === props.target?.slot &&
      at.field === props.target.field &&
      (props.target.index === undefined || at.index === props.target.index),
  );
const blocked = (id: string) => here(id) || !!refusal(id) || (unique.value && !!placedAt(id));
const keyLabel = (name: string) =>
  t(props.replacing ? "tray.picker.replaceWith" : "tray.picker.place", { name });

function choose(value: string) {
  const [source, key] = [value.slice(0, value.indexOf(":")), value.slice(value.indexOf(":") + 1)];
  if (source === "tray") emit("pick", key);
  else emit("take", key);
}

/** A pointer on the card opens its text; the key beside it, or Enter on the list, places it. */
function selected(event: CustomEvent<{ originalEvent: Event }>, value: string) {
  event.preventDefault();
  if (!(event.detail.originalEvent as MouseEvent).detail) choose(value);
}
</script>

<template>
  <ListboxRoot class="picker" highlight-on-hover>
    <slot name="current" />
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
          v-if="found?.facets.length || conditions.length"
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
      <div v-show="filtersShown" class="picker-filters">
        <AttributeFilters v-if="found?.facets.length" v-model="attributes" :facets="found.facets" />
        <MechanicFilters />
      </div>
    </div>
    <ListboxContent class="picker-list">
      <ListboxGroup v-if="inTray.length">
        <ListboxGroupLabel class="picker-label">{{ $t("tray.picker.inTray") }}</ListboxGroupLabel>
        <ListboxItem
          v-for="{ item, count } in inTray"
          :key="item.uid"
          :value="`tray:${item.uid}`"
          class="picker-choice"
          @select="selected($event as never, `tray:${item.uid}`)"
        >
          <ResultCard
            v-if="component(displayed(item))"
            compact
            :item="component(displayed(item))!"
            :note="{ text: $t('tray.picker.inTrayCount', { count }) }"
          >
            <button
              type="button"
              class="icon-button place-key"
              :aria-label="keyLabel(component(displayed(item))!.name)"
              @click.stop="choose(`tray:${item.uid}`)"
            >
              <i :class="['icon', replacing ? 'icon-replace' : 'icon-plus']"></i>
            </button>
          </ResultCard>
        </ListboxItem>
      </ListboxGroup>
      <ListboxGroup v-if="more.length">
        <ListboxGroupLabel class="picker-label"
          >{{ $t("tray.picker.moreMatches") }}
          <span class="picker-count">{{ more.length }}</span></ListboxGroupLabel
        >
        <ListboxItem
          v-for="item in more.slice(0, shown)"
          :key="item.id"
          :value="`data:${item.id}`"
          :disabled="blocked(item.id)"
          :data-note="note(item.id)?.text"
          class="picker-choice"
          @select="selected($event as never, `data:${item.id}`)"
        >
          <ResultCard compact :item="item" :line="item.detail" :note="note(item.id)">
            <button
              v-if="!blocked(item.id)"
              type="button"
              class="icon-button place-key"
              :aria-label="keyLabel(item.name)"
              @click.stop="choose(`data:${item.id}`)"
            >
              <i :class="['icon', replacing ? 'icon-replace' : 'icon-plus']"></i>
            </button>
          </ResultCard>
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
.filter-toggle.active,
.filter-toggle.active:hover {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--on-accent);
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
.picker-count {
  font: 400 16px / 1 var(--pixel-font);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
}
.picker-choice {
  margin-bottom: 2px;
}
.picker-choice > .result-card {
  border-color: var(--line);
}
.picker-choice:has(> .result-card)[data-highlighted] > .result-card {
  background: var(--raised);
}
.picker-choice[data-disabled] :deep(.cell-plate) {
  opacity: 0.4;
}
.place-key {
  color: var(--accent);
}
.place-key:has(.icon-replace) {
  color: var(--text);
}
/* Inside the dialog the empty line needs no box of its own. */
.empty {
  padding: var(--space-16) 0 0;
  background: none;
  border: 0;
}
</style>
