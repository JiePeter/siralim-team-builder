<script setup lang="ts">
import { RouterLink } from "vue-router";
import AssetImage from "./AssetImage.vue";
import { objectRoute } from "./presentation";

defineProps<{ src?: string | null; label: string; id?: string | null }>();
</script>

<template>
  <RouterLink
    v-if="id"
    class="identity-icon"
    :to="objectRoute(id)"
    :aria-label="label"
    :data-tooltip="label"
  >
    <AssetImage v-if="src" :src="src" alt="" />
    <template v-else>{{ label }}</template>
  </RouterLink>
  <span
    v-else-if="src"
    class="identity-icon"
    tabindex="0"
    :aria-label="label"
    :data-tooltip="label"
  >
    <AssetImage :src="src" alt="" />
  </span>
  <span v-else>{{ label }}</span>
</template>

<style scoped>
.identity-icon {
  position: relative;
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
}
.identity-icon img {
  width: 16px;
  height: 16px;
  object-fit: contain;
  image-rendering: pixelated;
}
.identity-icon:hover::after,
.identity-icon:focus-visible::after {
  content: attr(data-tooltip);
  position: absolute;
  left: 0;
  top: calc(100% + 4px);
  z-index: 5;
  padding: 4px 8px;
  background: var(--raised);
  border: 1px solid var(--strong);
  color: var(--text);
  font-size: var(--fs-13);
  font-weight: 400;
  white-space: nowrap;
  box-shadow: var(--elevation);
}
</style>
