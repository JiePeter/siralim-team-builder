<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";
import { createReusableTemplate } from "@vueuse/core";
import type { Effect } from "@/data";
import { className, t } from "@/i18n";
import EffectText from "./EffectText.vue";
import IdentityIcon from "./IdentityIcon.vue";
import RouteCard from "./RouteCard.vue";
import { hitRanks, objectRoute, type SummaryData } from "./presentation";

type SummaryEffect = Pick<Effect, "id" | "name" | "description" | "segments"> &
  Partial<Pick<Effect, "label" | "rank">>;

const [DefineEffect, ReuseEffect] = createReusableTemplate<{ effect: SummaryEffect }>({
  inheritAttrs: false,
});

const props = withDefaults(
  defineProps<{
    data: SummaryData;
    limit?: number;
    links?: boolean;
    sources?: boolean;
    /** An effect name the surrounding row already shows. */
    titled?: string;
  }>(),
  {
    limit: Infinity,
    links: true,
    sources: false,
    titled: "",
  },
);

const spellGem = computed(() => props.data.kind === "spell");
const ranks = computed(() => hitRanks(props.data.matched_rules || []));
const effects = computed<SummaryEffect[]>(() => {
  const data = props.data;
  let list: SummaryEffect[] = data.effects || [];
  if (data.kind === "enchantment") list = list.filter((e) => e.description?.trim() !== data.name);
  const hit = ranks.value;
  if (hit.size)
    list = [
      ...list.filter((e) => hit.has(Number(e.rank))),
      ...list.filter((e) => !hit.has(Number(e.rank))),
    ];
  if (
    !data.effects?.length &&
    data.description &&
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
const showFacts = computed(() => (props.data.facts || []).length || spellGem.value);
const named = (e: SummaryEffect) =>
  e.id !== props.data.id &&
  e.name !== props.data.name &&
  e.name !== props.titled &&
  props.data.kind !== "relic";
const effectContext = (e: SummaryEffect) => [props.data.id, e.id];
</script>

<template>
  <div class="object-summary">
    <DefineEffect v-slot="{ effect: e }">
      <div :class="['summary-effect', { 'effect-hit': ranks.has(Number(e.rank)) }]">
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
    </DefineEffect>
    <div v-if="showFacts" class="summary-facts">
      <IdentityIcon
        v-if="spellGem"
        :id="links ? data.attrs?.class_id : null"
        :src="data.attrs?.class_icon"
        :label="className(data.attrs?.class ?? '') || t('reference.spell')"
      />{{ (data.facts || []).join(" · ") }}
    </div>
    <ReuseEffect v-for="e in first" :key="e.id + (e.label ?? '')" :effect="e" />
    <details v-if="rest.length" class="summary-more">
      <summary>{{ moreLabel }}</summary>
      <ReuseEffect v-for="e in rest" :key="e.id + (e.label ?? '')" :effect="e" />
    </details>
    <template v-if="sources">
      <RouteCard v-for="route in data.routes || []" :key="route.id" :route="route" />
    </template>
  </div>
</template>
