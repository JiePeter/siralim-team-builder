import { ref, shallowRef } from "vue";
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
  type TextHits,
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
      // A prefix hit scores 0.375 of a whole word, which keeps one in a name below a word in the text.
      searchOptions: {
        prefix: true,
        combineWith: "AND",
        boost: { name: 4, members: 3, text: 2, locations: 1 },
      },
    });
    index.addAll(searchDocuments(pack));
    return index;
  }),
);

/** The fields holding `runs` unbroken or another matched word; none when a name matched. */
function fieldsOf(hit: SearchResult, runs: string[]): string[] {
  const fields = new Set([
    ...Object.entries(hit.match)
      .filter(([term]) => !runs.some((run) => run.includes(term)))
      .flatMap(([, where]) => where),
    ...TEXT_FIELDS.filter((field) => runs.some((run) => String(hit[field]).includes(run))),
  ]);
  return fields.has("name") || fields.has("members") ? [] : [...fields];
}

const hitsOf = (hits: SearchResult[], runs: string[] = []): TextHits =>
  new Map(hits.map((hit) => [String(hit.id), { score: hit.score, fields: fieldsOf(hit, runs) }]));

/** The components with every word of `q` anywhere in their text. */
export async function scatteredHits(q: string): Promise<TextHits> {
  return hitsOf((await textIndex()).search(q));
}

/**
 * The components whose text matches `q`; undefined when `q` has no words to match.
 * Those holding every Han run of `q` unbroken within a field, when there are any; else all matches.
 */
export async function textHits(q: string): Promise<TextHits | undefined> {
  if (!words(fold(q)).length) return undefined;
  const hits = (await textIndex()).search(q);
  const runs = hanRuns(q);
  const phrased = hits.filter((hit) =>
    runs.every((run) => TEXT_FIELDS.some((field) => String(hit[field]).includes(run))),
  );
  return phrased.length ? hitsOf(phrased, runs) : hitsOf(hits);
}

/**
 * What `attempt` finds with the components holding the phrase, or with the scattered matches of
 * `q` when `hasHits` rejects that; `phrased` is `textHits(q)`.
 */
export async function fallBackToScattered<T>(
  q: string,
  phrased: TextHits | undefined,
  attempt: (ids: TextHits | undefined) => T,
  hasHits: (found: T) => boolean,
): Promise<{ ids: TextHits | undefined; found: T }> {
  const found = attempt(phrased);
  if (!phrased || hasHits(found)) return { ids: phrased, found };
  const ids = await scatteredHits(q);
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
  /** Search text, a type or a mechanic produced the shown results. */
  const narrowed = ref(false);
  let version = 0;

  async function run() {
    const current = ++version;
    try {
      const [index, phrased] = await Promise.all([discoveryPack(), textHits(q.value)]);
      const wanted = !!phrased || !!kind.value || conditions.value.some((c) => c.category);
      // The chosen filters can exclude every component holding the phrase.
      const { found: result } = await fallBackToScattered(
        q.value,
        phrased,
        (matching) =>
          query(index, {
            q: q.value,
            kind: kind.value,
            attributes: attributes.value,
            conditions: conditions.value,
            scope: scope.value,
            ids: matching,
            limit: wanted ? Infinity : 0,
          }),
        (found) => found.total > 0,
      );
      const carded = await withCards(result.items);
      if (current !== version) return;
      items.value = carded;
      total.value = result.total;
      facets.value = result.facets;
      narrowed.value = wanted;
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
    conditions,
    scope,
    items,
    total,
    facets,
    ready,
    narrowed,
    run,
  };
});
