<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, watch } from "vue";
import { storeToRefs } from "pinia";
import { synergies } from "@/data";
import { whereIs } from "@/domain/placement";
import { useFillStore } from "@/stores/fill";
import { useTeamStore } from "@/stores/team";
import { t } from "@/i18n";
import AddButton from "@/components/AddButton.vue";
import IdentityLine from "@/components/IdentityLine.vue";
import MechanicFilters from "@/components/MechanicFilters.vue";
import ObjectCell from "@/components/ObjectCell.vue";
import ObjectSummary from "@/components/ObjectSummary.vue";
import SynergyCard from "@/components/SynergyCard.vue";
import { shownAs } from "@/components/assembly";
import { loadComponent } from "@/components/components";
import { suggestions, type Seed } from "@/components/fill";
import { useCatalog } from "@/components/selection";
import { kindNames, objectRoute, type Hit } from "@/components/presentation";
import { candidates, cards, categories, matching } from "@/components/synergy";
import { intentOf, useEntity } from "@/components/tray";

const PAGE = 24;

const store = useTeamStore();
const { team, index } = storeToRefs(store);
const catalog = useCatalog();
const entity = useEntity();
const query = useFillStore();
const { active, matched: mechanicMatches, items: mechanicItems, total } = storeToRefs(query);
onMounted(() => query.run());

const phase = ref<"loading" | "ready" | "failed">("loading");
const seeds = shallowRef<Seed[]>([]);
const kind = ref<string | null>(null);
const mechanism = ref<string | null>(null);
const keyword = ref("");
const shown = ref(PAGE);

/** Tray items that stand for the same Synergies file, such as a creature and its trait, count once. */
const trayIds = computed(() => [...new Set(team.value.inventory.map((item) => item.id))]);

let request = 0;
watch(
  [trayIds, index],
  async ([ids]) => {
    const current = ++request;
    phase.value = "loading";
    try {
      const loaded = await Promise.all(
        ids.map(async (id) => {
          const item = team.value.inventory.find((i) => i.id === id)!;
          const [page, own, found] = await Promise.all([
            loadComponent(shownAs(index.value, item)),
            loadComponent(id),
            synergies(id),
          ]);
          return { id, name: page.name, file: own.synergies, items: found?.items ?? [] };
        }),
      );
      if (current !== request) return;
      const files = new Set<string>();
      seeds.value = loaded.filter((seed) => {
        if (!seed.file || files.has(seed.file)) return false;
        files.add(seed.file);
        return true;
      });
      phase.value = "ready";
    } catch {
      if (current === request) phase.value = "failed";
    }
  },
  { immediate: true },
);

const ranked = computed(
  () =>
    new Map(
      suggestions(seeds.value, (id) => {
        const intent = intentOf({ id, kind: id.split(":")[0] }, catalog.value, team.value);
        const where = whereIs(team.value, intent.id, entity);
        return !!intent.ownBase || where.tray.length + where.placed.length > 0;
      }).map((s) => [s.id, s]),
    ),
);
const items = computed(() =>
  candidates(
    seeds.value
      .flatMap((seed) => seed.items)
      .filter((i) => ranked.value.has(i.id) && (!active.value || mechanicMatches.value.has(i.id))),
  ),
);
const matched = computed(() => matching(items.value, keyword.value));
const grouping = computed(() => categories(matched.value, kind.value, mechanism.value));
const visible = computed(() =>
  cards(matched.value, grouping.value.kind, grouping.value.mechanism).sort(
    (a, b) => ranked.value.get(b.id)!.score - ranked.value.get(a.id)!.score,
  ),
);
const count = computed(() => {
  const found = t("search.results", total.value);
  return total.value > mechanicItems.value.length
    ? t("search.showing", { found, shown: mechanicItems.value.length })
    : found;
});
const owners = (id: string) => ranked.value.get(id)!.links.map((link) => link.seed.name);

function change(field: "kind" | "mechanism", value: string) {
  kind.value = field === "kind" ? value : grouping.value.kind;
  mechanism.value = field === "mechanism" ? value : "";
  shown.value = PAGE;
}
function filter(value: string) {
  kind.value = grouping.value.kind;
  mechanism.value = grouping.value.mechanism;
  keyword.value = value;
  shown.value = PAGE;
}
</script>

