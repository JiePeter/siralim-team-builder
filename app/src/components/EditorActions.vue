<script setup lang="ts">
import { inject } from "vue";
import { DIALOG_ACTIONS } from "./dialog";

defineProps<{ replace?: boolean; tray?: boolean }>();
const emit = defineEmits<{ replace: []; tray: [] }>();
const actions = inject(DIALOG_ACTIONS, null);
</script>

<template>
  <Teleport v-if="actions" defer :to="`#${actions}`">
    <button v-if="replace" type="button" class="labelled-key" @click="emit('replace')">
      <i class="icon icon-replace"></i>{{ $t("editors.keys.replace") }}
    </button>
    <button v-if="tray" type="button" class="labelled-key" @click="emit('tray')">
      <i class="icon icon-undo"></i>{{ $t("editors.keys.tray") }}
    </button>
  </Teleport>
</template>
