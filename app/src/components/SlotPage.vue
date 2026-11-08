<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import { I18nT } from "vue-i18n";
import { useSwipe } from "@vueuse/core";
import type { Position } from "@/domain/assembly";
import { PARTY_SIZE } from "@/domain/team";
import { t } from "@/i18n";
import { useTeamStore } from "@/stores/team";
import SlotFields from "./SlotFields.vue";
import { slotIndex } from "./assembly";
import { isVacant, useBuildNotices } from "./buildNotices";
import { usePhone } from "./presentation";
import { attempt } from "./toast";

const props = defineProps<{ atSlot: number }>();
const emit = defineEmits<{
  open: [target: Position];
  drop: [target: Position];
  copy: [at: Position];
  tray: [at: Position];
  move: [];
  close: [];
}>();

const SWIPE_COMMIT = 72;
const store = useTeamStore();
const router = useRouter();
const phone = usePhone();
const { slotNotices } = useBuildNotices();
const root = ref<HTMLElement | null>(null);
const pips = computed(() => store.team.slots.map((s, index) => ({ index, vacant: isVacant(s) })));
const vacant = computed(() => pips.value[props.atSlot]!.vacant);

/** The side the slot on screen came in from; empty when it was opened directly. */
const enteredFrom = ref<"left" | "right" | "">("");
const slotAfter = (delta: number) => (props.atSlot + delta + PARTY_SIZE) % PARTY_SIZE;
const {
  isSwiping,
  lengthX,
  direction: swipeDirection,
} = useSwipe(() => (phone.value ? root.value : null), {
  threshold: 16,
  onSwipeEnd(_, direction) {
    if (direction !== "left" && direction !== "right") return;
    if (Math.abs(lengthX.value) < SWIPE_COMMIT) return;
    const forward = direction === "left";
    enteredFrom.value = forward ? "right" : "left";
    router.replace({ query: { slot: String(slotAfter(forward ? 1 : -1) + 1), page: "slot" } });
  },
});
const swipeOffset = computed(() =>
  isSwiping.value && ["left", "right"].includes(swipeDirection.value) ? -lengthX.value * 0.6 : 0,
);

function clearSlot() {
  const i = props.atSlot;
  if (confirm(t("build.confirmClearSlot", { n: slotIndex(i) }))) attempt(() => store.clearSlot(i));
}
</script>

<template>
  <section
    ref="root"
    :class="['slot', 'open-slot', { 'phone-page': phone }]"
    :aria-label="$t('build.slot', { n: atSlot + 1 })"
  >
    <h2>
      <button
        v-if="phone"
        type="button"
        class="page-back"
        :aria-label="$t('build.backToTeam')"
        @click="emit('close')"
      >
        <i class="icon icon-left"></i>
      </button>
      <span v-if="phone" class="slot-name"
        ><span class="slot-number">{{ slotIndex(atSlot) }}</span></span
      >
      <I18nT v-else keypath="build.slot" tag="span" class="slot-name" scope="global">
        <template #n
          ><span class="slot-number">{{ slotIndex(atSlot) }}</span></template
        >
      </I18nT>
      <span v-if="phone" class="slot-pips" aria-hidden="true">
        <i
          v-for="pip in pips"
          :key="pip.index"
          :class="{ current: pip.index === atSlot, vacant: pip.vacant }"
        ></i>
      </span>
      <button v-if="phone && !vacant" type="button" class="labelled-key" @click="emit('move')">
        <i class="icon icon-move"></i>{{ $t("editors.keys.move") }}
      </button>
      <button
        v-if="!vacant"
        type="button"
        class="clear"
        :aria-label="$t('build.clearSlot')"
        :title="$t('build.clearSlot')"
        @click="clearSlot"
      >
        <i class="icon icon-trash"></i>
      </button>
    </h2>
    <div v-if="slotNotices(atSlot).length" class="build-notices slot-notices">
      <ul>
        <li v-for="notice in slotNotices(atSlot)" :key="notice.text">{{ notice.text }}</li>
      </ul>
    </div>
    <span v-if="swipeOffset" :class="['swipe-peek', swipeOffset < 0 ? 'right' : 'left']">
      {{ $t("build.slot", { n: slotIndex(slotAfter(swipeOffset < 0 ? 1 : -1)) }) }}
    </span>
    <div
      :key="atSlot"
      :class="['slot-body', enteredFrom && `from-${enteredFrom}`]"
      :style="swipeOffset ? { transform: `translateX(${swipeOffset}px)` } : undefined"
    >
      <SlotFields
        :at-slot="atSlot"
        @open="emit('open', $event)"
        @drop="emit('drop', $event)"
        @copy="emit('copy', $event)"
        @tray="emit('tray', $event)"
      />
    </div>
  </section>
</template>

<style scoped>
.slot-notices {
  border-width: 1px 0 0;
}
/* The page's other rows say which creature and Traits the slot holds. */
.slot-name {
  display: inline-flex;
  flex: 1;
  align-items: baseline;
  gap: var(--space-8);
  font-size: var(--fs-18);
  font-weight: 700;
  white-space: pre;
}
.slot-number {
  font: 400 18px / 1 var(--pixel-font);
}
.slot-pips {
  display: flex;
  gap: var(--space-4);
}
.slot-pips > i {
  width: 6px;
  height: 6px;
  background: var(--muted);
}
.slot-pips > .vacant {
  background: transparent;
  box-shadow: inset 0 0 0 1px var(--muted);
}
.slot-pips > .current {
  background: var(--accent);
  box-shadow: none;
}
.open-slot.phone-page {
  overflow-x: hidden;
  touch-action: pan-y;
}
.swipe-peek {
  position: fixed;
  top: 40%;
  z-index: 3;
  color: var(--muted);
  font: 400 16px / 1 var(--pixel-font);
}
.swipe-peek.left {
  left: var(--space-8);
}
.swipe-peek.right {
  right: var(--space-8);
}
.slot-body.from-left {
  animation: slot-from-left 160ms var(--ease-out);
}
.slot-body.from-right {
  animation: slot-from-right 160ms var(--ease-out);
}
@keyframes slot-from-left {
  from {
    opacity: 0;
    transform: translateX(-32px);
  }
}
@keyframes slot-from-right {
  from {
    opacity: 0;
    transform: translateX(32px);
  }
}
@media (max-width: 767px) {
  .slot-number {
    font-size: 24px;
  }
}
</style>
