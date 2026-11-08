<script setup lang="ts">
import { computed, reactive, shallowRef, watch } from "vue";
import { RouterLink } from "vue-router";
import { object, type Offer, type ObjectPage, type ObjectSummary, type Route } from "@/data";
import { className, i18n, t } from "@/i18n";
import AddButton from "./AddButton.vue";
import CellPlate from "./CellPlate.vue";
import CreatureStats from "./CreatureStats.vue";
import DetailItem from "./DetailItem.vue";
import EffectText from "./EffectText.vue";
import { hitPerks, hitRanks, kindNames, objectRoute, routeView, type Hit } from "./presentation";

const props = withDefaults(
  defineProps<{
    data: ObjectPage;
    hits?: Hit[];
    /** Shown inside a dialog over the build, where switching to a family member does not belong. */
    preview?: boolean;
  }>(),
  { hits: () => [], preview: false },
);

/** Name lists show this many before the rest are asked for. */
const LIST_LIMIT = 24;
/** A god's shop shows its first offers before the rest are asked for. */
const OFFER_LIMIT = 6;
const addableKinds = new Set(["creature", "trait", "material", "spell", "relic", "specialization"]);

const kind = computed(() => props.data.kind);
const contextIds = computed(() => [props.data.id]);
const addable = computed(() => props.data.selectable && kind.value !== "enchantment");
const ranks = computed(() => hitRanks(props.hits));
const perks = computed(() => hitPerks(props.hits));
const listSeparator = computed(() => (i18n.global.locale.value.startsWith("zh") ? "、" : ", "));

const expanded = reactive<Record<string, boolean>>({});
const partner = shallowRef<ObjectPage | null>(null);
const carriers = shallowRef<ObjectPage[]>([]);

let version = 0;
watch(
  () => props.data.id,
  async () => {
    const current = ++version;
    for (const key of Object.keys(expanded)) delete expanded[key];
    partner.value = null;
    carriers.value = [];
    const data = props.data;
    // A God and its Realm read as one page: the Realm brings its creatures, the God its shop.
    const partnerId =
      data.kind === "realm"
        ? data.related?.find((r) => r.kind === "god")?.id
        : data.kind === "god"
          ? data.god_contents?.realms?.[0]?.id
          : undefined;
    if (partnerId) {
      const found = await object(partnerId).catch(() => null);
      if (current === version) partner.value = found;
    }
    if (data.kind === "trait" && data.options?.length) {
      const found = await Promise.all(data.options.map((o) => object(o.id).catch(() => null)));
      if (current === version) carriers.value = found.filter((c): c is ObjectPage => !!c);
    }
  },
  { immediate: true },
);

const god = computed(() => (kind.value === "god" ? props.data : partner.value));
const realm = computed(() => (kind.value === "realm" ? props.data : partner.value));
const offers = computed(() =>
  kind.value === "shop"
    ? (props.data.offers ?? [])
    : (god.value?.god_contents?.shops?.[0]?.offers ?? []),
);
/** The Favor rank has its own mark on the offer. */
const offerFacts = (offer: Offer) =>
  routeView({
    method: "purchase",
    requirements: { ...offer.requirements, favor_rank: "", ...offer.cost },
    via: offer.via,
  })?.facts.join(" · ");
const realmCreatures = computed(() => realm.value?.creatures ?? []);
const godParts = computed(() => {
  const content = god.value?.god_contents;
  if (!content) return [];
  return (
    [
      ["relics", t("reference.relic")],
      ["godspawn", t("reference.godspawn")],
      ["ultimate_spells", t("reference.ultimateSpell")],
    ] as const
  )
    .map(([key, title]) => ({ key, title, items: content[key] ?? [] }))
    .filter((part) => part.items.length);
});

