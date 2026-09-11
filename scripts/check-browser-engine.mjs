import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
await mkdir("test-results/engine", { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1500, height: 1100 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => {
  if (m.type() === "error") errors.push(m.text());
});
await page.goto("http://127.0.0.1:4173/#engine");
try {
  await page.waitForSelector(".catan-board", { timeout: 60000 });
} catch (e) {
  console.log(await page.locator("#engine-status").innerText());
  throw e;
}
console.log(await page.locator("#engine-status").innerText());
await page.screenshot({
  path: "test-results/engine/board-desktop.png",
  fullPage: true,
});
await page.getByRole("button", { name: "Run 50 moves", exact: true }).click();
await page.waitForFunction(
  () =>
    document
      .querySelector("#engine-status")
      .textContent.includes("50 moves recorded"),
  { timeout: 30000 },
);
console.log(await page.locator("#engine-status").innerText());
console.log("Errors:", errors);
await page.screenshot({
  path: "test-results/engine/board-progress.png",
  fullPage: true,
});
await page.setViewportSize({ width: 390, height: 844 });
await page.screenshot({
  path: "test-results/engine/board-mobile.png",
  fullPage: true,
});
await browser.close();
