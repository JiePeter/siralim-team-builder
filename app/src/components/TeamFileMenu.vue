<script setup lang="ts">
import { ref, useId } from "vue";
import { useFileDialog } from "@vueuse/core";
import { useTeamStore } from "@/stores/team";
import { t } from "@/i18n";
import FloatingMenu from "./FloatingMenu.vue";
import { useShowNether } from "./presentation";
import { attempt, toast } from "./toast";

const store = useTeamStore();
const showNether = useShowNether();
const menu = useId();
const open = ref(false);

async function copyPlannerLink() {
  await navigator.clipboard.writeText(await store.plannerLink());
  toast(t("build.linkCopied"));
}

async function importPlanner() {
  const text = prompt(t("build.plannerPrompt"));
  if (!text) return;
  const dropped = await store.importPlannerLink(text);
  if (dropped) toast(t("build.plannerDropped", { n: dropped }));
}

function exportTeam() {
  const link = document.createElement("a");
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(store.team, null, 2)], { type: "application/json" }),
  );
  link.href = url;
  link.download = "siralim-team.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const {
  open: chooseImport,
  onChange: onImportChosen,
  reset: resetImport,
} = useFileDialog({ accept: "application/json,.json", multiple: false });
onImportChosen(async (files) => {
  const file = files?.[0];
  if (!file) return;
  await attempt(async () => {
    if (file.size > 100000) throw new Error(t("build.fileTooLarge"));
    const imported: unknown = JSON.parse(await file.text());
    if (confirm(t("build.confirmImport", { name: store.team.name, file: file.name })))
      await store.replace(imported);
  });
  resetImport();
});
</script>

<template>
  <button
    type="button"
    class="icon-button more-key"
    :aria-label="$t('build.more')"
    :title="$t('build.more')"
    aria-haspopup="menu"
    :aria-expanded="open"
    :popovertarget="menu"
  >
    <i class="icon icon-more"></i>
  </button>
  <FloatingMenu :id="menu" v-slot="{ close }" v-model:open="open" :label="$t('build.more')">
    <button
      type="button"
      role="menuitemcheckbox"
      :aria-checked="showNether"
      @click="
        close();
        showNether = !showNether;
      "
    >
      <span>{{ $t("build.netherStones") }}</span
      ><i v-if="showNether" class="icon icon-check menu-mark"></i>
    </button>
    <hr />
    <button
      type="button"
      role="menuitem"
      @click="
        close();
        exportTeam();
      "
    >
      {{ $t("build.exportTeam") }}
    </button>
    <button
      type="button"
      role="menuitem"
      @click="
        close();
        chooseImport();
      "
    >
      {{ $t("build.importTeam") }}
    </button>
    <hr />
    <button
      type="button"
      role="menuitem"
      @click="
        close();
        attempt(copyPlannerLink);
      "
    >
      {{ $t("build.copyPlannerLink") }}
    </button>
    <button
      type="button"
      role="menuitem"
      @click="
        close();
        attempt(importPlanner);
      "
    >
      {{ $t("build.importPlannerLink") }}
    </button>
  </FloatingMenu>
</template>

<style scoped>
.more-key {
  width: var(--field);
  min-width: var(--field);
  height: var(--field);
}
@media (max-width: 767px) {
  .more-key {
    grid-column: 5;
  }
}
</style>
