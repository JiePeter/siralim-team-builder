import { computed, toRaw } from "vue";
import { createSharedComposable } from "@vueuse/core";
import { storeToRefs } from "pinia";
import type { SlotField } from "@/domain/assembly";
import { buildEffects } from "@/domain/effects";
import {
  avatarCheck,
  AVATAR_RACE,
  gemNotices,
  repeatedTraits,
  replacementNotices,
  slotTraits,
  unstackedTraits,
} from "@/domain/placement";
import type { EquipmentRef, Slot } from "@/domain/team";
import { t } from "@/i18n";
import { useTeamStore } from "@/stores/team";
import { BLEND, slotIndex } from "./assembly";
import { component } from "./components";

const NAMES_LISTED = 3;

/** Everything a slot holds besides its Primary. */
export const slotGear = (s: Slot): EquipmentRef[] =>
  [s.fusion, s.artifact, s.relic, ...(s.spells ?? []), ...(s.nether ?? [])].filter(
    (ref) => ref !== undefined,
  );

export const isVacant = (s: Slot) => !s.base && !slotGear(s).length;

/** The rule warnings for the team, as a list and per field. */
export const useBuildNotices = createSharedComposable(() => {
  const { team, index } = storeToRefs(useTeamStore());

  const avatars = computed(() =>
    index.value
      ? avatarCheck(index.value, team.value, (id) => component(id)?.attrs?.race_id === AVATAR_RACE)
      : null,
  );
  const unstacked = computed(() => (index.value ? unstackedTraits(index.value, team.value) : []));
  const traitName = (trait: string) => component(trait)?.name ?? t("build.aTrait");
  const nameList = (ids: string[]) => {
    const names = ids.map(traitName);
    const separator = t("build.nameSeparator");
    if (names.length <= NAMES_LISTED) return names.join(separator);
    return t("build.nameList", {
      names: names.slice(0, NAMES_LISTED).join(separator),
      count: names.length - NAMES_LISTED,
    });
  };
  const replaced = computed(() =>
    index.value ? replacementNotices(index.value, toRaw(team.value)) : [],
  );
  /** A fused creature takes its Fusion parent's class unless the team carries Blend. */
  const blended = computed(() => {
    const at = index.value;
    return (
      !!at && team.value.slots.some((s) => slotTraits(at, s).some(({ trait }) => trait === BLEND))
    );
  });

  /** Each notice with the slots it marks; a team-wide one marks none. */
  const notices = computed<{ text: string; slots: number[] }[]>(() => [
    ...(index.value
      ? buildEffects(index.value, toRaw(team.value), () => undefined).notices
      : []
    ).map((text) => ({ text, slots: [] })),
    ...unstacked.value.map(({ trait, slots }) => ({
      text: t("build.unstacked", { trait: traitName(trait), n: slotIndex(slots[0]!) }),
      slots: slots.slice(1),
    })),
    ...replaced.value.map(({ owner, listeners, certain }) => ({
      text: t(certain ? "build.replacedCertain" : "build.replacedPossible", {
        owner: traitName(owner),
        listeners: nameList(listeners),
      }),
      slots: [],
    })),
    ...team.value.slots.flatMap((s, i) =>
      !s.base && slotGear(s).length
        ? [{ text: t("build.noPrimary", { n: slotIndex(i) }), slots: [i] }]
        : [],
    ),
    ...(avatars.value?.notice ? [{ text: avatars.value.notice, slots: avatars.value.slots }] : []),
    ...(index.value
      ? gemNotices(
          team.value,
          (id) => component(id)?.attrs?.class,
          blended.value,
          index.value.rules.spell_gems,
        )
      : []
    ).map(({ slot, message }) => ({
      text: t("build.slotNotice", { n: slotIndex(slot), message }),
      slots: [slot],
    })),
  ]);
  const slotNotices = (i: number) => notices.value.filter((n) => n.slots.includes(i));
  const overAvatar = (i: number) => !!avatars.value?.notice && avatars.value.slots.includes(i);

  /** Each slot's Fusion and Artifact traits that repeat one the creature already has. */
  const repeats = computed(() =>
    index.value ? team.value.slots.map((s) => repeatedTraits(index.value!, s)) : [],
  );
  const repeatNotice = (trait: string) =>
    t("build.repeatNotice", { trait: component(trait)?.name ?? t("build.thisTrait") });
  function repeatWarning(at: number, field: SlotField) {
    const found = repeats.value[at]?.find((r) => r.field === field);
    if (found) return repeatNotice(found.trait);
    const trait =
      index.value &&
      slotTraits(index.value, team.value.slots[at]!).find((t) => t.field === field)?.trait;
    const shared = unstacked.value.find((u) => u.trait === trait && u.slots[0] !== at);
    return shared
      ? t("build.unstacked", { trait: traitName(shared.trait), n: slotIndex(shared.slots[0]!) })
      : null;
  }
  function fieldWarning(at: number, field: SlotField) {
    return field === "base" && overAvatar(at) ? avatars.value!.notice : repeatWarning(at, field);
  }

  return { blended, fieldWarning, notices, overAvatar, slotNotices };
});
