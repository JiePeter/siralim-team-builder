<script setup lang="ts">
import { ref, useId } from "vue";
import { useTeamStore } from "@/stores/team";
import { t } from "@/i18n";
import FloatingMenu from "./FloatingMenu.vue";

const store = useTeamStore();
const menu = useId();
const open = ref(false);

function removeTeam() {
  if (confirm(t("build.confirmDeleteTeam", { name: store.team.name }))) store.deleteTeam();
}
</script>

<template>
  <button
    type="button"
    class="icon-button teams-key"
    :aria-label="$t('build.teams')"
    :title="$t('build.teams')"
    aria-haspopup="menu"
    :aria-expanded="open"
    :popovertarget="menu"
  >
    <i class="icon icon-down"></i>
  </button>
  <FloatingMenu :id="menu" v-slot="{ close }" v-model:open="open" :label="$t('build.teams')">
    <button
      v-for="(name, i) in store.teams"
      :key="i"
      type="button"
      role="menuitemradio"
      :aria-checked="i === store.activeTeam"
      @click="
        close();
        store.openTeam(i);
      "
    >
      <span>{{ name }}</span
      ><i v-if="i === store.activeTeam" class="icon icon-check menu-mark"></i>
    </button>
    <hr />
    <button
      type="button"
      role="menuitem"
      @click="
        close();
        store.createTeam();
      "
    >
      <i class="icon icon-plus"></i>{{ $t("build.newTeam") }}
    </button>
    <button
      type="button"
      role="menuitem"
      @click="
        close();
        removeTeam();
      "
    >
      <i class="icon icon-trash"></i>{{ $t("build.deleteTeam") }}
    </button>
  </FloatingMenu>
</template>

<style scoped>
.teams-key {
  --key-line: transparent;
}
.teams-key:not(:hover, :active, [aria-expanded="true"]) {
  background-color: transparent;
}
</style>
