<script setup lang="ts">
import { inject } from "vue";
import { DIALOG_ACTIONS } from "./dialog";

defineProps<{ replace?: boolean; tray?: boolean }>();
const emit = defineEmits<{ replace: []; tray: [] }>();
const actions = inject(DIALOG_ACTIONS, null);
</script>

<template>
  <Teleport v-if="actions" defer :to="`#${actions}`">
    <button
      v-if="replace"
      type="button"
      class="icon-button"
      :aria-label="$t('editors.keys.replace')"
      :title="$t('editors.keys.replace')"
      @click="emit('replace')"
    >
      <i class="icon icon-replace"></i>
    </button>
    <button
      v-if="tray"
      type="button"
      class="icon-button"
      :aria-label="$t('editors.keys.tray')"
      :title="$t('editors.keys.tray')"
      @click="emit('tray')"
    >
      <i class="icon icon-undo"></i>
    </button>
  </Teleport>
</template>
