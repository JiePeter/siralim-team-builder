<script setup lang="ts">
import { computed } from "vue";
import type { Route } from "@/data";
import ObjectLink from "./ObjectLink.vue";
import { routeView } from "./presentation";

const props = defineProps<{ route: Route; godName?: string | null }>();
const view = computed(() => routeView(props.route, { godName: props.godName ?? null }));
</script>

<template>
  <div v-if="view" class="route-row">
    <ObjectLink
      v-if="route.location"
      :item="{ id: route.location, name: view.title, image: route.location_image }"
    />
    <strong v-else>{{ view.title }}</strong>
    <div class="route-facts">
      <span v-for="fact in view.facts" :key="fact" class="pill">{{ fact }}</span>
    </div>
  </div>
</template>
