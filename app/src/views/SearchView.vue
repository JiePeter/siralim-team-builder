<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { storeToRefs } from "pinia";
import { useDebounceFn, useIntersectionObserver, useMediaQuery } from "@vueuse/core";
import { t } from "@/i18n";
import { useSearchStore } from "@/stores/search";
import AddButton from "@/components/AddButton.vue";
import AttributeFilters from "@/components/AttributeFilters.vue";
import FacetOptions from "@/components/FacetOptions.vue";
import ResultCard from "@/components/ResultCard.vue";
import type { Attributes } from "@/domain/attributes";

const route = useRoute();
const store = useSearchStore();
const { q, kind, attributes, items, total, facets, ready, narrowed } = storeToRefs(store);
const filtersShown = ref(false);
const activeFilters = computed(
  () => (kind.value ? 1 : 0) + Object.values(attributes.value).filter(Boolean).length,
);
const phone = useMediaQuery("(max-width: 767px)");

const addableKinds = new Set([
  "creature",
  "trait",
  "material",
  "spell",
  "relic",
  "specialization",
  "perk",
]);
const detail = computed(() => route.name === "object");
const count = computed(() => {
  const found = t("search.results", total.value);
  return total.value > items.value.length
    ? t("search.showing", { found, shown: items.value.length })
    : found;
});
/** Cards are mounted a batch at a time while the end of the list is near the viewport. */
const BATCH = 20;
const rendered = ref(BATCH);
const shownItems = computed(() => items.value.slice(0, rendered.value));
const listEnd = ref<HTMLElement | null>(null);
const nearEnd = ref(false);
useIntersectionObserver(listEnd, ([entry]) => (nearEnd.value = !!entry?.isIntersecting), {
  rootMargin: "600px",
});
watch(items, () => (rendered.value = BATCH));
watch([nearEnd, rendered], () => {
  if (nearEnd.value && rendered.value < items.value.length)
    requestAnimationFrame(() => (rendered.value += BATCH));
});
const typed = useDebounceFn(() => store.run(), 180);

function changeKind() {
  attributes.value = {};
  store.run();
}

function narrow(next: Attributes) {
  attributes.value = next;
  store.run();
}

onMounted(() => {
  if (!ready.value) store.run();
});
</script>

<template>
  <div :class="['explore', detail ? 'pane-detail' : 'pane-list', { browsing: !narrowed }]">
    <aside class="search-panel">
      <label for="search">{{ t("search.label") }}</label>
      <div class="search-row">
        <input
          id="search"
          v-model="q"
          :placeholder="t('search.placeholder')"
          autocomplete="off"
          @input="typed"
        />
        <button
          type="button"
          :class="['filter-toggle', { active: activeFilters }]"
          :aria-expanded="filtersShown"
          :aria-label="
            activeFilters ? t('search.filtersCount', { count: activeFilters }) : t('search.filters')
          "
          :title="t('search.filters')"
          @click="filtersShown = !filtersShown"
        >
          <i class="icon icon-filter"></i
          ><span v-if="activeFilters" class="filter-count">{{ activeFilters }}</span>
        </button>
      </div>
      <div :class="['search-filters', { open: filtersShown }]">
        <label for="kind">{{ t("search.type") }}</label>
        <select id="kind" v-model="kind" @change="changeKind">
          <FacetOptions
            :options="facets.kinds"
            :selected="kind"
            namespace="kind"
            :all="t('search.allTypes')"
          />
        </select>
        <AttributeFilters
          v-if="facets.attributes.length"
          class="search-attributes"
          :facets="facets.attributes"
          :model-value="attributes"
          counts
          @update:model-value="narrow"
        />
      </div>
      <div v-if="narrowed" class="result-count muted">{{ count }}</div>
      <div v-if="narrowed" class="results">
        <template v-if="items.length">
          <ResultCard
            v-for="item in shownItems"
            :key="item.id"
            class="result"
            link
            :compact="phone"
            :item="item"
            :selected="detail && route.params.id === item.id"
          >
            <template v-if="addableKinds.has(item.kind)" #plate>
              <AddButton :item="item" :plate="item" />
            </template>
          </ResultCard>
          <div ref="listEnd" class="list-end"></div>
        </template>
        <p v-else class="empty">{{ t("search.noMatches") }}</p>
      </div>
    </aside>
    <section class="workspace">
      <RouterView />
    </section>
  </div>
</template>

<style scoped>
.explore {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  min-height: calc(100dvh - var(--header-height) - var(--footer-height));
}
.search-panel {
  position: sticky;
  top: var(--header-height);
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: calc(100dvh - var(--header-height) - var(--footer-height));
  padding: 8px 16px 0;
  background: var(--cell);
}
.search-row {
  display: flex;
  flex-shrink: 0;
  gap: var(--space-8);
}
.search-row > input {
  flex: 1;
  min-width: 0;
}
.filter-toggle {
  display: none;
}
.filter-toggle[aria-expanded="true"] {
  background: var(--ground);
  border-color: var(--accent);
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
.search-filters {
  display: contents;
}
.search-panel > label,
.search-filters > label {
  margin: 12px 0 6px;
  color: var(--muted);
  font-size: var(--fs-12);
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.search-filters > select {
  flex-shrink: 0;
}
.search-attributes {
  flex-shrink: 0;
  margin-top: 12px;
}
.result-count {
  flex-shrink: 0;
  min-height: 34px;
  padding: 8px 0;
  font-size: var(--fs-12);
}
.results {
  display: grid;
  flex: 1;
  align-content: start;
  gap: 2px;
  min-height: 0;
  margin: 0 -16px;
  overflow: auto;
  background: var(--ground);
}
.results > .empty {
  margin: 16px;
}
.result {
  padding: 12px 16px;
}
@media (hover: hover) {
  .result:hover {
    background: var(--raised);
  }
  .result:hover :deep(.result-name) {
    text-decoration-color: var(--text);
  }
}
.workspace {
  min-width: 0;
  padding: var(--gutter);
}

@media (min-width: 768px) {
  .search-panel {
    border-right: 1px solid var(--line);
  }
  .results {
    gap: 0;
    background: var(--cell);
    border-top: 1px solid var(--line);
  }
  .result:not(.selected) {
    border-bottom-color: var(--line);
  }
}
@media (max-width: 767px) {
  .explore {
    display: block;
    min-height: 0;
  }
  .search-panel {
    position: static;
    height: auto;
    padding: 4px 16px 0;
    background: var(--ground);
  }
  .results {
    flex: none;
    overflow: visible;
  }
  .search-panel > label {
    position: absolute;
    width: 1px;
    height: 1px;
    margin: 0;
    overflow: hidden;
    clip-path: inset(50%);
  }
  /* Stays above the results while they scroll. */
  .search-row {
    position: sticky;
    top: var(--header-height);
    z-index: 5;
    margin-inline: -16px;
    padding: var(--space-8) 16px;
    background: var(--ground);
  }
  .filter-toggle {
    display: inline-flex;
    flex: none;
    min-height: var(--field);
    padding: 0 var(--space-12);
  }
  .search-filters {
    display: none;
    padding-bottom: var(--space-8);
  }
  .search-filters.open {
    display: block;
  }
  .pane-detail .search-panel,
  .pane-list:not(.browsing) .workspace {
    display: none;
  }
  .pane-list .workspace {
    padding: 16px;
  }
  .workspace {
    padding: 0 0 16px;
  }
}
</style>
