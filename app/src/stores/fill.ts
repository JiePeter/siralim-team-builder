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
  type Scope,
} from "@/domain/discovery";
import { discoveryPack, type SearchItem } from "./search";

const noCard: CardFields = { effects: [], facts: [], attrs: {} };

/** The mechanic query on the Fill page: it narrows the tray's suggestions, or lists every match. */
export const useFillStore = defineStore("fill", () => {
  const conditions = ref<Condition[]>([blankCondition()]);
  const scope = ref<Scope>("action");
  const fromTray = ref(true);
  const items = shallowRef<SearchItem[]>([]);
  const total = ref(0);
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
      const result = query(await discoveryPack(), {
        conditions: conditions.value,
        scope: scope.value,
        limit: active.value ? Infinity : 0,
      });
      const shards = new Map(
        await Promise.all(
          [...new Set(result.items.map((i) => i.kind))].map(
            async (k) => [k, await cards(k)] as const,
          ),
        ),
      );
      if (current !== version) return;
      items.value = result.items.map((item) =>
        withCard(item, shards.get(item.kind)?.[item.id] ?? noCard),
      );
      total.value = result.total;
      matched.value = result.matched;
      facets.value = result.facets;
    } catch (error) {
      if (current !== version) return;
      console.error(error);
      toastError(t("search.loadFailed"));
    }
  }

  return { conditions, scope, fromTray, items, total, matched, facets, active, run };
});
