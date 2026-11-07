<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";
import type { Effect, ObjectSummary } from "@/data";
import { className, t } from "@/i18n";
import EffectText from "./EffectText.vue";
import IdentityIcon from "./IdentityIcon.vue";
import RouteCard from "./RouteCard.vue";
import { hitRanks, objectRoute, type Hit } from "./presentation";

type SummaryEffect = Pick<Effect, "id" | "name" | "description" | "segments"> &
  Partial<Pick<Effect, "label" | "rank">>;

const props = withDefaults(
  defineProps<{
    data: Partial<ObjectSummary> &
      Pick<ObjectSummary, "id" | "kind" | "name"> & { matched_rules?: Hit[] };
    limit?: number;
    /** A relic shows only the ranks up to this one. */
    rank?: number | null;
    links?: boolean;
    facts?: boolean;
    /** Effect ids already shown elsewhere on the page. */
    omit?: string[];
    sources?: boolean;
    classIcon?: boolean;
    /** A relic shows only the ranks the visitor arrived for. */
    matchedOnly?: boolean;
    contextIds?: string[];
  }>(),
  {
    limit: Infinity,
    rank: null,
    links: true,
    facts: true,
    omit: () => [],
    sources: false,
    classIcon: true,
    matchedOnly: false,
    contextIds: () => [],
  },
);

const spellGem = computed(() => props.data.kind === "spell");
const ranks = computed(() => hitRanks(props.data.matched_rules || []));
const effects = computed<SummaryEffect[]>(() => {
  const data = props.data;
  let list: SummaryEffect[] = (data.effects || []).filter((e) => !props.omit.includes(e.id));
  if (data.kind === "enchantment") list = list.filter((e) => e.description?.trim() !== data.name);
  const hit = ranks.value;
  if (props.matchedOnly && data.kind === "relic" && hit.size)
    list = list.filter((e) => hit.has(Number(e.rank)));
  if (hit.size)
    list = [
      ...list.filter((e) => hit.has(Number(e.rank))),
      ...list.filter((e) => !hit.has(Number(e.rank))),
    ];
  if (props.rank !== null && data.kind === "relic")
    list = list.filter((e) => Number(e.rank) <= props.rank!);
  if (
    !data.effects?.length &&
    data.description &&
    !props.omit.includes(data.id) &&
    !["specialization", "realm", "god", "shop"].includes(data.kind)
  )
    list = [
      { id: data.id, name: data.name, description: data.description, segments: data.segments },
    ];
  return list;
});
/** A shortened relic lists its ranks behind a toggle. */
const shown = computed(() =>
  props.data.kind === "relic" && props.limit !== Infinity ? 0 : props.limit,
);
const first = computed(() => effects.value.slice(0, shown.value));
const rest = computed(() => effects.value.slice(shown.value));
const moreLabel = computed(() => {
  const kind =
    props.data.kind === "relic"
      ? "Ranks"
      : props.data.kind === "specialization"
        ? "Perks"
        : "Effects";
  const key = first.value.length ? `more${kind}` : kind.toLowerCase();
  return t(`reference.${key}`, { count: rest.value.length });
});
const showFacts = computed(
  () => props.facts && ((props.data.facts || []).length || (spellGem.value && props.classIcon)),
);
const named = (e: SummaryEffect) =>
  e.id !== props.data.id && e.name !== props.data.name && props.data.kind !== "relic";
const effectContext = (e: SummaryEffect) => [...props.contextIds, props.data.id, e.id];
</script>

<template>
  <div class="object-summary">
    <div v-if="showFacts" class="summary-facts">
      <IdentityIcon
        v-if="spellGem && classIcon"
        :id="links ? data.attrs?.class_id : null"
        :src="data.attrs?.class_icon"
        :label="className(data.attrs?.class ?? '') || t('reference.spell')"
      />{{ (data.facts || []).join(" · ") }}
    </div>
    <div
      v-for="e in first"
      :key="e.id + (e.label ?? '')"
      :class="['summary-effect', { 'effect-hit': ranks.has(Number(e.rank)) }]"
    >
      <small v-if="e.label">{{ e.label }}</small>
      <strong v-if="named(e)">
        <RouterLink v-if="links" class="link" :to="objectRoute(e.id)">{{ e.name }}</RouterLink>
        <template v-else>{{ e.name }}</template>
      </strong>
      <p>
        <EffectText :text="e.description" :segments="e.segments" :context-ids="effectContext(e)" />
      </p>
    </div>
    <details v-if="rest.length" class="summary-more">
      <summary>{{ moreLabel }}</summary>
      <div
        v-for="e in rest"
        :key="e.id + (e.label ?? '')"
        :class="['summary-effect', { 'effect-hit': ranks.has(Number(e.rank)) }]"
      >
        <small v-if="e.label">{{ e.label }}</small>
        <strong v-if="named(e)">
          <RouterLink v-if="links" class="link" :to="objectRoute(e.id)">{{ e.name }}</RouterLink>
          <template v-else>{{ e.name }}</template>
        </strong>
        <p>
          <EffectText
            :text="e.description"
            :segments="e.segments"
            :context-ids="effectContext(e)"
          />
        </p>
      </div>
    </details>
    <template v-if="sources">
      <RouteCard v-for="route in data.routes || []" :key="route.id" :route="route" />
    </template>
  </div>
</template>
