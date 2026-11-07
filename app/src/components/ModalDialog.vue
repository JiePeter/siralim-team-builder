<script setup lang="ts">
import { onMounted, provide, ref, useId, watch } from "vue";
import { useRoute } from "vue-router";
import { t } from "@/i18n";
import { DIALOG_ACTIONS, DIALOG_FOOTER } from "./dialog";

const open = defineModel<boolean>("open", { required: true });
const props = withDefaults(
  defineProps<{
    title: string;
    drawer?: boolean;
    closeLabel?: string;
    /** A short list: a bottom sheet on phones. */
    sheet?: boolean;
    /** The owner opens and closes the dialog with the route. */
    routed?: boolean;
  }>(),
  { drawer: false, closeLabel: t("editors.close"), sheet: false, routed: false },
);
const dialog = ref<HTMLDialogElement | null>(null);
const foot = ref<HTMLElement | null>(null);
const route = useRoute();
const footer = `dialog-foot-${useId()}`;
provide(DIALOG_FOOTER, footer);
const actions = `dialog-actions-${useId()}`;
provide(DIALOG_ACTIONS, actions);

function sync(value: boolean) {
  const element = dialog.value;
  if (!element) return;
  if (value && !element.open) element.showModal();
  if (!value && element.open) element.close();
}

watch(open, sync, { flush: "post" });
watch(
  () => route.fullPath,
  () => {
    if (!props.routed) open.value = false;
  },
);
onMounted(() => sync(open.value));

/** A click on the dialog element itself is on the backdrop. A pending Apply keeps the dialog open. */
function backdropClick(event: MouseEvent) {
  if (event.target === dialog.value && !foot.value?.childElementCount) open.value = false;
}
</script>

<template>
  <dialog
    ref="dialog"
    :class="[drawer ? 'drawer' : 'choice-dialog', { sheet }]"
    :aria-label="title"
    @close="open = false"
    @click="backdropClick"
  >
    <div class="section-head dialog-head">
      <h2>{{ title }}</h2>
      <div :id="actions" class="dialog-actions"></div>
      <button type="button" class="icon-button" :aria-label="closeLabel" @click="open = false">
        <i class="icon icon-close"></i>
      </button>
    </div>
    <div class="dialog-body"><slot v-if="open" /></div>
    <div :id="footer" ref="foot" class="dialog-foot"></div>
  </dialog>
</template>

<style scoped>
dialog {
  max-width: calc(100vw - 32px);
  padding: 0;
  background: var(--cell);
  color: var(--text);
  border: 1px solid var(--strong);
  border-radius: 0;
  box-shadow: var(--elevation);
}
dialog::backdrop {
  background: var(--backdrop);
}
dialog[open] {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.dialog-head {
  flex: none;
  min-height: 56px;
  padding: 8px 8px 8px 16px;
  background: var(--cell);
}
.dialog-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}
.dialog-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
.drawer .dialog-body {
  display: flex;
  flex-direction: column;
}
.drawer .dialog-body > :deep(*) {
  flex: 1;
}
.dialog-foot {
  flex: none;
}
.dialog-foot:not(:empty) {
  padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
}
.dialog-foot :deep(.primary) {
  width: 100%;
  min-height: var(--row);
}
.dialog-head h2 {
  min-width: 0;
  overflow-wrap: anywhere;
}
.drawer {
  position: fixed;
  inset: 0 0 0 auto;
  width: min(440px, 100vw);
  max-width: 100vw;
  height: 100dvh;
  max-height: 100dvh;
  margin: 0;
  border-width: 0 0 0 1px;
}
.drawer[open] {
  animation: drawer-in 0.22s var(--ease-out);
}
.choice-dialog {
  width: min(680px, calc(100vw - 32px));
  max-height: 80dvh;
}
@keyframes drawer-in {
  from {
    transform: translateX(100%);
  }
  to {
    transform: none;
  }
}
@keyframes sheet-in {
  from {
    transform: translateY(100%);
  }
  to {
    transform: none;
  }
}
@media (max-width: 767px) {
  .choice-dialog,
  .drawer {
    inset: 0;
    width: 100%;
    max-width: 100%;
    height: 100dvh;
    max-height: 100dvh;
    margin: 0;
    border-width: 0;
  }
  .sheet {
    inset: auto 0 0 0;
    height: auto;
    max-height: 60dvh;
    border-width: 1px 0 0;
  }
  .choice-dialog[open],
  .drawer[open] {
    animation: sheet-in 0.24s var(--ease-out);
  }
}
</style>