const identity = computed(() => {
  const data = props.data;
  if (!["creature", "trait", "spell"].includes(kind.value)) return null;
  const cls = data.classification?.[0]?.class ?? data.attrs.class ?? "";
  const race =
    kind.value === "spell" ? "" : (data.classification?.[0]?.race ?? data.attrs.race ?? "");
  return {
    classIcon: data.attrs.class_icon,
    className: cls ? className(cls) : "",
    raceIcon: kind.value === "creature" ? data.attrs.race_icon : undefined,
    race,
  };
});

const lastParagraph = (text: string) => text.split("\n\n").pop() ?? text;
/** The effect shown in the head; pages whose text belongs to a part below leave it out. */
const headEffect = computed(
  () =>
    !!props.data.description &&
    ![
      "creature",
      "material",
      "race",
      "specialization",
      "god",
      "realm",
      "class",
      "card_set",
    ].includes(kind.value),
);

const purchaseMethods = ["purchase", "shop_source", "purchase_inscription_then_craft"];
const routes = computed<Route[]>(() => (props.data.routes ?? []).filter((r) => r.location_name));
function routeTerms(list: Route[]): string[] {
  const priced = list.find((r) => r.requirements?.cost);
  const req = priced?.requirements ?? list[0]?.requirements ?? {};
  const depths = [...new Set(list.map((r) => r.requirements?.source_realm_depth).filter(Boolean))];
  return [
    req.cost ? `${req.cost} ${req.currency ?? ""}`.trim() : "",
    req.favor_rank ? t("tray.route.favor", { rank: req.favor_rank }) : "",
    req.rank ? t("tray.route.rank", { rank: req.rank }) : "",
    req.project_required ? t("tray.route.projectRequired") : "",
    depths.length ? t("tray.route.realmDepth", { depth: depths.join("/") }) : "",
  ].filter(Boolean);
}
const found = computed(() => {
  const list = routes.value;
  if (!list.length) return null;
  const bought = list.every((r) => purchaseMethods.includes(r.method));
  const places = [...new Set(list.map((r) => r.location_name))];
  return {
    label: bought ? t("reference.boughtAt") : t("reference.foundIn"),
    places,
    via: list[0]?.via ?? "",
    terms: routeTerms(list),
  };
});

/** Where a Trait's carrier comes from, without its price. */
function carrierSource(carrier: ObjectPage): string {
  const route = carrier.routes?.find((r) => r.location_name);
  if (route)
    return [
      `${t("reference.boughtAt")} ${route.location_name}`,
      ...routeTerms([route]).filter((term) => !term.startsWith(String(route.requirements?.cost))),
    ].join(" · ");
  const from = carrier.creatures?.map((c) => c.name).join(listSeparator.value);
  return from ? `${t("reference.from")} ${from}` : "";
}

/** The Trait a creature or material carries pairs with the other half of that pair. */
const traitPartner = computed(() => {
  if (kind.value === "creature") {
    const material = props.data.materials?.[0];
    if (!material) return null;
    return {
      item: material,
      label: kindNames.material,
      note: material.routes?.[0]?.location_name ?? "",
    };
  }
  if (kind.value === "material") {
    const creature = props.data.creatures?.[0];
    if (!creature) return null;
    const c = creature.classification?.[0];
    const note = [className(c?.class ?? creature.attrs.class ?? ""), c?.race ?? creature.attrs.race]
      .filter(Boolean)
      .join(" · ");
    return { item: creature, label: kindNames.creature, note };
  }
  return null;
});

const family = computed(() =>
  kind.value === "creature" && !props.preview ? (props.data.family ?? []) : [],
);

const relicRanks = computed(() =>
  [...(props.data.effects ?? [])].sort((a, b) => Number(a.rank) - Number(b.rank)),
);

const condition = computed(() => {
  if (kind.value !== "condition") return null;
  const type = String(props.data.attrs.type ?? "");
  return {
    type,
    label: type ? t(`reference.kinds.${type}`) : "",
    duration: props.data.attrs.duration,
  };
});

