<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { refDebounced, useDebounceFn } from "@vueuse/core";
import {
  TabsContent,
  TabsList,
  TabsRoot,
  TabsTrigger,
  ToggleGroupItem,
  ToggleGroupRoot,
} from "reka-ui";
import { useFillStore } from "@/stores/fill";
import { t } from "@/i18n";
import AddButton from "@/components/AddButton.vue";
import MechanicFilters from "@/components/MechanicFilters.vue";
import ModalDialog from "@/components/ModalDialog.vue";
import ResultCard from "@/components/ResultCard.vue";
import SynergyCard from "@/components/SynergyCard.vue";
import { conditionSummaries } from "@/components/filters";
import { kindGroups, kindNames } from "@/components/presentation";
import {
  candidates,
  cards,
  categories,
  matching,
  mechanismMatches,
  pairingMechanisms,
} from "@/components/synergy";
import { useTraySuggestions } from "@/components/traySuggestions";

const PAGE = 24;

const query = useFillStore();
const {
  active,
  conditions,
  scope,
  facets,
  fromTray,
  q: keyword,
  kind: listedKind,
  kinds: listedKinds,
  suggestedKind,
  listing,
  mechanism,
  matched: mechanicMatches,
  items: mechanicItems,
  total,
} = storeToRefs(query);
onMounted(() => query.run());
const rerun = useDebounceFn(() => query.run(), 180);
const settledKeyword = refDebounced(keyword, 180);

const { trayIds, phase, seeds, ranked } = useTraySuggestions();
const shown = ref(PAGE);
const editing = ref(false);

const suggesting = computed({
  get: () => fromTray.value && trayIds.value.length > 0,
  set: (value) => {
    fromTray.value = value;
  },
});
const source = computed({
  get: () => (suggesting.value ? "tray" : "all"),
  set: (value) => {
    if (value) suggesting.value = value === "tray";
  },
});
watch([suggesting, mechanicItems], () => {
  shown.value = PAGE;
});
watch(editing, (open) => {
  if (!open) query.dropBlank();
});

const items = computed(() =>
  candidates(
    seeds.value
      .flatMap((seed) => seed.items)
      .filter((i) => ranked.value.has(i.id) && (!active.value || mechanicMatches.value.has(i.id))),
  ),
);
const matched = computed(() => matching(items.value, settledKeyword.value));
const grouping = computed(() => categories(matched.value, suggestedKind.value, mechanism.value));
const visible = computed(() =>
  cards(matched.value, grouping.value.kind, grouping.value.mechanism).sort(
    (a, b) => ranked.value.get(a.id)!.position - ranked.value.get(b.id)!.position,
  ),
);
const suggestionCount = computed(
  () =>
    matched.value.filter((item) =>
      item.paths.some((path) => mechanismMatches(path, grouping.value.mechanism)),
    ).length,
);
const found = computed(() => t("search.results", total.value));

const chosen = computed(() => conditionSummaries(conditions.value, facets.value.conditions));
const relation = computed(() =>
  suggesting.value && grouping.value.mechanism
    ? pairingMechanisms[grouping.value.mechanism]
    : undefined,
);
const filterCount = computed(() => chosen.value.length + (relation.value ? 1 : 0));

const tabs = computed(() => {
  if (suggesting.value) return phase.value === "failed" ? [] : grouping.value.kinds;
  if (!listing.value) return [];
  return listedKinds.value.map((k) => {
    const group = kindGroups.find((candidate) => candidate.kinds.includes(k.value));
    return {
      value: k.value,
      label: (group?.kinds.length === 1 ? group.label : kindNames[k.value]) || k.label,
      count: k.count,
    };
  });
});
const tab = computed(() => (suggesting.value ? (grouping.value.kind ?? "") : listedKind.value));

