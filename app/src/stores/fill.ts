import { computed, ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import { cards } from "@/data";
import { toastError } from "@/components/toast";
import { t } from "@/i18n";
import {
  blankCondition,
  query,
  withCard,
  type CardFields,
  type Condition,
  type DiscoveryResult,
  type Option,
  type Scope,
} from "@/domain/discovery";
import { discoveryPack, scatteredIds, textIds, type SearchItem } from "./search";

const noCard: CardFields = { effects: [], facts: [], attrs: {} };

/** The query on the Fill page: it narrows the tray's suggestions, or lists every match. */
export const useFillStore = defineStore("fill", () => {
  const conditions = ref<Condition[]>([blankCondition()]);
  const scope = ref<Scope>("action");
  const fromTray = ref(true);
  const q = ref("");
  const kind = ref("");
  /** The relationship the tray's suggestions are narrowed to. */
  const mechanism = ref("");
  const items = shallowRef<SearchItem[]>([]);
  const total = ref(0);
  const kinds = shallowRef<Option[]>([]);
  /** A mechanic or search text is set, so the whole-catalog list has something to show. */
  const listing = ref(false);
  const matched = shallowRef<Set<string>>(new Set());
  const facets = shallowRef<DiscoveryResult["facets"]>({
    kinds: [],
    conditions: [],
    attributes: [],
  });
  const active = computed(() => conditions.value.some((c) => c.category));
  let version = 0;

  async function run() {
    const current = ++version;
    try {
      const [index, phrased] = await Promise.all([discoveryPack(), textIds(q.value)]);
      const filters = { conditions: conditions.value, scope: scope.value };
      const search = (ids: Set<string> | undefined, limit: number, within = "") =>
        query(index, { ...filters, q: q.value, ids, kind: within, limit });
      const mechanics = query(index, { ...filters, limit: 0 });
      const wanted = active.value || !!phrased;
      let ids = phrased;
      let every = ids ? search(ids, 0) : mechanics;
      // The chosen filters can exclude every component holding the phrase.
      if (ids && !every.total) {
        ids = await scatteredIds(q.value);
        every = search(ids, 0);
      }
      const available = every.facets.kinds;
      const within = available.some((k) => k.value === kind.value)
        ? kind.value
        : (available[0]?.value ?? "");
      const list = wanted ? search(ids, Infinity, within).items : [];
      const shards = new Map(
        await Promise.all(
          [...new Set(list.map((i) => i.kind))].map(async (k) => [k, await cards(k)] as const),
        ),
      );
      if (current !== version) return;
      kind.value = within;
      kinds.value = available;
      listing.value = wanted;
      items.value = list.map((item) => withCard(item, shards.get(item.kind)?.[item.id] ?? noCard));
      total.value = every.total;
      matched.value = mechanics.matched;
      facets.value = mechanics.facets;
    } catch (error) {
      if (current !== version) return;
      console.error(error);
      toastError(t("search.loadFailed"));
    }
  }

  function removeCondition(index: number) {
    conditions.value.splice(index, 1);
    if (!conditions.value.length) conditions.value.push(blankCondition());
    run();
  }

  /** Rows left without a category go away once the filters are closed. */
  function dropBlank() {
    const chosen = conditions.value.filter((c) => c.category);
    const next = chosen.length ? chosen : [blankCondition()];
    if (next.length === conditions.value.length) return;
    conditions.value = next;
    run();
  }

  return {
    conditions,
    scope,
    fromTray,
    q,
    kind,
    mechanism,
    items,
    total,
    kinds,
    listing,
    matched,
    facets,
    active,
    run,
    removeCondition,
    dropBlank,
  };
});
