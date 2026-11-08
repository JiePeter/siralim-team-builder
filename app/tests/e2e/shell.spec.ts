import { expect, test } from "@playwright/test";

test("shell loads, opens an object page, and docks navigation on phones", async ({ page }) => {
  await page.goto("./");
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link", { name: "Search" })).toBeVisible();

  const manifest = await (await page.request.get("data/manifest.json")).json();
  const creatures = await (await page.request.get(`data/${manifest.cards.creature}`)).json();
  const id = Object.keys(creatures)[0]!;
  const path = manifest.objects[id] ?? `objects/${id.replace(/[^A-Za-z0-9_-]/g, ".")}.json`;
  const name = (await (await page.request.get(`data/${path}`)).json()).name;
  await page.goto(`./#/object/${id}`);
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  const sprite = page.locator(".detail-plate img").first();
  await expect
    .poll(() => sprite.evaluate((img: HTMLImageElement) => img.naturalWidth))
    .toBeGreaterThan(0);

  await page.setViewportSize({ width: 390, height: 844 });
  const box = await nav.boundingBox();
  expect(box!.y + box!.height).toBeCloseTo(844, 0);
  expect(box!.width).toBe(390);
});
