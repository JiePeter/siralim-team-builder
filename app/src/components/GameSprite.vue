<script setup lang="ts">
import { computed } from "vue";
import { assetUrl } from "@/data";
import { spriteOf, type Displayable } from "./presentation";

const props = defineProps<{
  data: Displayable | null | undefined;
  /** A Spell Gem's property count, which picks its sprite. */
  properties?: number;
}>();
const src = computed(() => spriteOf(props.data, props.properties));
</script>

<template>
  <img v-if="src" class="game-sprite" :src="assetUrl(src)" alt="" loading="lazy" />
</template>
