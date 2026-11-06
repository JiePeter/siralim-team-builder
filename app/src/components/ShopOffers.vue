<script setup lang="ts">
import type { Offer } from "@/data";
import ObjectLink from "./ObjectLink.vue";
import ObjectSummary from "./ObjectSummary.vue";
import { routeView } from "./presentation";

const props = withDefaults(
  defineProps<{ offers: Offer[]; godName?: string | null; contextIds?: string[] }>(),
  { godName: null, contextIds: () => [] },
);

function facts(offer: Offer): string {
  return (
    routeView(
      {
        method: "purchase",
        requirements: { ...offer.requirements, ...offer.cost },
        via: offer.via,
      },
      { godName: props.godName },
    )?.facts.join(" · ") ?? ""
  );
}
</script>

<template>
  <div class="shop-products">
    <article v-for="offer in offers" :key="offer.id" class="shop-offer">
      <div class="shop-offer-heading">
        <ObjectLink :item="offer.item" />
        <small>{{ facts(offer) }}</small>
      </div>
      <ObjectSummary :data="offer.item" :context-ids="contextIds" />
    </article>
  </div>
</template>
