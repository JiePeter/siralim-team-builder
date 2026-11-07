import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { PLANNER_URL } from "@/domain/planner";
import { TeamError, itemId } from "@/domain/team";
import { useTeamStore } from "@/stores/team";

const pack = resolve(__dirname, "../../public/data") + "/";
vi.stubGlobal("fetch", async (url: string) => {
  try {
    return new Response(await readFile(pack + url.replace(/^\/data\//, "").replace(/\?.*$/, "")));
  } catch {
    return new Response(null, { status: 404 });
  }
});

// Team links players published with the planner's Compendium 2.0 data.
const lazyGotg =
  "b=faf5a1711bb21377076943f6_aa1b1b7f89e96151cbc99c92_________&a=ASABMFPMGWDHFAF&r=______";
const caliban =
  "b=14e969df461d942b5bd41fef0442960155f2b25c298daa18537aa0aa111c6d411c46a0782b351a04d0446da3829ab67d72f6bfbb2968&a=DEASOKWREHKHBMA&r=___ge_vn";

describe("Siralim Planner links", () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it.each([lazyGotg, caliban])("reads and writes the same link: %s", async (query) => {
    const store = useTeamStore();
    expect(await store.importPlannerLink(`https://example.test/planner/?${query}`)).toBe(0);
    expect(await store.plannerLink()).toBe(`${PLANNER_URL}?${query}`);
  });

  it("places a link's parts by creature, Artifact, Anointment and Relic", async () => {
    const store = useTeamStore();
    await store.importPlannerLink(`${PLANNER_URL}?${caliban}`);
    const [first] = store.team.slots;
    expect(itemId(first!.base)).toMatch(/^creature:/);
    expect(itemId(first!.fusion)).toMatch(/^creature:/);
    expect(itemId(first!.artifact)).toMatch(/^material:/);
    expect(store.team.character.anointments).toHaveLength(5);
    expect(itemId(store.team.slots[3]!.relic)).toMatch(/^relic:/);
    expect(store.team.slots[4]!.relic).toBeUndefined();
  });

  it("counts parts it has no place for and rejects anything else", async () => {
    const store = useTeamStore();
    expect(await store.importPlannerLink("?b=000000______&a=ZZZ")).toBe(2);
    await expect(store.importPlannerLink("https://example.test/")).rejects.toBeInstanceOf(
      TeamError,
    );
  });
});
