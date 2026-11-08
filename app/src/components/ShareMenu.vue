<script setup lang="ts">
import { ref, useId } from "vue";
import { storeToRefs } from "pinia";
import { useTeamStore } from "@/stores/team";
import { t } from "@/i18n";
import FloatingMenu from "./FloatingMenu.vue";
import { attempt, toast } from "./toast";

const store = useTeamStore();
const { team, trayCount } = storeToRefs(store);
const shareTray = ref(false);
const menu = useId();
const sharing = ref(false);

async function share() {
  const url = await store.shareUrl(shareTray.value && trayCount.value > 0);
  if (navigator.share) {
    await navigator.share({ title: team.value.name, url }).catch(() => {});
    return;
  }
  await navigator.clipboard.writeText(url);
  toast(t("build.linkCopied"));
}
</script>

<template>
  <button
    type="button"
    class="icon-button share-key"
    :aria-label="$t('build.shareLink')"
    :title="$t('build.shareLink')"
    :aria-haspopup="trayCount ? 'dialog' : undefined"
    :aria-expanded="trayCount ? sharing : undefined"
    :popovertarget="trayCount ? menu : undefined"
    @click="trayCount || attempt(share)"
  >
    <i class="icon icon-share"></i>
  </button>
  <FloatingMenu
    v-if="trayCount"
    :id="menu"
    v-slot="{ close }"
    v-model:open="sharing"
    role="dialog"
    :label="$t('build.shareLink')"
  >
    <label><input v-model="shareTray" type="checkbox" />{{ $t("build.includeTray") }}</label>
    <button
      type="button"
      class="primary"
      @click="
        close();
        attempt(share);
      "
    >
      {{ $t("build.share") }}
    </button>
  </FloatingMenu>
</template>

<style scoped>
.share-key {
  width: var(--field);
  min-width: var(--field);
  height: var(--field);
}
@media (max-width: 767px) {
  .share-key {
    grid-column: 4;
  }
}
</style>
