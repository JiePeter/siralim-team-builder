import { describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter } from "vue-router";
import type { GemProperty, SynergyItem } from "@/data";
import EffectText from "@/components/EffectText.vue";
import GemEditor from "@/components/GemEditor.vue";
import ObjectCell from "@/components/ObjectCell.vue";
import SynergyStrip from "@/components/SynergyStrip.vue";
import { routeView } from "@/components/presentation";
import { candidates, cards, categories } from "@/components/synergy";
import { useTeamStore } from "@/stores/team";

vi.mock("@/data", async (original) => ({
  ...(await original<typeof import("@/data")>()),
  synergies: vi.fn(async () => null),
}));

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: "/object/:id", name: "object", component: { template: "<div />" } }],
});

function path(id: string, kind: string, relation: string): SynergyItem {
  return {
    id,
    kind,
    name: id,
    relation,
    strength: "supported",
    shared_constraints: [],
    witness: {},
    target_rule: {
      reference: id,
      rank: null,
      conditions: [],
      segments: [],
      text: "",
    },
  };
}

describe("ObjectCell", () => {
  it("marks the selected cell and falls back to the kind icon without a sprite", () => {
    const cell = mount(ObjectCell, {
      props: { data: { kind: "relic" }, selected: true },
      slots: { label: "Relic" },
    });
    expect(cell.classes()).toContain("selected");
    expect(cell.find(".kind-plate img").attributes("src")).toMatch(/category\/relic\.png$/);
  });
});

describe("EffectText", () => {
  it("does not link a reference back to an object already in context", async () => {
    const text = mount(EffectText, {
      props: {
        segments: [
          { text: "Casts " },
          { text: "Seduction", id: "spell:a", kind: "spell" },
          { text: " and " },
          { text: "Weak", id: "condition:b", kind: "condition" },
        ],
        contextIds: ["spell:a"],
      },
      global: { plugins: [router] },
    });
    expect(text.find("strong.inline-ref-current").text()).toBe("Seduction");
    expect(text.findAll("button.inline-ref").map((b) => b.text())).toEqual(["Weak"]);
  });
});

describe("routeView", () => {
  it("shows a God's own Emblems without its name, whatever language prices them", () => {
    const route = { method: "purchase", requirements: { cost: 10, currency: "苏拉斯莉徽章" } };
    expect(routeView(route, { godName: "苏拉斯莉" })?.facts).toEqual(["10 Emblems"]);
    expect(routeView(route)?.facts).toEqual(["10 苏拉斯莉徽章"]);
  });
});

describe("GemEditor", () => {
  const property = (id: string, name: string, variants: GemProperty["variants"]): GemProperty => ({
    id,
    name,
    game_property_ids: variants.map((v) => v.id),
    variants,
    image: "",
    routes: [],
  });

  function editor(properties: GemProperty[]) {
    setActivePinia(createPinia());
    useTeamStore().index = {
      rules: { spell_gems: { properties: 3 }, potency_sources: [19, 21] },
      catalog: { class_icons: { Chaos: "/chaos.png", Death: "/death.png" } },
    } as never;
    return mount(GemEditor, { props: { item: { id: "spell:1" } as never, properties } });
  }

  it("keeps one potency source, however the properties are named", async () => {
    const gem = editor([
      property("enchantment:16", "效能基于攻击", [{ id: 19, label: "x%效能基于攻击" }]),
      property("enchantment:19", "效能基于防御", [{ id: 21, label: "x%效能基于防御" }]),
    ]);
    const [attack, defense] = gem.findAll("button.gem-option");
    await attack!.trigger("click");
    await defense!.trigger("click");
    expect(gem.emitted("apply")!.at(-1)![0]).toEqual(["enchantment:19"]);
  });

  it("tells variants apart in a language without spaces and finds their class icons", async () => {
    const gem = editor([
      property("enchantment:17", "系别转换", [
        { id: 10, label: "系别转换：混乱", class: "Chaos" },
        { id: 11, label: "系别转换：死亡", class: "Death" },
      ]),
      property("enchantment:7", "行动后施放几率", [
        { id: 24, label: "x%攻击后施放几率" },
        { id: 25, label: "x%防御后施放几率" },
      ]),
    ]);
    for (const option of gem.findAll("button.gem-option")) await option.trigger("click");
    const [classes, casts] = gem.findAll(".gem-variants");
    expect(classes!.findAll("button").map((b) => b.text())).toEqual(["Chaos", "Death"]);
    expect(classes!.find("img").attributes("src")).toMatch(/chaos\.png$/);
    expect(casts!.findAll("button").map((b) => b.text())).toEqual(["攻击", "防御"]);
  });
});

describe("Synergies", () => {
  it("offers only the relationships present within the chosen type", () => {
    const items = candidates([
      path("trait:a", "trait", "Event chain"),
      path("relic:b", "relic", "Amplification"),
    ]);
    const trait = categories(items, "trait", "Amplification");
    expect(trait.kinds.map((g) => g.value)).toEqual(["trait", "relic"]);
    expect(trait.mechanisms.map((g) => g.value)).toEqual(["", "Event chain"]);
    expect(trait.mechanism).toBe("");
    expect(categories(items, "relic", "Event chain").mechanism).toBe("");
    expect(categories(items, "relic", "Amplification").mechanism).toBe("Amplification");
  });

  it("lists unconditional connections before conditional ones", () => {
    const conditional = { ...path("trait:a", "trait", "Event chain"), strength: "conditional" };
    const items = candidates([conditional, path("trait:b", "trait", "Event chain")]);
    expect(cards(items, "trait", "Event chain").map((c) => c.id)).toEqual(["trait:b", "trait:a"]);
  });

  it("shows the empty state when the owner has no synergies", async () => {
    const strip = mount(SynergyStrip, {
      props: { owner: "trait:x", seed: "trait:x" },
      global: { plugins: [router] },
    });
    await strip.get("button").trigger("click");
    await flushPromises();
    expect(strip.get(".pairing-cards").attributes("data-empty")).toBe("true");
    expect(strip.text()).toContain("No synergies found");
  });
});
