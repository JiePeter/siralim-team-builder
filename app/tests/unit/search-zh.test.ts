// @vitest-environment node
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { createPinia, setActivePinia } from "pinia";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { candidates } from "@/components/candidates";
import { catalog } from "@/data";
import { searchDocuments, textMatches } from "@/domain/discovery";
import { matchesText } from "@/domain/values";
import { discoveryPack, useSearchStore } from "@/stores/search";

// Runs against the Simplified Chinese pack written by `python -m kb.export`.
const pack = fileURLToPath(new URL("../../public/data/zh-CN/", import.meta.url));

vi.stubGlobal("fetch", async (url: string) => {
  const path = url.replace(/^\/data\//, "").replace(/\?.*$/, "");
  return new Response(await readFile(pack + path));
});

async function search(q: string, kind = "") {
  const store = useSearchStore();
  store.q = q;
  store.kind = kind;
  await store.run();
  return store;
}

async function scattered(q: string, kind = "") {
  const groups = textMatches(await discoveryPack(), q);
  return groups.filter((group) => !kind || group.kinds.has(kind)).length;
}

describe("Chinese search", () => {
  // The first search builds the index and parses card shards, which outlasts a test's timeout.
  beforeAll(async () => {
    setActivePinia(createPinia());
    await search("法力");
  }, 60_000);

  it("returns only the components holding a Han run unbroken within a field", async () => {
    const found = await search("法力");
    expect(found.total).toBeGreaterThan(0);
    expect(found.total).toBeLessThan(await scattered("法力"));

    const index = await discoveryPack();
    const documents = new Map(searchDocuments(index.pack).map((doc) => [doc.id, doc]));
    for (const item of found.items) {
      const doc = documents.get(index.canonical.get(item.id) ?? item.id)!;
      expect([doc.name, doc.members, doc.text, doc.locations].join("\n")).toContain("法力");
    }
  });

  it("falls back to scattered characters when nothing holds the run", async () => {
    expect((await search("攻击力")).total).toBe(await scattered("攻击力"));
  });

  it("falls back when the chosen type excludes everything holding the run", async () => {
    const wide = await scattered("法力", "spell");
    expect(wide).toBeGreaterThan(0);
    expect((await search("法力", "spell")).total).toBe(wide);
  });

  it("keeps words without Han independent of each other", async () => {
    const wide = await scattered("10 50", "trait");
    expect(wide).toBeGreaterThan(0);
    expect((await search("10 50", "trait")).total).toBe(wide);
  });

  it("matches list filters by unbroken Han runs and word prefixes", () => {
    expect(matchesText("法力值", "法力")).toBe(true);
    expect(matchesText("魔法能力", "法力")).toBe(false);
    expect(matchesText("法力 Fire Ball", "ba 法力 fi")).toBe(true);
    expect(matchesText("Fire Ball", "ba fi")).toBe(true);
  });

  it("falls back in a picker whose field accepts none of the phrase's components", async () => {
    const picked = await candidates("spells", "法力", await catalog());
    expect(picked.items.length).toBeGreaterThan(0);
  });
});
