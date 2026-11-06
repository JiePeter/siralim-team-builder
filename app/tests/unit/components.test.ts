import { describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import type { SynergyItem } from "@/data";
import EffectText from "@/components/EffectText.vue";
import ObjectCell from "@/components/ObjectCell.vue";
import SynergyStrip from "@/components/SynergyStrip.vue";
import { candidates, cards, categories } from "@/components/synergy";

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
