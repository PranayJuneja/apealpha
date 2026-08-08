import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright-core";

const executablePath =
  process.env.CHROME_PATH || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const baseUrl = process.env.APE_WEB_URL || "http://127.0.0.1:3000";
const query = process.env.APE_VERIFY_TICKER || "PLTR";
const outputDir = path.resolve("artifacts");
await mkdir(outputDir, { recursive: true });

async function revealWholePage(page) {
  await page.evaluate(async () => {
    const delay = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
    document.documentElement.style.scrollBehavior = "auto";
    const step = Math.max(400, Math.floor(window.innerHeight * 0.75));
    for (let y = 0; y < document.documentElement.scrollHeight; y += step) {
      window.scrollTo(0, y);
      await delay(140);
    }
    window.scrollTo(0, 0);
    await delay(200);
  });
}

const browser = await chromium.launch({ executablePath, headless: true });
const context = await browser.newContext({ viewport: { width: 1536, height: 960 } });
const page = await context.newPage();
const consoleErrors = [];
const failedRequests = [];

page.on("console", (message) => {
  if (message.type() === "error") consoleErrors.push(message.text());
});
page.on("requestfailed", (request) => {
  failedRequests.push(
    `${request.method()} ${request.url()} ${request.failure()?.errorText || "failed"}`,
  );
});

try {
  const home = await page.goto(baseUrl, { waitUntil: "networkidle", timeout: 30_000 });
  if (!home?.ok()) throw new Error(`Dashboard returned HTTP ${home?.status() ?? "unknown"}`);
  await page.getByRole("heading", { name: /Did the crowd/i }).waitFor();
  await page.getByText("Who knew first?", { exact: true }).first().waitFor();

  await page.goto(`${baseUrl}/research`, { waitUntil: "networkidle", timeout: 30_000 });
  await page.getByLabel("Ticker or company").fill(query);
  const pending = page.waitForResponse(
    (response) => response.url().includes("/api/research") && response.request().method() === "POST",
    { timeout: 140_000 },
  );
  await page.getByRole("button", { name: /Run the analysis/i }).click();
  const researchResponse = await pending;
  const researchBody = await researchResponse.json();
  if (!researchResponse.ok()) {
    throw new Error(`Research returned HTTP ${researchResponse.status()}: ${JSON.stringify(researchBody)}`);
  }

  await page.locator(".phase-pill").first().waitFor({ timeout: 30_000 });
  await page.getByRole("heading", { name: researchBody.company, exact: true }).waitFor();
  await page.getByText("Every observation, timestamped.", { exact: true }).waitFor();

  const evidenceCount = await page.locator('a[target="_blank"]').count();
  const coverageCount = await page
    .getByText("What this run could see", { exact: true })
    .locator("xpath=following::ul[1]/li")
    .count();
  const desktopScreenshot = path.join(outputDir, "ape-alpha-live-research.png");
  await revealWholePage(page);
  await page.screenshot({ path: desktopScreenshot, fullPage: true });

  await page.goto(`${baseUrl}/sources`, { waitUntil: "networkidle", timeout: 30_000 });
  await page.getByRole("heading", { name: /Every leg/i }).waitFor();
  const sourceCards = await page.locator("main li").count();

  await page.goto(`${baseUrl}/lab`, { waitUntil: "networkidle", timeout: 30_000 });
  await page.getByRole("heading", { name: /Does the rule survive/i }).waitFor();
  const strategyRows = await page.locator("tbody tr").count();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(baseUrl, { waitUntil: "networkidle", timeout: 30_000 });
  await page.getByRole("button", { name: "Open menu" }).click();
  await page.getByRole("navigation", { name: "Mobile navigation" }).waitFor();
  const mobileScreenshot = path.join(outputDir, "ape-alpha-mobile.png");
  await revealWholePage(page);
  await page.screenshot({ path: mobileScreenshot, fullPage: true });

  const overlay = await page
    .locator("[data-nextjs-dialog], .vite-error-overlay, #webpack-dev-server-client-overlay")
    .count();
  const result = {
    status:
      consoleErrors.length === 0 &&
      failedRequests.length === 0 &&
      overlay === 0 &&
      evidenceCount >= 1 &&
      coverageCount === 4 &&
      sourceCards >= 5 &&
      strategyRows >= 1
        ? "PASS"
        : "FAIL",
    query,
    resolvedTicker: researchBody.ticker,
    company: researchBody.company,
    phase: researchBody.snapshot?.phase,
    events: researchBody.events?.length ?? 0,
    coverage: researchBody.coverage,
    evidenceCount,
    coverageCount,
    sourceCards,
    strategyRows,
    errorOverlayCount: overlay,
    consoleErrors,
    failedRequests,
    screenshots: [desktopScreenshot, mobileScreenshot],
  };
  console.log(JSON.stringify(result, null, 2));
  if (result.status !== "PASS") process.exitCode = 1;
} finally {
  await browser.close();
}