const variants = computed(
  () =>
    (props.data.attrs.variants as { id: number; label: string; image: string }[] | undefined) ?? [],
);

type Item = ObjectSummary & { matched_rules?: { rank?: number | null }[] };
/** Lists of creatures or Spell Gems on a race or class page read as names. */
const nameKinds = new Set(["creature", "spell"]);
const sections = computed(() =>
  (props.data.sections ?? [])
    .filter((s) => s.items.length)
    .map((s) => {
      const items = s.items as Item[];
      const style =
        items[0]?.kind === "card_set"
          ? "tiers"
          : ["race", "class"].includes(kind.value) && items.every((i) => nameKinds.has(i.kind))
            ? "names"
            : "items";
      return { title: s.title, items, style };
    }),
);

function itemLevel(item: Item): string {
  const rank = item.matched_rules?.[0]?.rank;
  return item.kind === "relic" && rank ? t("reference.level", { rank }) : "";
}
function itemFaint(item: Item): string {
  if (item.kind === "relic") return kindNames.relic ?? "";
  const effect = item.effects?.[0];
  if (effect?.name && effect.name !== item.name) return effect.name;
  return item.classification?.[0]?.race ?? "";
}
function itemText(item: Item) {
  const rank = item.matched_rules?.[0]?.rank;
  if (item.kind === "relic" && rank) return item.effects?.find((e) => e.rank === rank) ?? null;
  const effect = item.effects?.[0];
  return effect?.description ? effect : item.description ? item : null;
}
const shown = <T,>(key: string, list: T[], limit = LIST_LIMIT) =>
  expanded[key] || list.length <= limit ? list : list.slice(0, limit);
</script>

