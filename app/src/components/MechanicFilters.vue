<script setup lang="ts">
import { computed, inject, nextTick, ref } from "vue";
import { storeToRefs } from "pinia";
import { useMediaQuery } from "@vueuse/core";
import { t } from "@/i18n";
import { useFillStore } from "@/stores/fill";
import { MECHANIC_SEARCH, useSearchStore } from "@/stores/search";
import { blankCondition, type Condition } from "@/domain/discovery";
import { DIALOG_ACTIONS } from "./dialog";
import FacetOptions from "./FacetOptions.vue";
import { filterState } from "./filters";

/** Which page's mechanic query the rows edit; the provided one by default. */
const props = defineProps<{ fill?: boolean }>();
const search = props.fill ? undefined : inject(MECHANIC_SEARCH, useSearchStore)();
const fillQuery = search ? undefined : useFillStore();
const store = search ?? fillQuery!;
const { conditions, scope, facets } = storeToRefs(store);
const dialogActions = inject(DIALOG_ACTIONS, null);
const phone = useMediaQuery("(max-width: 767px)");
const rows = ref<HTMLElement | null>(null);

const state = computed(() =>
  filterState(conditions.value, phone.value && !!search, search?.filtersOpened ?? false),
);
const facetRow = (index: number) =>
  facets.value.conditions[index] ?? { categories: [], relations: [], values: [] };

function update(condition: Condition, field: keyof Condition, value: string) {
  condition[field] = value;
  if (field === "category") {
    condition.relation = "";
    condition.value = "";
  }
  store.run();
}

function remove(index: number) {
  conditions.value.splice(index, 1);
  store.run();
}

async function add() {
  if (state.value.collapsed) {
    search!.filtersOpened = true;
    await nextTick();
    rows.value?.querySelector("select")?.focus();
    return;
  }
  conditions.value.push(blankCondition());
  store.run();
}

function clear() {
  conditions.value = [blankCondition()];
  scope.value = "action";
  if (search) search.filtersOpened = false;
  if (fillQuery) fillQuery.mechanism = "";
  store.run();
}
</script>

<template>
  <section
    class="mechanism-filters"
    :class="{ 'in-sheet': fill }"
    :aria-label="t('search.mechanic.filters')"
  >
    <Teleport
      v-if="fill && dialogActions && (state.showClear || fillQuery?.mechanism)"
      defer
      :to="`#${dialogActions}`"
    >
      <button
        type="button"
        class="clear"
        :aria-label="t('search.mechanic.clear')"
        :title="t('search.mechanic.clear')"
        @click="clear"
      >
        <i class="icon icon-trash"></i>
      </button>
    </Teleport>
    <div v-show="!state.collapsed" ref="rows">
      <div v-for="(condition, index) in conditions" :key="index" class="mechanism-row">
        <select
          class="filter-category"
          :aria-label="t('search.mechanic.category', { n: index + 1 })"
          :value="condition.category"
          @change="update(condition, 'category', ($event.target as HTMLSelectElement).value)"
        >
          <FacetOptions
            :options="facetRow(index).categories"
            :selected="condition.category"
            namespace="category"
            :all="t('search.mechanic.all')"
          />
        </select>
        <button
          v-if="conditions.length > 1"
          type="button"
          class="icon-button filter-remove"
          :aria-label="t('search.mechanic.remove', { n: index + 1 })"
          @click="remove(index)"
        >
          <i class="icon" :class="fill ? 'icon-minus' : 'icon-close'"></i>
        </button>
        <template v-if="condition.category">
          <select
            class="filter-relation"
            :aria-label="t('search.mechanic.interaction', { n: index + 1 })"
            :value="condition.relation"
            @change="update(condition, 'relation', ($event.target as HTMLSelectElement).value)"
          >
            <FacetOptions
              :options="facetRow(index).relations"
              :selected="condition.relation"
              :namespace="`${condition.category}-relation`"
              :all="fill ? t('fill.allInteractions') : undefined"
            />
          </select>
          <select
            class="filter-value"
            :aria-label="t('search.mechanic.target', { n: index + 1 })"
            :value="condition.value"
            @change="update(condition, 'value', ($event.target as HTMLSelectElement).value)"
          >
            <FacetOptions
              :options="facetRow(index).values"
              :selected="condition.value"
              :namespace="`${condition.category}-value`"
              :all="fill ? t('fill.allTargets') : undefined"
            />
          </select>
        </template>
      </div>
    </div>
    <div class="mechanism-toolbar" :class="{ end: fill }">
      <button v-if="state.canAdd" type="button" @click="add">
        <i class="icon icon-plus"></i>{{ t("search.mechanic.add") }}
      </button>
      <select
        v-if="state.showScope"
        v-model="scope"
        :aria-label="t('search.mechanic.scope')"
        @change="store.run()"
      >
        <option value="action">{{ t("search.mechanic.action") }}</option>
        <option value="rule">{{ t("search.mechanic.rule") }}</option>
        <option value="component">{{ t("search.mechanic.component") }}</option>
      </select>
      <button
        v-if="state.showClear && !fill"
        type="button"
        class="clear"
        :aria-label="t('search.mechanic.clear')"
        :title="t('search.mechanic.clear')"
        @click="clear"
      >
        <i class="icon icon-close"></i>
      </button>
    </div>
  </section>
</template>

<style scoped>
.mechanism-filters {
  flex-shrink: 0;
  max-height: 45vh;
  margin: 12px 0;
  overflow: auto;
}
.mechanism-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) var(--control);
  gap: 6px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line);
}
.filter-category {
  grid-column: 1 / 3;
}
.mechanism-row:not(:has(.filter-remove)) .filter-category {
  grid-column: 1 / -1;
}
.filter-remove {
  grid-column: 3;
  height: var(--field);
}
.filter-relation {
  grid-column: 1;
}
.filter-value {
  grid-column: 2 / 4;
}
.mechanism-row select {
  min-width: 0;
}
.mechanism-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.mechanism-toolbar.end {
  justify-content: flex-end;
}
.mechanism-toolbar:empty {
  display: none;
}
.in-sheet {
  max-height: none;
  margin: 0;
  overflow: visible;
}
.in-sheet .mechanism-row:last-child {
  margin-bottom: var(--space-12);
  padding-bottom: 0;
  border-bottom: 0;
}
.mechanism-toolbar button {
  font-size: var(--fs-13);
}
.mechanism-toolbar select {
  width: auto;
  min-height: var(--control);
  font-size: var(--fs-13);
}
@media (max-width: 767px) {
  .mechanism-filters {
    max-height: none;
    overflow: visible;
  }
  .mechanism-toolbar button,
  .mechanism-toolbar select {
    min-height: var(--field);
  }
}
</style>
