// @vitest-environment node
import { describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import { decodeTeam, encodeTeam } from "@/domain/share";
import { newTeam } from "@/domain/team";
import { openShareLinks } from "@/shareLinks";

/** Every slot filled: creature, fusion, configured Artifact, three configured gems and a Relic. */
function sharedTeam() {
  const item = (id: string, extra = {}) => ({ uid: "", id, properties: [], ...extra });
  const team = newTeam();
  team.name = "Shared Team";
  team.slots = team.slots.map((_, i) => ({
    base: item(`creature:${100 + i}`),
    fusion: item(`creature:${1200 + i}`),
    artifact: item(`material:${1000 + i}`, {
      artifact: {
        type: "Sword",
        stats: [`artifact_property:${50 + i}`, "artifact_property:47", "artifact_property:48"],
        tricks: [`artifact_property:${10 + i}`, `artifact_property:${30 + i}`],
        spell: `spell:${300 + i}`,
      },
    }),
    spells: [0, 1, 2].map((gem) =>
      item(`spell:${400 + i * 3 + gem}`, {
        properties: [`enchantment:${gem}`, `enchantment:${gem + 7}`],
        property_variants: { [`enchantment:${gem}`]: 19 },
      }),
    ),
    relic: item(`relic:${i}`, { rank: 100 }),
    ...(i === 0 ? { nether: [item("trait:1953"), item("trait:899")] } : {}),
  }));
  team.inventory = [item("trait:1953", { shown: "creature:1242" })];
  team.character = {
    specialization: "spec:17",
    perks: { "perk:321": 5, "perk:407": 0 },
    anointments: ["perk:0", "perk:1"],
    ascended: true,
    all_ascended: false,
  };
  return team;
}

const withoutUids = (team: unknown) =>
  JSON.parse(JSON.stringify(team, (key, value) => (key === "uid" ? undefined : value)));

describe("share links", () => {
  it("round-trip a full team through a short URL-safe code", async () => {
    const code = await encodeTeam(sharedTeam());
    expect(code).toMatch(/^[A-Za-z0-9_-]+$/);
    expect(code.length).toBeLessThan(300);
    const decoded = await decodeTeam(code);
    expect(withoutUids(decoded)).toEqual(withoutUids(sharedTeam()));
    expect(new Set(decoded.slots.map((s) => s.base && (s.base as { uid: string }).uid)).size).toBe(
      6,
    );
  });

  it("round-trip an empty team, a blank Artifact and a Chinese note", async () => {
    const team = newTeam();
    team.notes = "这是一段备注".repeat(20);
    team.slots[2] = { artifact: { uid: "", id: "artifact:0", properties: [] } };
    const decoded = await decodeTeam(await encodeTeam(team));
    expect(withoutUids(decoded)).toEqual(withoutUids(team));
    expect((await encodeTeam(newTeam())).length).toBeLessThan(12);
  });

  it("open a team from a link followed in a running app, and only from a link", async () => {
    const page = { template: "<div />" };
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/search", component: page },
        { path: "/build", component: page },
        { path: "/:unknown(.*)*", redirect: "/search" },
      ],
    });
    const receive = vi.fn();
    openShareLinks(router, receive);
    await router.push("/search");
    await router.push("/object/creature:1242");
    expect(receive).not.toHaveBeenCalled();
    await router.push("/team=abc-_1");
    expect(receive).toHaveBeenCalledExactlyOnceWith("abc-_1");
    expect(router.currentRoute.value.path).toBe("/build");
  });
});
