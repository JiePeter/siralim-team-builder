<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";
import type { ObjectPage } from "@/data";
import ObjectLink from "./ObjectLink.vue";
import ObjectRegion from "./ObjectRegion.vue";
import ShopOffers from "./ShopOffers.vue";
import { objectRoute } from "./presentation";

const props = defineProps<{ data: ObjectPage; contextIds: string[] }>();

const content = computed(
  () =>
    props.data.god_contents ?? {
      realms: [],
      relics: [],
      shops: [],
      godspawn: [],
      ultimate_spells: [],
    },
);
const components = computed(() =>
  (
    [
      ["godspawn", "Godspawn"],
      ["ultimate_spells", "Ultimate Spell"],
    ] as const
  ).filter(([key]) => content.value[key]?.length),
);
</script>

<template>
  <div class="god-overview">
    <span v-for="fact in data.facts" :key="fact" class="god-title">{{ fact }}</span>
    <div v-if="content.realms?.length" class="god-realm" data-god-section="realm">
      <span>Realm</span>
      <ObjectLink v-for="realm in content.realms" :key="realm.id" :item="realm" />
    </div>
  </div>
  <div class="god-components">
    <section
      v-for="[key, title] in components"
      :key="key"
      class="god-component"
      :data-god-section="key"
    >
      <h2>{{ title }}</h2>
      <ObjectRegion
        v-for="item in content[key]"
        :key="item.id"
        :item="item"
        :sources="false"
        :identity="false"
        :context-ids="contextIds"
      />
    </section>
  </div>
  <section v-if="content.relics?.length" class="god-relic" data-god-section="relic">
    <h2>Relic</h2>
    <ObjectRegion
      v-for="item in content.relics"
      :key="item.id"
      :item="item"
      :sources="false"
      :identity="false"
      :context-ids="contextIds"
    />
  </section>
  <section
    v-for="shop in content.shops || []"
    :key="shop.id"
    class="god-shop"
    data-god-section="shop"
  >
    <div class="section-head">
      <h2>
        <RouterLink
          v-if="data.name && shop.name === `${data.name} God Shop`"
          class="link"
          :to="objectRoute(shop.id)"
          >Shop</RouterLink
        >
        <ObjectLink v-else :item="shop" />
      </h2>
      <small>{{ shop.offers.length }} {{ shop.offers.length === 1 ? "Item" : "Items" }}</small>
    </div>
    <ShopOffers :offers="shop.offers" :god-name="data.name" :context-ids="contextIds" />
  </section>
</template>
