import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFile } from "node:fs/promises";

test.setTimeout(90000);
async function ready(page) {
  await page.goto("/#engine");
  await expect(page.locator(".catan-board")).toBeVisible({ timeout: 60000 });
  await expect(page.locator("#engine-root")).toHaveAttribute(
    "aria-busy",
    "false",
  );
}

test("the live engine places, searches, undoes and runs a game to completion", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const outside = [];
  page.on("request", (r) => {
    if (
      !r.url().startsWith("http://127.0.0.1") &&
      !r.url().startsWith("blob:") &&
      !r.url().startsWith("data:")
    )
      outside.push(r.url());
  });
  await ready(page);
  await expect(page.locator("#bot-policy")).toHaveValue("tactical");
  await expect(page.locator("#engine-status")).toContainText(
    "0 moves recorded",
  );
  await expect(page.locator("#legal-moves option")).toHaveCount(54);
  await page
    .getByRole("button", { name: "Compare opening futures", exact: true })
    .click();
  await expect(page.locator(".draft-choice")).toHaveCount(5, {
    timeout: 30000,
  });
  await page.locator(".draft-choice").first().click();
  await page
    .getByRole("button", { name: "Play selected move", exact: true })
    .click();
  await expect(page.locator("#engine-status")).toContainText(
    "1 moves recorded",
  );
  await expect(page.locator(".board-topline strong")).toHaveText(
    "Choose its road",
  );
  await page.getByRole("button", { name: "Undo move", exact: true }).click();
  await expect(page.locator("#engine-status")).toContainText(
    "0 moves recorded",
  );
  await page
    .getByRole("button", { name: "Run to a winner", exact: true })
    .click();
  await expect(page.locator(".board-topline strong")).toContainText("wins!", {
    timeout: 60000,
  });
  await expect(
    page.getByRole("button", { name: "Play selected move", exact: true }),
  ).toBeDisabled();
  expect(errors).toEqual([]);
  expect(outside).toEqual([]);
});

test("native Python replays import identically in browser Python; bad replays are atomic", async ({
  page,
}) => {
  await ready(page);
  const fixture = JSON.parse(
    await readFile(
      new URL("../fixtures/native-replay.json", import.meta.url),
      "utf8",
    ),
  );
  await page.getByLabel("Import replay file").setInputFiles({
    name: "native.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(fixture)),
  });
  await expect(page.locator("#engine-status")).toContainText(
    "200 moves recorded",
    { timeout: 30000 },
  );
  const downloadPromise = page.waitForEvent("download");
  await expect(page.locator(".legacy-rules")).toContainText(
    "Historical replay",
  );
  await page
    .getByRole("button", { name: "Export replay", exact: false })
    .click();
  const file = await downloadPromise;
  const exported = JSON.parse(await readFile(await file.path(), "utf8"));
  expect(exported).toEqual(fixture);
  const before = await page.locator(".board-topline").innerText();
  await page.getByLabel("Import replay file").setInputFiles({
    name: "bad.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify({ ...fixture, checksum: "bad" })),
  });
  await expect(page.locator("#engine-status")).toContainText(
    "checksum mismatch",
    { timeout: 30000 },
  );
  expect(await page.locator(".board-topline").innerText()).toBe(before);
  await page.getByLabel("View as", { exact: true }).selectOption("BLUE");
  await expect(page.locator(".hand-panel")).toContainText("BLUE");
  await page
    .getByRole("button", { name: "Estimate win chances", exact: true })
    .click();
  await expect(page.locator(".forecast-row")).toHaveCount(4, {
    timeout: 60000,
  });
  await expect(page.locator(".forecast-result")).toContainText("12/12");
  await expect(page.locator(".forecast-result")).toContainText(
    "95% sampling interval",
  );
  await expect(page.locator(".forecast-result")).toContainText(
    "model-based forecasts",
  );
});

test("solver exposes opening order, production and general decision analysis", async ({
  page,
}) => {
  await ready(page);
  await expect(page.locator(".draft-sequence .current-pick")).toHaveText(
    "1. Red",
  );
  await expect(page.locator(".opening-audit")).toContainText(
    "6 rival settlement picks",
  );
  await expect(page.locator(".resource-projection")).toContainText(
    "cards / 36 rolls",
  );
  await page
    .getByRole("button", { name: "Analyze this decision", exact: true })
    .click();
  await expect(page.locator(".search-choice")).toHaveCount(6, {
    timeout: 60000,
  });
  await expect(page.locator("#plan-results")).toContainText(
    "not calibrated win probabilities",
  );
  await page.locator(".search-choice").first().click();
  await page
    .getByRole("button", { name: "Play selected move", exact: true })
    .click();
  await expect(page.locator("#engine-status")).toContainText(
    "1 moves recorded",
  );
  await expect(page.locator(".move-recommendations")).toContainText("roads");
  await page.getByLabel("Bot policy", { exact: true }).selectOption("baseline");
  await expect(page.locator("#bot-policy")).toHaveValue("baseline");
});

test("engine controls and populated board remain accessible and fit small screens", async ({
  page,
}, testInfo) => {
  await ready(page);
  const audit = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    audit.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        summary: n.failureSummary,
      })),
    })),
  ).toEqual([]);
  if (testInfo.project.name === "mobile")
    await page.setViewportSize({ width: 320, height: 850 });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(await page.evaluate(() => innerWidth + 1));
});

test("public completed turns constrain development cards after replay import", async ({
  page,
}) => {
  await ready(page);
  const data = JSON.parse(
    await readFile(
      new URL("../fixtures/development-history-repro.json", import.meta.url),
      "utf8",
    ),
  );
  await page.getByLabel("Import replay file").setInputFiles({
    name: "history.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(data.replay)),
  });
  await expect(page.locator("#engine-status")).toContainText(
    "439 moves recorded",
    { timeout: 30000 },
  );
  await page.getByLabel("View as", { exact: true }).selectOption(data.viewer);
  await page.locator(".development-model summary").click();
  const red = page
    .locator(".development-model tbody tr")
    .filter({ has: page.getByRole("rowheader", { name: "Red", exact: true }) });
  await expect(red.locator("td").nth(1)).toHaveText("0.0%");
  await expect(red.locator("td").nth(3)).toHaveText("0–0");
  await expect(page.locator(".development-model")).toContainText(
    "completed turns",
  );
});
