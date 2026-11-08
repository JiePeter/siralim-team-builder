<script setup lang="ts">
import { assetUrl } from "@/data";

defineProps<{ src: string }>();
</script>

<template>
  <img :src="assetUrl(src)" />
</template>