function chooseTab(value: string | number) {
  if (suggesting.value) return change("kind", String(value));
  listedKind.value = String(value);
  query.run();
}
function change(field: "kind" | "mechanism", value: string) {
  suggestedKind.value = field === "kind" ? value : grouping.value.kind;
  mechanism.value = field === "mechanism" ? value : "";
  shown.value = PAGE;
}
function filter(value: string) {
  keyword.value = value;
  shown.value = PAGE;
  rerun();
}
</script>

<template>
  <TabsRoot
    as="section"
    class="fill"
    :aria-label="t('app.fill')"
    :model-value="tab"
    @update:model-value="chooseTab"
  >
    <div class="fill-controls">
      <ToggleGroupRoot
        v-model="source"
        type="single"
        class="fill-source"
        :aria-label="t('fill.source')"
      >
        <ToggleGroupItem value="tray" :disabled="!trayIds.length">
          {{ t("fill.fromTray") }}
          <span v-if="trayIds.length && phase === 'ready'" class="tally">{{
            suggestionCount
          }}</span>
        </ToggleGroupItem>
        <ToggleGroupItem value="all">
          {{ t("search.all") }} <span v-if="listing" class="tally">{{ total }}</span>
        </ToggleGroupItem>
      </ToggleGroupRoot>
      <div class="fill-search">
        <div class="fill-input">
          <i class="icon icon-search"></i>
          <input
            type="search"
            :aria-label="t('synergy.placeholder')"
            :placeholder="t('synergy.placeholder')"
            autocomplete="off"
            :value="keyword"
            @input="filter(($event.target as HTMLInputElement).value)"
          />
          <button
            v-if="keyword"
            type="button"
            class="clear"
            :aria-label="t('synergy.clearFilter')"
            @click="filter('')"
          >
            <i class="icon icon-close"></i>
          </button>
        </div>
        <button
          type="button"
          class="fill-filter"
          :class="{ active: filterCount }"
          aria-haspopup="dialog"
          :aria-label="
            filterCount ? t('search.filtersCount', { count: filterCount }) : t('search.filters')
          "
          @click="editing = true"
        >
          <i class="icon icon-filter"></i>{{ t("search.filters") }}
          <span v-if="filterCount" class="tally">{{ filterCount }}</span>
        </button>
      </div>
      <div
        v-if="filterCount"
        class="fill-chosen"
        role="group"
        :aria-label="t('search.mechanic.filters')"
      >
        <span v-for="c in chosen" :key="c.index" class="fill-chip">
          <button type="button" @click="editing = true">{{ c.label }}</button>
          <button
            type="button"
            :aria-label="t('fill.removeFilter', { name: c.label })"
            @click="query.removeCondition(c.index)"
          >
            <i class="icon icon-close"></i>
          </button>
        </span>
        <span v-if="relation" class="fill-chip">
          <button type="button" @click="editing = true">{{ relation }}</button>
          <button
            type="button"
            :aria-label="t('fill.removeFilter', { name: relation })"
            @click="change('mechanism', '')"
          >
            <i class="icon icon-close"></i>
          </button>
        </span>
      </div>
      <TabsList v-if="tabs.length" class="fill-tabs" :aria-label="t('search.type')">
        <TabsTrigger v-for="g in tabs" :key="g.value" :value="g.value">
          {{ g.label }} <span class="tally">{{ g.count }}</span>
        </TabsTrigger>
      </TabsList>
    </div>
    <ModalDialog v-model:open="editing" :title="t('search.mechanic.filters')" sheet>
      <div class="fill-sheet">
        <MechanicFilters
          v-model:conditions="conditions"
          v-model:scope="scope"
          :rows="facets.conditions"
          fill
          :clearable="!!mechanism"
          @change="query.run()"
          @clear="mechanism = ''"
        />
        <div
          v-if="suggesting && grouping.mechanisms.length > 1"
          class="fill-relations"
          role="group"
          aria-labelledby="fill-relations-title"
        >
          <h3 id="fill-relations-title">{{ t("synergy.relationships") }}</h3>
          <div>
            <button
              v-for="g in grouping.mechanisms"
              :key="g.value"
              type="button"
              :aria-pressed="grouping.mechanism === g.value"
              @click="change('mechanism', g.value)"
            >
              {{ g.label }} <span class="tally">{{ g.count }}</span>
            </button>
          </div>
        </div>
        <div class="fill-sheet-foot">
          <button type="button" class="primary" @click="editing = false">
            {{ t("fill.view", { n: suggesting ? suggestionCount : total }) }}
          </button>
        </div>
      </div>
    </ModalDialog>
    <component
      :is="tabs.length ? TabsContent : 'div'"
      v-bind="tabs.length ? { value: tab } : {}"
      class="fill-results"
    >
      <template v-if="!suggesting">
        <p v-if="!listing" class="muted">
          {{ trayIds.length ? t("fill.chooseCondition") : t("fill.emptyTray") }}
        </p>
        <template v-else>
          <div class="pairing-cards">
            <ResultCard
              v-for="item in mechanicItems.slice(0, shown)"
              :key="item.id"
              class="match"
              link
              :item="item"
              :line="item.matched_names.join(' · ') || kindNames[item.kind] || item.kind"
            >
              <AddButton quick :item="item" />
            </ResultCard>
            <p v-if="!mechanicItems.length" class="muted">{{ t("search.noMatches") }}</p>
          </div>
          <button
            v-if="mechanicItems.length > shown"
            type="button"
            class="show-more"
            @click="shown += PAGE"
          >
            {{ t("fill.showMore") }}
          </button>
        </template>
      </template>
      <p v-else-if="phase === 'failed'" class="muted">{{ t("fill.failed") }}</p>
      <p v-else-if="phase === 'loading' && !items.length" class="muted">{{ t("fill.loading") }}</p>
      <template v-else-if="!matched.length">
        <p class="muted">{{ listing ? t("fill.noSuggestionMatch") : t("fill.none") }}</p>
        <button v-if="listing && total" type="button" class="show-more" @click="suggesting = false">
          {{ t("fill.showAll", { found }) }}
        </button>
      </template>
      <template v-else>
        <div class="pairing-cards" role="region" :aria-label="t('synergy.results')">
          <SynergyCard
            v-for="card in visible.slice(0, shown)"
            :key="card.id"
            :card="card"
            :owner="ranked.get(card.id)!.links[0]!.seed.id"
            :owners="ranked.get(card.id)!.owners"
          />
          <p v-if="!visible.length" class="muted">{{ t("synergy.empty") }}</p>
        </div>
        <button
          v-if="visible.length > shown"
          type="button"
          class="show-more"
          @click="shown += PAGE"
        >
          {{ t("fill.showMore") }}
        </button>
      </template>
    </component>
  </TabsRoot>