<template>
  <div :class="['object-detail', `detail-${kind}`]">
    <header :class="['detail-head', { 'with-stats': kind === 'creature' }]">
      <AddButton v-if="addable" class="detail-plate" :item="data" :plate="data" />
      <CellPlate v-else class="detail-plate" :data="data" />
      <div class="detail-titles">
        <h1>
          {{ data.attrs.short_name || data.name
          }}<span class="detail-kind">{{ kindNames[kind] || kind }}</span>
        </h1>
        <div v-if="identity" class="detail-sub">
          <span v-if="identity.className" class="detail-icon-text"
            ><img v-if="identity.classIcon" :src="identity.classIcon" alt="" />{{
              identity.className
            }}</span
          >
          <span v-if="identity.race" class="detail-icon-text"
            ><img v-if="identity.raceIcon" :src="identity.raceIcon" alt="" />{{
              identity.race
            }}</span
          >
          <span v-for="fact in kind === 'spell' ? data.facts : []" :key="fact">{{ fact }}</span>
        </div>
        <div v-else-if="kind === 'race' && data.description" class="detail-sub">
          {{ data.description }}
        </div>
        <div v-else-if="kind === 'god' || kind === 'realm'" class="detail-sub">
          <template v-if="kind === 'god'">
            <span v-for="fact in data.facts" :key="fact">{{ fact }}</span>
            <span v-if="realm"
              >{{ t("reference.realm") }} -
              <RouterLink class="detail-strong" :to="objectRoute(realm.id)">{{
                realm.name
              }}</RouterLink></span
            >
          </template>
          <span v-else-if="god"
            >{{ kindNames.god }} -
            <RouterLink class="detail-strong" :to="objectRoute(god.id)">{{
              god.name
            }}</RouterLink></span
          >
        </div>
        <div v-else-if="condition" class="detail-sub">
          <span v-if="condition.label" :class="['detail-tag', condition.type]">{{
            condition.label
          }}</span>
          <span v-if="condition.duration">{{
            t("reference.duration", { n: condition.duration })
          }}</span>
        </div>
        <p v-else-if="kind === 'specialization' && data.description" class="detail-note">
          {{ lastParagraph(data.description) }}
        </p>
      </div>
      <div v-if="found" class="detail-found">
        <div>
          {{ found.label }}
          <template v-for="(place, i) in found.places" :key="place"
            >{{ i ? listSeparator : " " }}<b>{{ place }}</b></template
          ><template v-if="found.via">
            · <b>{{ found.via }}</b></template
          >
        </div>
        <div v-if="found.terms.length">{{ found.terms.join(" · ") }}</div>
      </div>
      <CreatureStats v-if="kind === 'creature'" :data="data" />
      <p v-if="headEffect" class="detail-effect">
        <EffectText :text="data.description" :segments="data.segments" :context-ids="contextIds" />
      </p>
    </header>
    <slot name="head" />

    <section
      v-for="trait in kind === 'creature' || kind === 'material' ? data.traits : []"
      :key="trait.id"
      class="detail-section detail-split"
    >
      <h2 class="detail-trait-name">
        <RouterLink :to="objectRoute(trait.id)">{{ trait.name }}</RouterLink>
      </h2>
      <p class="detail-split-text">
        <EffectText
          :text="trait.description"
          :segments="trait.segments"
          :context-ids="[...contextIds, trait.id]"
        />
      </p>
      <div v-if="traitPartner" class="detail-side">
        <DetailItem :item="traitPartner.item" :addable="true">
          <small
            >{{ traitPartner.label
            }}<template v-if="traitPartner.note"> · {{ traitPartner.note }}</template></small
          >
        </DetailItem>
      </div>
    </section>

    <section v-if="family.length" class="detail-section">
      <h2>
        {{ t("reference.raceCreatures", { race: data.classification?.[0]?.race ?? "" })
        }}<span class="detail-count">{{ family.length }}</span>
      </h2>
      <nav
        :class="['detail-family', { tiles: family.length <= 9 }]"
        :style="{ '--n': family.length }"
      >
        <RouterLink
          v-for="member in family"
          :key="member.id"
          :to="objectRoute(member.id)"
          :aria-current="member.id === data.id ? 'page' : undefined"
        >
          <CellPlate :data="member" compact />
          <span>{{ member.name }}</span>
        </RouterLink>
      </nav>
    </section>

    <section v-if="kind === 'trait' && data.options?.length" class="detail-section">
      <h2>
        {{ t("reference.sources") }}<span class="detail-count">{{ data.options.length }}</span>
      </h2>
      <div class="detail-grid two">
        <DetailItem
          v-for="carrier in carriers.length ? carriers : data.options"
          :key="carrier.id"
          :item="carrier"
          :faint="kindNames[carrier.kind]"
          addable
        >
          <small v-if="'routes' in carrier && carrierSource(carrier)" class="detail-source">{{
            carrierSource(carrier)
          }}</small>
        </DetailItem>
      </div>
    </section>

    <div v-if="kind === 'relic'" class="detail-ranks">
      <div
        v-for="r in relicRanks"
        :key="r.id"
        :class="['detail-rank', { 'effect-hit': ranks.has(Number(r.rank)) }]"
        :data-rank="r.rank"
        :data-focus-hit="ranks.has(Number(r.rank)) || undefined"
      >
        <b>{{ t("reference.level", { rank: r.rank }) }}</b>
        <span
          ><EffectText :text="r.description" :segments="r.segments" :context-ids="contextIds"
        /></span>
      </div>
    </div>

    <section v-if="kind === 'specialization' && data.perks?.length" class="detail-section">
      <h2>
        {{ t("reference.perkList") }}<span class="detail-count">{{ data.perks.length }}</span>
      </h2>
      <div class="detail-grid three">
        <div
          v-for="p in data.perks"
          :key="p.id"
          :class="{ 'effect-hit': perks.has(p.id) }"
          :data-perk="p.id"
          :data-focus-hit="perks.has(p.id) || undefined"
        >
          <DetailItem
            :item="{ ...p, kind: 'perk' }"
            :addable="!!p.attrs.anointment"
            :level="p.attrs.ascension ? '' : `${p.attrs.ranks}/${p.attrs.ranks}`"
            :faint="p.attrs.ascension ? t('reference.ascension') : ''"
            :text="p"
            :context-ids="[...contextIds, p.id]"
          />
        </div>
      </div>
    </section>

    <section v-if="offers.length" class="detail-section">
      <h2>
        {{ t("reference.shop") }}<span class="detail-count">{{ offers.length }}</span>
      </h2>
      <div class="detail-grid three detail-offers">
        <div
          v-for="offer in shown('offers', offers, OFFER_LIMIT)"
          :key="offer.id"
          class="detail-offer"
        >
          <span v-if="offer.requirements.favor_rank" class="detail-favor">{{
            t("tray.route.favor", { rank: offer.requirements.favor_rank })
          }}</span>
          <DetailItem
            :item="offer.item"
            :addable="addableKinds.has(offer.item.kind)"
            :faint="itemFaint(offer.item as Item)"
          >
            <small>{{ offerFacts(offer) }}</small>
          </DetailItem>
          <p v-if="itemText(offer.item as Item)">
            <EffectText
              :text="itemText(offer.item as Item)!.description"
              :segments="itemText(offer.item as Item)!.segments ?? []"
              :context-ids="contextIds"
            />
          </p>
        </div>
      </div>
      <button
        v-if="!expanded.offers && offers.length > OFFER_LIMIT"
        type="button"
        class="detail-more"
        @click="expanded.offers = true"
      >
        {{ t("reference.showAll", { n: offers.length }) }}
      </button>
    </section>

    <section v-for="part in godParts" :key="part.key" class="detail-section">
      <h2>{{ part.title }}</h2>
      <div class="detail-grid two">
        <DetailItem
          v-for="item in part.items"
          :key="item.id"
          :item="item"
          :addable="part.key !== 'ultimate_spells' && addableKinds.has(item.kind)"
          :text="itemText(item)"
          :context-ids="contextIds"
        />
      </div>
    </section>

    <section v-if="realmCreatures.length" class="detail-section">
      <h2>
        {{ kindNames.creature }}<span class="detail-count">{{ realmCreatures.length }}</span>
      </h2>
      <div class="detail-names">
        <RouterLink v-for="c in shown('realm', realmCreatures)" :key="c.id" :to="objectRoute(c.id)">
          <CellPlate :data="c" compact /><span>{{ c.name }}</span>
        </RouterLink>
      </div>
      <button
        v-if="!expanded.realm && realmCreatures.length > LIST_LIMIT"
        type="button"
        class="detail-more"
        @click="expanded.realm = true"
      >
        {{ t("reference.showAll", { n: realmCreatures.length }) }}
      </button>
    </section>

    <section v-if="variants.length" class="detail-section">
      <div class="detail-variants">
        <div v-for="v in variants" :key="v.id"><img :src="v.image" alt="" />{{ v.label }}</div>
      </div>
    </section>

    <section v-if="kind === 'acquisition_source' && data.products?.length" class="detail-section">
      <h2>
        {{ t("reference.drops") }}<span class="detail-count">{{ data.products.length }}</span>
      </h2>
      <div class="detail-grid two">
        <DetailItem
          v-for="item in data.products"
          :key="item.id"
          :item="item"
          :addable="addableKinds.has(item.kind)"
          :faint="itemFaint(item)"
          :text="itemText(item)"
          :context-ids="contextIds"
        />
      </div>
    </section>

    <section v-for="section in sections" :key="section.title" class="detail-section">
      <h2>
        <template v-if="section.style === 'tiers'">{{ section.title }}</template>
        <template v-else
          >{{ section.title }}<span class="detail-count">{{ section.items.length }}</span></template
        >
      </h2>
      <div v-if="section.style === 'tiers'" class="detail-ranks tiers">
        <div v-for="e in section.items[0]?.effects" :key="e.id" class="detail-rank">
          <b>{{ e.label }}</b>
          <span
            ><EffectText :text="e.description" :segments="e.segments" :context-ids="contextIds"
          /></span>
        </div>
      </div>
      <template v-else-if="section.style === 'names'">
        <div class="detail-names">
          <RouterLink
            v-for="item in shown(section.title, section.items)"
            :key="item.id"
            :to="objectRoute(item.id)"
          >
            <CellPlate :data="item" compact /><span>{{ item.name }}</span>
          </RouterLink>
        </div>
        <button
          v-if="!expanded[section.title] && section.items.length > LIST_LIMIT"
          type="button"
          class="detail-more"
          @click="expanded[section.title] = true"
        >
          {{ t("reference.showAll", { n: section.items.length }) }}
        </button>
      </template>
      <div v-else class="detail-grid two">
        <DetailItem
          v-for="item in section.items"
          :key="item.id"
          :item="item"
          :addable="addableKinds.has(item.kind)"
          :level="itemLevel(item)"
          :faint="itemFaint(item)"
          :text="itemText(item)"
          :context-ids="contextIds"
        />
      </div>
    </section>
    <slot />
  </div>
