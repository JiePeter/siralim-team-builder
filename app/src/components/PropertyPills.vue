<script setup lang="ts">
import type { Equipment } from "@/domain/team";
import { propertyLabel, useGemProperties } from "./assembly";

defineProps<{ item: Equipment }>();
const properties = useGemProperties();
</script>

<template>
  <span v-for="id in item.properties ?? []" :key="id" class="pill">{{
    propertyLabel(properties, item, id)
  }}</span>
</template>
