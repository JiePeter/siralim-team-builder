<script setup lang="ts">
import { computed } from "vue";
import AssetImage from "./AssetImage.vue";
import { spriteOf, type Displayable } from "./presentation";

const props = defineProps<{
  data: Displayable | null | undefined;
  /** A Spell Gem's property count, which picks its sprite. */
  properties?: number;
}>();
const src = computed(() => spriteOf(props.data, props.properties));
</script>

<template>
  <AssetImage v-if="src" class="game-sprite" :src="src" alt="" loading="lazy" />
</template>