</template>

<style scoped>
.object-detail {
  container-type: inline-size;
  display: grid;
  align-content: start;
  gap: 18px;
  min-width: 0;
}
.object-detail p {
  margin: 0;
}
.object-detail h1,
.object-detail h2 {
  margin: 0;
}

/* head: the plate spans the name and the lines under it; stats sit at the right */
.detail-head {
  --plate: 76px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  grid-template-areas:
    "plate titles"
    "plate found"
    "plate effect";
  align-items: center;
  gap: 6px 20px;
}
.detail-head.with-stats {
  --plate: 104px;
  grid-template-columns: auto minmax(0, 1fr) auto;
  grid-template-areas:
    "plate titles stats"
    "plate found stats";
}
.detail-plate {
  grid-area: plate;
  align-self: center;
}
.detail-head :deep(.cell-plate) {
  width: var(--plate);
  height: var(--plate);
}
.detail-head :deep(.cell-plate > img:not(.plate-badge)) {
  width: calc(var(--plate) - 6px);
  height: calc(var(--plate) - 6px);
}
.detail-head :deep(.plate-badge) {
  display: none;
}
.detail-head :deep(.kind-plate > img) {
  width: 40px;
  height: 40px;
}
.detail-titles {
  grid-area: titles;
  display: grid;
  gap: 6px;
  min-width: 0;
  align-self: end;
}
.detail-head:not(:has(.detail-found, .detail-effect)) .detail-titles {
  grid-row: 1 / -1;
  align-self: center;
}
.detail-titles h1 {
  font-size: 28px;
  line-height: 1.15;
  overflow-wrap: anywhere;
}
.detail-kind {
  display: inline-block;
  margin-left: 10px;
  color: var(--muted);
  font-size: var(--fs-13);
  font-weight: 400;
  white-space: nowrap;
}
.detail-sub {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px 8px;
  color: var(--muted);
  font-size: var(--fs-13);
  line-height: 18px;
}
.detail-sub > * + span:not(.detail-icon-text)::before {
  content: "·";
  margin-right: 8px;
}
.detail-icon-text {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}
.detail-icon-text img {
  width: 20px;
  height: 20px;
  image-rendering: pixelated;
}
.detail-strong,
.detail-found b {
  color: var(--text);
  font-weight: 400;
}
.detail-tag {
  padding: 1px 6px;
  background: var(--raised);
  font-size: var(--fs-12);
}
.detail-tag.buff {
  color: var(--buff);
}
.detail-tag.debuff {
  color: var(--debuff);
}
.detail-note {
  color: var(--muted);
  font-size: var(--fs-13);
  line-height: 20px;
}
.detail-found {
  grid-area: found;
  display: grid;
  gap: 2px;
  align-self: start;
  color: var(--muted);
  font-size: var(--fs-12);
  line-height: 18px;
}
.detail-effect {
  grid-area: effect;
  align-self: start;
  font-size: 14px;
  line-height: 21px;
}
.detail-head :deep(.creature-stats) {
  grid-area: stats;
  display: grid;
  grid-template-columns: repeat(5, auto);
  gap: 2px 14px;
  margin: 0;
  padding: 10px 14px;
  background: var(--raised);
}
.detail-head :deep(.creature-stats > div) {
  display: contents;
}
.detail-head :deep(.creature-stats dt) {
  grid-row: 1;
  color: var(--muted);
  font-size: 11px;
}
.detail-head :deep(.creature-stats dd) {
  grid-row: 2;
  margin: 0;
  font: 400 13px / 1 var(--pixel-font);
}

