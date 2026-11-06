<script setup lang="ts">
import { computed } from "vue";
import IdentityIcon from "./IdentityIcon.vue";
import type { Displayable } from "./presentation";

const props = withDefaults(
  defineProps<{
    data: Displayable;
    /** Show the class and race icons. */
    identity?: boolean;
    omit?: string[];
    title?: boolean;
  }>(),
  { identity: true, omit: () => [], title: false },
);

const classification = computed(() => (props.identity ? props.data.classification?.[0] : null));
const attrs = computed(() => props.data.attrs ?? {});
</script>

<template>
  <div :class="['entity-identity', { 'entity-identity-title': title }]">
    <slot />
    <div v-if="classification" class="identity-icons">
      <IdentityIcon
        v-if="!omit.includes('class')"
        :id="attrs.class_id"
        :src="attrs.class_icon"
        :label="classification.class ?? ''"
      />
      <IdentityIcon
        v-if="!omit.includes('race')"
        :id="attrs.race_id"
        :src="attrs.race_icon"
        :label="classification.race ?? ''"
      />
    </div>
    <slot name="meta" />
  </div>
</template>

<style scoped>
.entity-identity {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
  min-width: 0;
}
.identity-icons {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin: 0;
}
.entity-identity-title :deep(h1) {
  display: flex;
  align-items: center;
  gap: 20px;
  min-width: 0;
  overflow-wrap: anywhere;
}
.entity-identity-title :deep(.identity-icon img) {
  width: 32px;
  height: 32px;
}
@media (max-width: 767px) {
  .entity-identity-title :deep(h1) {
    gap: 16px;
  }
}
</style>
