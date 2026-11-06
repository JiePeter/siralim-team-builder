<script setup lang="ts">
import { inject } from "vue";
import { DIALOG_FOOTER } from "./dialog";

const footer = inject(DIALOG_FOOTER, null);
</script>

<template>
  <Teleport v-if="footer" defer :to="`#${footer}`"><slot /></Teleport>
  <slot v-else />
</template>