/* sections */
.detail-section {
  display: grid;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
  min-width: 0;
}
.detail-section > h2 {
  font-size: 16px;
}
.detail-count {
  margin-left: 8px;
  color: var(--muted);
  font: 400 11px / 1 var(--pixel-font);
}
.detail-split {
  grid-template-columns: minmax(0, 1fr) 236px;
  gap: 6px 24px;
  align-items: start;
}
.detail-split > .detail-side {
  grid-column: 2;
  grid-row: 1 / span 2;
}
.detail-trait-name a {
  color: var(--kind-trait);
  font-size: 18px;
  text-decoration: none;
}
.detail-split-text {
  font-size: 14px;
  line-height: 21px;
}
.detail-side {
  padding: 8px 10px;
  background: var(--raised);
}
.detail-side small,
.detail-source,
.detail-offer small {
  color: var(--muted);
  font-size: var(--fs-12);
  line-height: 18px;
}

.detail-family {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 16px;
}
.detail-family a,
.detail-names a {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  color: var(--text);
  font-size: var(--fs-13);
  text-decoration: none;
}
.detail-family a > span,
.detail-names a > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-family a[aria-current="page"] {
  color: var(--accent);
  font-weight: 700;
}
.detail-family.tiles {
  grid-template-columns: repeat(var(--n), minmax(0, 1fr));
  gap: 3px;
}
.detail-family.tiles a {
  flex-direction: column;
  justify-content: start;
  gap: 4px;
  padding: 8px 2px 6px;
  background: var(--raised);
  font-size: 11px;
  font-weight: 700;
  line-height: 14px;
  text-align: center;
}
.detail-family.tiles a > span {
  white-space: normal;
}
.detail-family.tiles a[aria-current="page"] {
  outline: 1px solid var(--accent);
  outline-offset: -1px;
}
.detail-family.tiles :deep(.cell-plate) {
  width: 52px;
  height: 52px;
}
.detail-family.tiles :deep(.cell-plate > img) {
  width: 46px;
  height: 46px;
}
.detail-family:not(.tiles) :deep(.cell-plate),
.detail-names :deep(.cell-plate) {
  width: 32px;
  height: 32px;
}
.detail-family:not(.tiles) :deep(.cell-plate > img),
.detail-names :deep(.cell-plate > img) {
  width: 28px;
  height: 28px;
}
.detail-family :deep(.plate-badge),
.detail-names :deep(.plate-badge) {
  display: none;
}
.detail-names {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px 16px;
}
.detail-more {
  justify-self: start;
  min-height: 32px;
  padding: 0 12px;
  font-size: var(--fs-13);
}

