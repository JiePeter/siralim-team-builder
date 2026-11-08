<script setup lang="ts">
import { computed } from "vue";
import type { Route } from "@/data";
import ObjectLink from "./ObjectLink.vue";
import { routeView } from "./presentation";

const props = defineProps<{ route: Route }>();
const view = computed(() => routeView(props.route));
</script>

<template>
  <div v-if="view" class="route-row">
    <ObjectLink :item="{ id: route.location, name: view.title, image: route.location_image }">
      <span v-if="view.facts.length" class="route-facts">
        <span v-for="fact in view.facts" :key="fact" class="pill">{{ fact }}</span>
      </span>
    </ObjectLink>
  </div>
</template>
