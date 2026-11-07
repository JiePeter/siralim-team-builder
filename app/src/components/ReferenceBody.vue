<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";
import type { ObjectPage, ObjectSummary as Summary } from "@/data";
import { className, t } from "@/i18n";
import { useTeamStore } from "@/stores/team";
import AddButton from "./AddButton.vue";
import EffectText from "./EffectText.vue";
import GameSprite from "./GameSprite.vue";
import GodReference from "./GodReference.vue";
import IdentityIcon from "./IdentityIcon.vue";
import IdentityLine from "./IdentityLine.vue";
import ObjectCell from "./ObjectCell.vue";
import ObjectLink from "./ObjectLink.vue";
import ObjectRegion from "./ObjectRegion.vue";
import ObjectSummary from "./ObjectSummary.vue";
import RouteCard from "./RouteCard.vue";
import ShopOffers from "./ShopOffers.vue";
import { hitPerks, hitRanks, kindNames, objectRoute, routeView, type Hit } from "./presentation";
import { usePlacedText } from "./tray";

const props = withDefaults(defineProps<{ data: ObjectPage; hits?: Hit[] }>(), { hits: () => [] });

const store = useTeamStore();
const placed = usePlacedText();
const perkItem = (p: Summary) => ({
  id: p.id,
  kind: "perk",
  name: String(p.attrs.short_name || p.name),
});
const contextIds = computed(() => [props.data.id]);
const rowOptions = computed(() => {
  const kind = props.data.kind;
  return {
    contextIds: contextIds.value,
    omit: (props.data.traits || []).map((t) => t.id),
    omitIdentity: ["race", "class"].includes(kind) ? [kind] : [],
    classIcon: kind !== "class",
    sources: ["race", "class", "material", "enchantment"].includes(kind) ? false : null,
    identity: !["material", "enchantment"].includes(kind),
  };
});

const ownRoutes = computed(() => (props.data.routes || []).filter((r) => routeView(r)));
const stats = computed(() =>
  (
    [
      ["health", t("reference.stats.health")],
      ["attack", t("reference.stats.attack")],
      ["intelligence", t("reference.stats.intelligence")],
      ["defense", t("reference.stats.defense")],
      ["speed", t("reference.stats.speed")],
    ] as const
  )
    .filter(([key]) => props.data.attrs?.stats?.[key] !== undefined)
    .map(([key, label]) => ({ label, value: props.data.attrs.stats![key] })),
);

const shopMethods = ["purchase", "shop_source", "purchase_inscription_then_craft"];
const shopRoutes = computed(() => ownRoutes.value.filter((r) => shopMethods.includes(r.method)));
const otherRoutes = computed(() => ownRoutes.value.filter((r) => !shopMethods.includes(r.method)));

const ranks = computed(() => hitRanks(props.hits));
const perks = computed(() => hitPerks(props.hits));
const targetRank = computed(() => {
  const relic = store.team.slots.find(
    (s) => (typeof s.relic === "string" ? s.relic : s.relic?.id) === props.data.id,
  )?.relic;
  return typeof relic === "object" ? relic.rank : undefined;
});
const relicRanks = computed(() =>
  [...props.data.effects].sort((a, b) => Number(a.rank) - Number(b.rank)),
);

const realmGroups = computed(() => {
  const groups = new Map<string, Summary[]>();
  for (const c of props.data.creatures || []) {
    const label = String(c.routes[0]?.requirements?.interaction || t("reference.encounters"));
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label)!.push(c);
  }
  return [...groups];
});

const ownSummary = computed(
  () =>
    (!props.data.description || props.data.kind === "card_set") &&
    props.data.effects?.some((e) => e.id === props.data.id),
);
</script>