.detail-grid {
  display: grid;
  gap: 3px;
}
.detail-grid.two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 24px;
}
.detail-grid.three {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.detail-grid.three > * {
  padding: 10px;
  background: var(--raised);
}
.detail-grid > .effect-hit {
  outline: 1px solid var(--accent);
  outline-offset: -1px;
}
.detail-offers {
  row-gap: 14px;
  padding-top: 7px;
}
.detail-offer {
  position: relative;
  display: grid;
  gap: 6px;
  align-content: start;
  min-width: 0;
}
.detail-offer > p {
  font-size: var(--fs-13);
  line-height: 19px;
}
/* The favor rank straddles the cell's top edge. */
.detail-favor {
  position: absolute;
  top: 0;
  left: 50%;
  transform: translate(-50%, -50%);
  padding: 1px 8px;
  background: var(--ground);
  border: 1px solid var(--line);
  color: var(--muted);
  font-size: 11px;
  line-height: 14px;
  white-space: nowrap;
}

.detail-ranks {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 28px;
}
.detail-rank {
  display: grid;
  grid-template-columns: 50px minmax(0, 1fr);
  gap: 8px;
  padding: 7px 0;
  border-bottom: 1px solid var(--line);
  font-size: var(--fs-13);
  line-height: 19px;
}
.detail-rank > b {
  color: var(--accent);
  font: 400 10px / 19px var(--pixel-font);
  white-space: nowrap;
}
.detail-rank.effect-hit {
  background: var(--raised);
}
.detail-ranks.tiers {
  gap: 8px 28px;
}
.detail-ranks.tiers .detail-rank {
  grid-template-columns: 64px minmax(0, 1fr);
  padding: 0;
  border: 0;
}
.detail-ranks.tiers .detail-rank > b {
  font: 400 12px / 19px var(--text-font);
}
.detail-variants {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 16px;
}
.detail-variants div {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-13);
}
.detail-variants img {
  width: 24px;
  height: 24px;
  image-rendering: pixelated;
}