<template>
  <section class="fill" :aria-label="t('app.fill')">
    <aside class="fill-query">
      <MechanicFilters fill />
    </aside>
    <div class="fill-results">
      <template v-if="!trayIds.length">
        <p v-if="!active" class="muted">{{ t("fill.emptyTray") }}</p>
        <template v-else>
          <p class="muted">{{ count }}</p>
          <div class="pairing-cards">
            <ObjectCell
              v-for="item in mechanicItems"
              :key="item.id"
              tag="article"
              layout="card"
              class="match"
              :data="item"
            >
              <template #label>
                <div class="match-head">
                  <IdentityLine :data="item" :identity="false">
                    <RouterLink
                      class="match-name"
                      :to="objectRoute(item.id, item.matched_rules as Hit[])"
                      >{{ item.name }}</RouterLink
                    >
                  </IdentityLine>
                  <AddButton quick :item="item" />
                </div>
              </template>
              <template #detail>
                <small>{{
                  item.matched_names.join(" · ") || kindNames[item.kind] || item.kind
                }}</small>
                <ObjectSummary :data="item" :limit="2" />
              </template>
            </ObjectCell>
            <p v-if="!mechanicItems.length" class="muted">{{ t("search.noMatches") }}</p>
          </div>
        </template>
      </template>
      <p v-else-if="phase === 'failed'" class="muted">{{ t("fill.failed") }}</p>
      <p v-else-if="phase === 'loading' && !items.length" class="muted">{{ t("fill.loading") }}</p>
      <p v-else-if="!items.length" class="muted">
        {{ active ? t("search.noMatches") : t("fill.none") }}
      </p>
      <template v-else>
        <div class="pairing-controls">
          <div class="pairing-filter">
            <input
              type="search"
              :aria-label="t('synergy.filter')"
              :placeholder="t('synergy.placeholder')"
              autocomplete="off"
              :value="keyword"
              @input="filter(($event.target as HTMLInputElement).value)"
            />
            <button
              v-if="keyword"
              type="button"
              class="icon-button"
              :aria-label="t('synergy.clearFilter')"
              @click="filter('')"
            >
              <i class="icon icon-close"></i>
            </button>
          </div>
          <div class="pairing-kinds" role="group" :aria-label="t('synergy.types')">
            <button
              v-for="g in grouping.kinds"
              :key="g.value"
              type="button"
              :aria-pressed="grouping.kind === g.value"
              @click="change('kind', g.value)"
            >
              {{ g.label }} <span class="count">{{ g.count }}</span>
            </button>
          </div>
          <div class="pairing-mechanisms" role="group" :aria-label="t('synergy.relationships')">
            <button
              v-for="g in grouping.mechanisms"
              :key="g.value"
              type="button"
              :aria-pressed="grouping.mechanism === g.value"
              @click="change('mechanism', g.value)"
            >
              {{ g.label }} <span class="count">{{ g.count }}</span>
            </button>
          </div>
        </div>
        <div class="pairing-cards" role="region" :aria-label="t('synergy.results')">
          <SynergyCard
            v-for="card in visible.slice(0, shown)"
            :key="card.id"
            :card="card"
            :owner="ranked.get(card.id)!.links[0]!.seed.id"
            :owners="owners(card.id)"
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
    </div>
  </section>
</template>

<style scoped>
.fill {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-items: start;
  gap: var(--space-12);
  padding: var(--gutter);
}
.fill-query :deep(.mechanism-filters) {
  margin: 0;
}
.fill-results {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-content: start;
  gap: var(--space-12);
}
.match {
  background: var(--raised);
}
.match :deep(.cell-detail > small) {
  display: block;
  margin-top: 6px;
  color: var(--muted);
  font-size: var(--fs-12);
}
.match-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}
.match-name {
  font-weight: 700;
}
@media (min-width: 1024px) {
  .fill {
    grid-template-columns: 280px minmax(0, 1fr);
  }
  .fill-query {
    position: sticky;
    top: calc(var(--header-height) + var(--gutter));
  }
}
.muted {
  margin: 0;
  color: var(--muted);
}
.pairing-filter {
  display: flex;
  gap: 4px;
  max-width: 420px;
}
.pairing-filter input {
  flex: 1;
  min-width: 0;
}
.pairing-filter input::-webkit-search-cancel-button {
  display: none;
}
.pairing-filter .icon-button {
  width: var(--field);
  height: var(--field);
}
.pairing-kinds,
.pairing-mechanisms {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 6px;
  min-height: var(--field);
  padding-right: 32px;
  overflow-x: auto;
  scrollbar-width: none;
  -webkit-mask-image: linear-gradient(to right, #000 calc(100% - 32px), transparent);
  mask-image: linear-gradient(to right, #000 calc(100% - 32px), transparent);
}
.pairing-kinds::-webkit-scrollbar,
.pairing-mechanisms::-webkit-scrollbar {
  display: none;
}
.pairing-kinds {
  gap: 0;
  margin-top: 12px;
  border-bottom: 1px solid var(--line);
}
.pairing-mechanisms {
  min-height: var(--control-compact);
  margin-top: 10px;
}
.pairing-kinds button,
.pairing-mechanisms button {
  flex-shrink: 0;
  color: var(--muted);
  white-space: nowrap;
}
.pairing-kinds button {
  min-height: var(--field);
  padding: 0 14px;
  background-color: transparent;
  border: 0;
  clip-path: none;
  font-size: var(--fs-15);
}
.pairing-mechanisms button {
  min-height: var(--control-compact);
  padding: 0 10px;
  background-color: transparent;
  font-size: var(--fs-13);
}
.pairing-kinds button:hover,
.pairing-mechanisms button:hover {
  color: var(--text);
}
.pairing-kinds [aria-pressed="true"] {
  box-shadow: inset 0 -2px 0 var(--accent);
  color: var(--text);
  font-weight: 700;
}
.pairing-mechanisms [aria-pressed="true"] {
  background-color: var(--raised);
  border-color: var(--accent);
  color: var(--text);
}
.count {
  color: var(--muted);
  font-family: var(--pixel-font);
  font-size: 16px;
  font-variant-numeric: tabular-nums;
}
[aria-pressed="true"] > .count {
  color: var(--text);
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
  .pairing-kinds button,
  .pairing-mechanisms button {
    min-height: var(--field);
  }
}
</style>
