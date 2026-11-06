<script setup lang="ts">
import { ref } from "vue";
import { useDropZone } from "@vueuse/core";
import { DRAG_TYPE } from "./dragging";

const props = withDefaults(
  defineProps<{
    /** Whether the item being placed fits here; null while nothing is being placed. */
    accepts?: boolean | null;
    /** What a drop here does, shown while a drag is held over the zone. */
    hint?: string | null;
  }>(),
  { accepts: null, hint: null },
);
const emit = defineEmits<{ drop: [] }>();
const zone = ref<HTMLElement | null>(null);
const { isOverDropZone } = useDropZone(zone, {
  checkValidity: (items) =>
    props.accepts !== false && [...items].some((item) => item.type === DRAG_TYPE),
  onDrop: () => emit("drop"),
});
</script>

<template>
  <div
    ref="zone"
    :class="{
      'drop-ready': isOverDropZone,
      'drop-valid': accepts === true,
      'drop-invalid': accepts === false,
      'has-hint': hint,
    }"
  >
    <slot />
    <span v-if="isOverDropZone && hint" class="drop-hint" aria-hidden="true">{{ hint }}</span>
  </div>
</template>

<style scoped>
.drop-valid {
  outline: 2px dashed var(--accent);
  outline-offset: 1px;
}
.drop-invalid {
  opacity: 0.4;
}
.drop-ready {
  background: var(--raised);
  outline: 1px solid var(--drop-line);
  outline-offset: -1px;
}
.has-hint {
  position: relative;
}
.drop-hint {
  position: absolute;
  top: 50%;
  left: 50%;
  z-index: 2;
  color: var(--text);
  font: 400 20px / 1 var(--pixel-font);
  text-shadow:
    2px 0 var(--ground),
    -2px 0 var(--ground),
    0 2px var(--ground),
    0 -2px var(--ground);
  text-transform: uppercase;
  white-space: nowrap;
  pointer-events: none;
  transform: translate(-50%, -50%);
  animation: drop-hint-rise 1.2s steps(12) infinite;
}
@keyframes drop-hint-rise {
  from {
    opacity: 1;
    transform: translate(-50%, -50%);
  }
  to {
    opacity: 0;
    transform: translate(-50%, calc(-50% - 24px));
  }
}
@media (prefers-reduced-motion: reduce) {
  .drop-hint {
    animation: none;
  }
}
</style>