/* narrow: stats and text take the full width under the plate and name */
@container (max-width: 720px) {
  .detail-head.with-stats {
    grid-template-columns: auto minmax(0, 1fr);
    grid-template-areas:
      "plate titles"
      "plate stats"
      "plate found";
  }
  .detail-head.with-stats :deep(.creature-stats) {
    justify-self: start;
  }
  .detail-grid.three {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .detail-names {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@container (max-width: 480px) {
  .object-detail {
    gap: 16px;
  }
  .detail-head,
  .detail-head.with-stats {
    --plate: 64px;
    grid-template-columns: auto minmax(0, 1fr);
    grid-template-areas:
      "plate titles"
      "stats stats"
      "found found"
      "effect effect";
    gap: 10px 14px;
  }
  .detail-head :deep(.creature-stats) {
    grid-template-columns: repeat(5, minmax(0, 1fr));
    text-align: center;
  }
  .detail-titles {
    align-self: center;
  }
  .detail-titles h1 {
    font-size: 21px;
  }
  .detail-split {
    grid-template-columns: minmax(0, 1fr);
  }
  .detail-split > .detail-side {
    grid-column: 1;
    grid-row: auto;
    margin-top: 6px;
  }
  .detail-family.tiles {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px 16px;
  }
  .detail-family.tiles a {
    flex-direction: row;
    gap: 6px;
    padding: 0;
    background: none;
    font-size: var(--fs-13);
    font-weight: 400;
    text-align: left;
  }
  .detail-family.tiles a > span {
    white-space: nowrap;
  }
  .detail-family.tiles a[aria-current="page"] {
    outline: 0;
    font-weight: 700;
  }
  .detail-family.tiles :deep(.cell-plate) {
    width: 32px;
    height: 32px;
  }
  .detail-family.tiles :deep(.cell-plate > img) {
    width: 28px;
    height: 28px;
  }
  .detail-names,
  .detail-grid.two,
  .detail-ranks,
  .detail-variants {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .detail-grid.two,
  .detail-ranks,
  .detail-variants {
    grid-template-columns: minmax(0, 1fr);
  }
  .detail-grid.three {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
  }
  .detail-grid.three > * {
    padding: 10px 0;
    background: none;
    border-bottom: 1px solid var(--line);
  }
  .detail-offers {
    row-gap: 0;
    padding-top: 0;
  }
  .detail-grid.three > .detail-offer {
    padding-top: 16px;
  }
}
</style>
