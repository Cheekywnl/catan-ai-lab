import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
const destination = resolve(process.argv[2] || "test-results/review");
await mkdir(destination, { recursive: true });
const browser = await chromium.launch();
for (const [name, width, height, route] of [
  ["overview-desktop", 1440, 1080, "overview"],
  ["belief-desktop", 1440, 1080, "belief"],
  ["reader-desktop", 1440, 1080, "research/3"],
  ["overview-mobile", 390, 844, "overview"],
  ["belief-mobile", 390, 844, "belief"],
]) {
  const page = await browser.newPage({
    viewport: { width, height },
    deviceScaleFactor: 1,
  });
  await page.goto("http://127.0.0.1:4173/#" + route);
  await page.waitForFunction(
    () => document.querySelector("main h1") && document.title.includes("·"),
  );
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: resolve(destination, name + ".png"),
    fullPage: true,
  });
  await page.close();
}
await browser.close();
process.stdout.write(`Saved five review screenshots in ${destination}\n`);
