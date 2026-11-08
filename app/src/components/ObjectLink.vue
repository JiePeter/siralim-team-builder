<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";
import GameSprite from "./GameSprite.vue";
import { objectRoute, type Displayable, type Hit } from "./presentation";

const props = withDefaults(
  defineProps<{
    item: Displayable & { id: string; name: string; matched_rules?: unknown[] };
    hits?: Hit[];
    sprite?: boolean;
  }>(),
  { hits: undefined, sprite: true },
);
const to = computed(() =>
  objectRoute(props.item.id, props.hits ?? (props.item.matched_rules as Hit[] | undefined) ?? []),
);
</script>

<template>
  <RouterLink class="object-link" :to="to">
    <GameSprite v-if="sprite" :data="item" />
    <span class="object-link-text">
      <span class="object-link-name">{{ item.name }}</span>
      <slot />
    </span>
  </RouterLink>
</template>

<style scoped>
.object-link {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--text);
  font-weight: 700;
  text-decoration: none;
}
.object-link-text {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
}
.object-link-text :slotted(small) {
  color: var(--muted);
  font-size: var(--fs-12);
  font-weight: 400;
}
.object-link:hover .object-link-name {
  text-decoration: underline;
  text-decoration-color: var(--strong);
  text-underline-offset: 3px;
}
</style>
