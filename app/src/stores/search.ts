import { ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import MiniSearch from "minisearch";
import { cards, discovery, type SearchDocument } from "@/data";
import { memoRequest } from "@/data/memo";
import type { Attributes } from "@/domain/attributes";
import { toastError } from "@/components/toast";
import {
  blankCondition,
  discoveryIndex,
  query,
  searchDocuments,
  withCard,
  type CardFields,
  type Condition,
  type DiscoveryItem,
  type DiscoveryResult,
  type Scope,
} from "@/domain/discovery";
import { fold, words } from "@/domain/values";

export type SearchItem = ReturnType<typeof withCard<DiscoveryItem>>;

export const discoveryPack = memoRequest(() => discovery().then(discoveryIndex));

/** Names, members, effect text and locations, matched per word by prefix like the discovery words. */
const textIndex = memoRequest(() =>
  discoveryPack().then(({ pack }) => {
    const index = new MiniSearch<SearchDocument>({
      fields: ["name", "members", "text", "locations"],
      tokenize: words,
      processTerm: fold,
      searchOptions: { prefix: true, combineWith: "AND" },
    });
    index.addAll(searchDocuments(pack));
    return index;
  }),
);

/** Ids of the components whose text matches `q`; undefined when `q` has no words to match. */
export async function textIds(q: string): Promise<Set<string> | undefined> {
  if (!words(fold(q)).length) return undefined;
  return new Set((await textIndex()).search(q).map((hit) => String(hit.id)));
}

const noCard: CardFields = { effects: [], facts: [], attrs: {} };

export const useSearchStore = defineStore("search", () => {
  const q = ref("");
  const kind = ref("");
  const attributes = ref<Attributes>({});
  const conditions = ref<Condition[]>([blankCondition()]);
  const scope = ref<Scope>("action");
  /** The phone layout folds empty mechanic filters behind "+ Filter" until opened. */
  const filtersOpened = ref(false);
  const items = shallowRef<SearchItem[]>([]);
  const total = ref(0);
  const facets = shallowRef<DiscoveryResult["facets"]>({
    kinds: [],
    conditions: [],
    attributes: [],
  });
  const ready = ref(false);
  /** The shown results came from search text, a type or a mechanic filter, not the bare catalog. */
  const narrowed = ref(false);
  /** The search field takes focus the next time the search page opens. */
  const wantsFocus = ref(false);
  let version = 0;

  async function run() {
    const current = ++version;
    try {
      const [index, ids] = await Promise.all([discoveryPack(), textIds(q.value)]);
      const result = query(index, {
        q: q.value,
        kind: kind.value,
        attributes: attributes.value,
        conditions: conditions.value,
        scope: scope.value,
        ids,
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
      facets.value = result.facets;
      narrowed.value = !!ids || !!kind.value || conditions.value.some((c) => c.category);
      ready.value = true;
    } catch (error) {
      if (current !== version) return;
      console.error(error);
      toastError("Search data could not be loaded. Reload the page to try again.");
    }
  }

  /** Start a fresh search for one component kind, as a picker's Open in Search does. */
  function browse(next: string, text = "", narrowing: Attributes = {}) {
    q.value = text;
    kind.value = next;
    attributes.value = { ...narrowing };
    conditions.value = [blankCondition()];
    scope.value = "action";
    filtersOpened.value = false;
    wantsFocus.value = true;
    return run();
  }

  return {
    q,
    kind,
    attributes,
    conditions,
    scope,
    filtersOpened,
    items,
    total,
    facets,
    ready,
    narrowed,
    wantsFocus,
    run,
    browse,
  };
});