<template>
  <template v-if="data.kind === 'creature'">
    <nav
      class="family-switcher"
      :aria-label="
        t('reference.raceCreatures', {
          race: data.classification?.[0]?.race || t('reference.race'),
        })
      "
    >
      <ObjectCell
        v-for="member in data.family"
        :key="member.id"
        :data="member"
        layout="tile"
        :to="objectRoute(member.id)"
        :aria-current="member.id === data.id ? 'page' : undefined"
      >
        <template #label>{{ member.name }}</template>
      </ObjectCell>
    </nav>
  </template>

  <template v-if="data.kind === 'creature' || data.kind === 'material'">
    <section v-for="(trait, position) in data.traits" :key="trait.id" class="reference-trait">
      <RouterLink class="link" :to="objectRoute(trait.id)">{{ trait.name }}</RouterLink>
      <p>
        <EffectText
          :text="trait.description"
          :segments="trait.segments"
          :context-ids="[...contextIds, trait.id]"
        />
      </p>
      <slot v-if="position === 0" name="trait" />
    </section>
  </template>

  <template v-if="data.kind === 'creature'">
    <div class="creature-facts">
      <dl class="creature-stats">
        <div v-for="s in stats" :key="s.label">
          <dt>{{ s.label }}</dt>
          <dd>{{ s.value }}</dd>
        </div>
      </dl>
      <div v-if="ownRoutes.length" class="creature-origins">
        <h3>{{ t("reference.foundIn") }}</h3>
        <RouteCard v-for="route in ownRoutes" :key="route.id" :route="route" />
      </div>
    </div>
    <section v-if="data.materials.length">
      <h2>{{ t("reference.traitMaterial") }}</h2>
      <ObjectRegion
        v-for="item in data.materials"
        :key="item.id"
        :item="item"
        v-bind="rowOptions"
      />
    </section>
  </template>

  <template v-else-if="data.kind === 'material'">
    <ObjectSummary
      v-if="!data.traits.length"
      :data="data"
      :facts="false"
      :context-ids="contextIds"
    />
    <div v-if="data.creatures.length || ownRoutes.length" class="material-acquisition">
      <section v-if="data.creatures.length">
        <h2>{{ t("reference.creatures") }}</h2>
        <ObjectRegion
          v-for="item in data.creatures"
          :key="item.id"
          :item="item"
          v-bind="rowOptions"
        />
      </section>
      <section v-if="shopRoutes.length">
        <h2>{{ t("reference.shops") }}</h2>
        <RouteCard v-for="route in shopRoutes" :key="route.id" :route="route" />
      </section>
      <section v-if="otherRoutes.length">
        <h2>{{ t("reference.otherSources") }}</h2>
        <RouteCard v-for="route in otherRoutes" :key="route.id" :route="route" />
      </section>
    </div>
  </template>

  <template v-else-if="data.kind === 'trait'">
    <div v-for="item in data.options" :key="item.id" class="source-line">
      <span>{{ kindNames[item.kind] || item.kind }}</span>
      <div><ObjectLink :item="item" /></div>
    </div>
  </template>

  <template v-else-if="data.kind === 'relic'">
    <p v-if="targetRank" class="muted">
      {{ t("reference.buildTarget", { rank: targetRank }) }}
    </p>
    <div class="rank-list">
      <section
        v-for="r in relicRanks"
        :key="r.id"
        :class="['rank-effect', { 'effect-hit': ranks.has(Number(r.rank)) }]"
        :data-rank="r.rank"
        :data-focus-hit="ranks.has(Number(r.rank)) || undefined"
      >
        <strong>{{ t("reference.rank", { rank: r.rank }) }}</strong>
        <p><EffectText :text="r.description" :segments="r.segments" :context-ids="contextIds" /></p>
      </section>
    </div>
  </template>

  <template v-else-if="data.kind === 'specialization'">
    <div class="perk-list">
      <section
        v-for="p in data.perks"
        :key="p.id"
        :class="['perk-option', { 'effect-hit': perks.has(p.id) }]"
        :data-perk="p.id"
        :data-focus-hit="perks.has(p.id) || undefined"
      >
        <div class="section-head">
          <div class="perk-title">
            <strong><GameSprite :data="p" />{{ p.attrs.short_name || p.name }}</strong>
            <div class="muted">
              {{
                p.attrs.ascension
                  ? t("reference.ascension")
                  : t("reference.rankRange", { ranks: p.attrs.ranks })
              }}
              <template v-if="p.attrs.anointment && placed(perkItem(p))">
                · <span class="perk-added">{{ placed(perkItem(p)) }}</span>
              </template>
            </div>
          </div>
          <AddButton v-if="p.attrs.anointment" quick :item="perkItem(p)" />
        </div>
        <p>
          <EffectText
            :text="p.description"
            :segments="p.segments"
            :context-ids="[...contextIds, p.id]"
          />
        </p>
      </section>
    </div>
  </template>

  <template v-else-if="data.kind === 'realm'">
    <ObjectRegion v-for="item in data.related" :key="item.id" :item="item" v-bind="rowOptions" />
    <section v-for="[label, creatures] in realmGroups" :key="label">
      <h2>
        {{ label }} <small>{{ creatures.length }}</small>
      </h2>
      <div class="realm-creatures">
        <article v-for="c in creatures" :key="c.id">
          <IdentityLine :data="c">
            <ObjectLink :item="c" />
            <template v-if="c.routes[0]?.requirements?.source_realm_depth" #meta>
              <small class="realm-depth">{{
                t("reference.realmDepth", { depth: c.routes[0].requirements.source_realm_depth })
              }}</small>
            </template>
          </IdentityLine>
          <ObjectSummary :data="c" :context-ids="contextIds" />
        </article>
      </div>
    </section>
  </template>

  <GodReference v-else-if="data.kind === 'god'" :data="data" :context-ids="contextIds" />

  <template v-else-if="data.kind === 'shop'">
    <ObjectRegion v-for="item in data.related" :key="item.id" :item="item" v-bind="rowOptions" />
    <ShopOffers :offers="data.offers" :context-ids="contextIds" />
  </template>

  <template v-else>
    <ObjectRegion
      v-for="item in data.related || []"
      :key="item.id"
      :item="item"
      v-bind="rowOptions"
    />
    <ObjectSummary v-if="ownSummary" :data="data" :context-ids="contextIds" />
    <div v-if="data.kind === 'spell'" class="spell-facts">
      <IdentityIcon
        :src="data.attrs.class_icon"
        :label="className(data.attrs.class ?? '') || t('reference.spell')"
      />
      {{ t("reference.charges", { charges: data.attrs.charges ?? "—" })
      }}{{ data.attrs.manually_castable === false ? ` · ${t("reference.automaticOnly")}` : "" }}
    </div>
    <ObjectRegion v-for="item in data.products" :key="item.id" :item="item" v-bind="rowOptions" />
    <RouteCard v-for="route in ownRoutes" :key="route.id" :route="route" />
  </template>

  <template v-for="section in data.sections || []" :key="section.title">
    <section v-if="section.items.length" class="related-section">
      <h2>
        {{ section.title }} <small>{{ section.items.length }}</small>
      </h2>
      <ObjectRegion
        v-for="item in section.items"
        :key="item.id"
        :item="item as Summary"
        v-bind="rowOptions"
        :matched-only="section.title === 'Cast by'"
      />
    </section>
  </template>
</template>
