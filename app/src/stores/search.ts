import { ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import MiniSearch, { type SearchResult } from "minisearch";
import { cards, discovery, type SearchDocument } from "@/data";
import { memoRequest } from "@/data/memo";
import type { Attributes } from "@/domain/attributes";
import { toastError } from "@/components/toast";
import { t } from "@/i18n";
import {
  discoveryIndex,
  query,
  searchDocuments,
  withCard,
  type CardFields,
  type DiscoveryItem,
  type DiscoveryResult,
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

/**
 * What `attempt` finds with the ids holding the phrase, or with the scattered matches of `q` when
 * `hasHits` rejects that; `phrased` is `textIds(q)`.
 */
export async function fallBackToScattered<T>(
  q: string,
  phrased: Set<string> | undefined,
  attempt: (ids: Set<string> | undefined) => T,
  hasHits: (found: T) => boolean,
): Promise<{ ids: Set<string> | undefined; found: T }> {
  const found = attempt(phrased);
  if (!phrased || hasHits(found)) return { ids: phrased, found };
  const ids = await scatteredIds(q);
  return { ids, found: attempt(ids) };
}

const noCard: CardFields = { effects: [], facts: [], attrs: {} };

/** `items` joined with their entries from the card shards. */
export async function withCards(items: DiscoveryItem[]): Promise<SearchItem[]> {
  const shards = new Map(
    await Promise.all(
      [...new Set(items.map((i) => i.kind))].map(async (k) => [k, await cards(k)] as const),
    ),
  );
  return items.map((item) => withCard(item, shards.get(item.kind)?.[item.id] ?? noCard));
}

export const useSearchStore = defineStore("search", () => {
  const q = ref("");
  const kind = ref("");
  const attributes = ref<Attributes>({});
  const items = shallowRef<SearchItem[]>([]);
  const total = ref(0);
  const facets = shallowRef<DiscoveryResult["facets"]>({
    kinds: [],
    conditions: [],
    attributes: [],
  });
  const ready = ref(false);
  /** Search text or a type produced the shown results. */
  const narrowed = ref(false);
  let version = 0;

  async function run() {
    const current = ++version;
    try {
      const [index, phrased] = await Promise.all([discoveryPack(), textIds(q.value)]);
      // The chosen filters can exclude every component holding the phrase.
      const { ids, found: result } = await fallBackToScattered(
        q.value,
        phrased,
        (matching) =>
          query(index, {
            q: q.value,
            kind: kind.value,
            attributes: attributes.value,
            ids: matching,
          }),
        (found) => found.total > 0,
      );
      const carded = await withCards(result.items);
      if (current !== version) return;
      items.value = carded;
      total.value = result.total;
      facets.value = result.facets;
      narrowed.value = !!ids || !!kind.value;
      ready.value = true;
    } catch (error) {
      if (current !== version) return;
      console.error(error);
      toastError(t("search.loadFailed"));
    }
  }

  return {
    q,
    kind,
    attributes,
    items,
    total,
    facets,
    ready,
    narrowed,
    run,
  };
});
