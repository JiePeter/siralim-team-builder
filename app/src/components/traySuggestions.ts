import { computed, ref, shallowRef, watch } from "vue";
import { storeToRefs } from "pinia";
import { synergies } from "@/data";
import { whereIs } from "@/domain/placement";
import { useTeamStore } from "@/stores/team";
import { shownAs } from "./assembly";
import { loadComponent } from "./components";
import { suggestions, type Seed } from "./fill";
import { useCatalog } from "./selection";
import { intentOf, useEntity } from "./tray";

/** The Synergies of what the tray holds, ranked into suggestions for what the team lacks. */
export function useTraySuggestions() {
  const { team, index } = storeToRefs(useTeamStore());
  const catalog = useCatalog();
  const entity = useEntity();

  const phase = ref<"loading" | "ready" | "failed">("loading");
  const seeds = shallowRef<Seed[]>([]);
  /** One entry per component in the tray, however many copies it holds. */
  const trayIds = computed(() => [...new Set(team.value.inventory.map((item) => item.id))]);

  let request = 0;
  watch(
    [trayIds, index],
    async ([ids]) => {
      const current = ++request;
      phase.value = "loading";
      try {
        const loaded = await Promise.all(
          ids.map(async (id) => {
            const item = team.value.inventory.find((i) => i.id === id)!;
            const [page, own, found] = await Promise.all([
              loadComponent(shownAs(index.value, item)),
              loadComponent(id),
              synergies(id),
            ]);
            return { id, name: page.name, file: own.synergies, items: found?.items ?? [] };
          }),
        );
        if (current !== request) return;
        const files = new Set<string>();
        seeds.value = loaded.filter((seed) => {
          if (!seed.file || files.has(seed.file)) return false;
          files.add(seed.file);
          return true;
        });
        phase.value = "ready";
      } catch {
        if (current === request) phase.value = "failed";
      }
    },
    { immediate: true },
  );

  const ranked = computed(
    () =>
      new Map(
        suggestions(seeds.value, (id) => {
          const intent = intentOf({ id, kind: id.split(":")[0] }, catalog.value, team.value);
          const where = whereIs(team.value, intent.id, entity);
          return !!intent.ownBase || where.tray.length + where.placed.length > 0;
        }).map((suggestion, position) => [
          suggestion.id,
          { ...suggestion, position, owners: suggestion.links.map((link) => link.seed.name) },
        ]),
      ),
  );

  return { trayIds, phase, seeds, ranked };
}
