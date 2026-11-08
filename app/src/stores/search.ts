import { ref, shallowRef, type InjectionKey } from "vue";
import { defineStore } from "pinia";
import MiniSearch, { type SearchResult } from "minisearch";
import { cards, discovery, type SearchDocument } from "@/data";
import { memoRequest } from "@/data/memo";
import type { Attributes } from "@/domain/attributes";
import { toastError } from "@/components/toast";
import { t } from "@/i18n";
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
import { fold, hanRuns, words } from "@/domain/values";

export type SearchItem = ReturnType<typeof withCard<DiscoveryItem>>;

export const discoveryPack = memoRequest(() => discovery().then(discoveryIndex));

const TEXT_FIELDS = ["name", "members", "text", "locations"];

/** Names, members, effect text and locations, matched per word by prefix like the discovery words. */
const textIndex = memoRequest(() =>
  discoveryPack().then(({ pack }) => {
    const index = new MiniSearch<SearchDocument>({
      fields: TEXT_FIELDS,
      storeFields: TEXT_FIELDS,
      tokenize: words,
      processTerm: fold,
      searchOptions: { prefix: true, combineWith: "AND" },
    });
    index.addAll(searchDocuments(pack));
    return index;
  }),
);

const idsOf = (hits: SearchResult[]) => new Set(hits.map((hit) => String(hit.id)));

/** Ids of the components with every word of `q` anywhere in their text. */
export async function scatteredIds(q: string): Promise<Set<string>> {
  return idsOf((await textIndex()).search(q));
}

/**
 * Ids of the components whose text matches `q`; undefined when `q` has no words to match.
 * Those holding every Han run of `q` unbroken within a field, when there are any; else all matches.
 */
export async function textIds(q: string): Promise<Set<string> | undefined> {
  if (!words(fold(q)).length) return undefined;
  const hits = (await textIndex()).search(q);
  const runs = hanRuns(q);
  const phrased = hits.filter((hit) =>
    runs.every((run) => TEXT_FIELDS.some((field) => String(hit[field]).includes(run))),
  );
  return idsOf(phrased.length ? phrased : hits);
}

const noCard: CardFields = { effects: [], facts: [], attrs: {} };

function searchState() {
  const q = ref("");
  const kind = ref("");
  const attributes = ref<Attributes>({});
  const conditions = ref<Condition[]>([blankCondition()]);
  const scope = ref<Scope>("action");
  const items = shallowRef<SearchItem[]>([]);
  const total = ref(0);
  const facets = shallowRef<DiscoveryResult["facets"]>({
    kinds: [],
    conditions: [],
    attributes: [],
  });
  const ready = ref(false);
  /** Search text, a type or a mechanic filter produced the shown results. */
  const narrowed = ref(false);
  /** The search field takes focus the next time the search page opens. */
  const wantsFocus = ref(false);
  let version = 0;

  async function run() {
    const current = ++version;
    try {
      const [index, ids] = await Promise.all([discoveryPack(), textIds(q.value)]);
      const search = (matching?: Set<string>) =>
        query(index, {
          q: q.value,
          kind: kind.value,
          attributes: attributes.value,
          conditions: conditions.value,
          scope: scope.value,
          ids: matching,
        });
      let result = search(ids);
      // The chosen filters can exclude every component holding the phrase.
      if (ids && !result.total) result = search(await scatteredIds(q.value));
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
      toastError(t("search.loadFailed"));
    }
  }

  /** Start a fresh search for one component kind, as a picker's Open in Search does. */
  function browse(next: string, text = "", narrowing: Attributes = {}) {
    q.value = text;
    kind.value = next;
    attributes.value = { ...narrowing };
    conditions.value = [blankCondition()];
    scope.value = "action";
    wantsFocus.value = true;
    return run();
  }

  return {
    q,
    kind,
    attributes,
    conditions,
    scope,
    items,
    total,
    facets,
    ready,
    narrowed,
    wantsFocus,
    run,
    browse,
  };
}

export const useSearchStore = defineStore("search", searchState);
/** The picker's own search, so replacing a field leaves the Search page's as it was. */
export const usePickerSearchStore = defineStore("picker-search", searchState);

/** The search a MechanicFilters inside this tree narrows. */
export const MECHANIC_SEARCH: InjectionKey<typeof useSearchStore> = Symbol("mechanic search");
