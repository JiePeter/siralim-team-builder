<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { storeToRefs } from "pinia";
import { useMediaQuery } from "@vueuse/core";
import { useSearchStore } from "@/stores/search";
import { blankCondition, type Condition } from "@/domain/discovery";
import FacetOptions from "./FacetOptions.vue";
import { filterState } from "./filters";

const store = useSearchStore();
const { conditions, scope, facets, filtersOpened } = storeToRefs(store);
const phone = useMediaQuery("(max-width: 767px)");
const rows = ref<HTMLElement | null>(null);

const state = computed(() => filterState(conditions.value, phone.value, filtersOpened.value));
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
    filtersOpened.value = true;
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
  filtersOpened.value = false;
  store.run();
}
</script>

<template>
  <section class="mechanism-filters" aria-label="Mechanic filters">
    <div v-show="!state.collapsed" ref="rows">
      <div v-for="(condition, index) in conditions" :key="index" class="mechanism-row">
        <select
          class="filter-category"
          :aria-label="`Mechanic category ${index + 1}`"
          :value="condition.category"
          @change="update(condition, 'category', ($event.target as HTMLSelectElement).value)"
        >
          <FacetOptions
            :options="facetRow(index).categories"
            :selected="condition.category"
            namespace="category"
            all="All mechanics"
          />
        </select>
        <button
          v-if="conditions.length > 1"
          type="button"
          class="icon-button filter-remove"
          :aria-label="`Remove filter ${index + 1}`"
          @click="remove(index)"
        >
          <i class="icon icon-close"></i>
        </button>
        <template v-if="condition.category">
          <select
            class="filter-relation"
            :aria-label="`Mechanic interaction ${index + 1}`"
            :value="condition.relation"
            @change="update(condition, 'relation', ($event.target as HTMLSelectElement).value)"
          >
            <FacetOptions
              :options="facetRow(index).relations"
              :selected="condition.relation"
              :namespace="`${condition.category}-relation`"
            />
          </select>
          <select
            class="filter-value"
            :aria-label="`Mechanic target ${index + 1}`"
            :value="condition.value"
            @change="update(condition, 'value', ($event.target as HTMLSelectElement).value)"
          >
            <FacetOptions
              :options="facetRow(index).values"
              :selected="condition.value"
              :namespace="`${condition.category}-value`"
            />
          </select>
        </template>
      </div>
    </div>
    <div class="mechanism-toolbar">
      <button v-if="state.canAdd" type="button" @click="add">
        <i class="icon icon-plus"></i>Mechanic
      </button>
      <select v-if="state.showScope" v-model="scope" aria-label="Match scope" @change="store.run()">
        <option value="action">Same action</option>
        <option value="rule">Same rule</option>
        <option value="component">Whole component</option>
      </select>
      <button
        v-if="state.showClear"
        type="button"
        class="clear"
        aria-label="Clear mechanic filters"
        title="Clear mechanic filters"
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