</template>

<style scoped>
.fill {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-items: start;
  gap: var(--space-12);
  padding: var(--gutter);
}
.fill-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--space-8);
}
.tally {
  font: 400 16px / 1 var(--pixel-font);
  font-variant-numeric: tabular-nums;
}
.fill-source {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(0, 1fr);
  gap: 1px;
}
.fill-source > button {
  gap: var(--space-8);
  min-width: 0;
  min-height: var(--field);
  padding: 0 var(--space-8);
  background: var(--raised);
  border: 0;
  clip-path: none;
  color: var(--muted);
  font-size: var(--fs-15);
  font-weight: 400;
  white-space: nowrap;
}
.fill-source > button:hover:not(:disabled) {
  background: var(--raised-hover);
  color: var(--text);
}
.fill-source > [data-state="on"],
.fill-source > [data-state="on"]:hover:not(:disabled) {
  --focus-ink: var(--on-accent);
  background: var(--accent);
  color: var(--on-accent);
  font-weight: 700;
}
.fill-search {
  display: flex;
  gap: var(--space-8);
}
.fill-input {
  position: relative;
  display: flex;
  flex: 1;
  align-items: center;
  min-width: 0;
}
.fill-input > .icon {
  position: absolute;
  z-index: 1;
  left: var(--space-12);
  color: var(--muted);
  pointer-events: none;
}
.fill-input > input {
  flex: 1;
  min-width: 0;
  padding-right: var(--field);
  padding-left: var(--field);
}
.fill-input > input::-webkit-search-cancel-button {
  display: none;
}
.fill-input > .clear {
  position: absolute;
  right: var(--space-4);
  margin: 0;
}
.fill-filter {
  flex: none;
  gap: var(--space-8);
  min-height: var(--field);
  padding: 0 var(--space-12);
}
.fill-chosen {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  scrollbar-width: none;
}
.fill-chosen::-webkit-scrollbar {
  display: none;
}
.fill-chip {
  display: flex;
  flex: none;
}
.fill-chip > button {
  min-height: var(--control);
  font-size: var(--fs-13);
  white-space: nowrap;
}
.fill-chip > button:first-child {
  padding: 0 var(--space-8) 0 var(--space-12);
}
.fill-chip > button + button {
  width: var(--control);
  min-width: var(--control);
  margin-left: -1px;
  padding: 0;
  color: var(--muted);
}
.fill-tabs {
  display: flex;
  overflow-x: auto;
  border-bottom: 1px solid var(--line);
  scrollbar-width: none;
}
.fill-tabs::-webkit-scrollbar {
  display: none;
}
.fill-tabs > button {
  flex: none;
  gap: 6px;
  min-height: var(--field);
  margin-bottom: -1px;
  padding: 0 var(--space-12);
  background: none;
  border: 0;
  border-bottom: 2px solid transparent;
  clip-path: none;
  color: var(--muted);
  font-size: var(--fs-15);
  font-weight: 400;
  white-space: nowrap;
}
.fill-tabs > button:hover {
  background: none;
  color: var(--text);
}
.fill-tabs > [aria-selected="true"] {
  border-bottom-color: var(--accent);
  color: var(--text);
  font-weight: 700;
}
.fill-tabs .tally,
.fill-relations .tally {
  font-size: 11px;
}
.fill-sheet {
  padding: var(--space-4) 16px 0;
}
.fill-relations {
  margin-top: var(--space-12);
}
.fill-relations h3 {
  margin: 0 0 var(--space-8);
  color: var(--muted);
  font-size: var(--fs-13);
  font-weight: 400;
}
.fill-relations > div {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.fill-relations button {
  gap: 6px;
  min-height: var(--control-compact);
  padding: 0 10px;
  font-size: var(--fs-13);
}
.fill-sheet-foot {
  position: sticky;
  bottom: 0;
  padding: var(--space-12) 0 calc(var(--space-12) + env(safe-area-inset-bottom));
  background: var(--cell);
}
.fill-sheet-foot > .primary {
  width: 100%;
  min-height: var(--row);
}
.fill-results {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-content: start;
  gap: var(--space-12);
}
.pairing-cards > .match {
  background: var(--raised);
}
.muted {
  margin: 0;
  color: var(--muted);
}
.pairing-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr));
  align-items: start;
  gap: 8px;
}
.show-more {
  justify-self: start;
}
@media (max-width: 767px) {
  .fill-search {
    position: sticky;
    top: var(--header-height);
    z-index: 5;
    margin: calc(-1 * var(--space-8)) calc(-1 * var(--gutter));
    padding: var(--space-8) var(--gutter);
    background: var(--ground);
  }
}
@media (min-width: 768px) {
  .fill-controls {
    grid-template-columns: minmax(0, 320px) minmax(0, 1fr);
    column-gap: var(--space-12);
  }
  .fill-chosen,
  .fill-tabs {
    grid-column: 1 / -1;
  }
  .fill-chosen {
    flex-wrap: wrap;
    overflow-x: visible;
  }
}
</style>
