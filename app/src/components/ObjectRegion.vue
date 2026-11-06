<script setup lang="ts">
import type { ObjectSummary as Summary } from "@/data";
import IdentityLine from "./IdentityLine.vue";
import ObjectLink from "./ObjectLink.vue";
import ObjectSummary from "./ObjectSummary.vue";
import type { Hit } from "./presentation";

withDefaults(
  defineProps<{
    item: Partial<Summary> & Pick<Summary, "id" | "kind" | "name"> & { matched_rules?: Hit[] };
    omit?: string[];
    /** Defaults to showing sources for creatures and materials. */
    sources?: boolean | null;
    identity?: boolean;
    omitIdentity?: string[];
    classIcon?: boolean;
    matchedOnly?: boolean;
    contextIds?: string[];
  }>(),
  {
    omit: () => [],
    sources: null,
    identity: true,
    omitIdentity: () => [],
    classIcon: true,
    matchedOnly: false,
    contextIds: () => [],
  },
);
</script>

<template>
  <article class="reference-row">
    <IdentityLine :data="item" :identity="identity" :omit="omitIdentity">
      <ObjectLink :item="item" />
    </IdentityLine>
    <ObjectSummary
      :data="item"
      :omit="omit"
      :sources="sources ?? ['creature', 'material'].includes(item.kind)"
      :class-icon="classIcon"
      :matched-only="matchedOnly"
      :context-ids="contextIds"
    />
  </article>
</template>
