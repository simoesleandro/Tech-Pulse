import { test, expect } from "@playwright/test";

const MOCK_EXPORT_RESULT = {
  exported: 2,
  skipped: 0,
  errors: [],
};

const MOCK_NEWS = {
  items: [
    {
      id: 1,
      title: "Nota teste A",
      url: "https://example.com/a",
      source: "dev_to",
      ai_relevance: "RELEVANTE",
      obsidian_exported: false,
    },
    {
      id: 2,
      title: "Nota teste B",
      url: "https://example.com/b",
      source: "reddit",
      ai_relevance: "RELEVANTE",
      obsidian_exported: false,
    },
  ],
  total: 2,
};

function sseBody(events: object[]): string {
  return events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join("");
}

async function openSystemPanel(page: import("@playwright/test").Page) {
  await page.goto("/");
  const adminToggle = page.getByRole("button", { name: /Administração/i });
  await adminToggle.click();
  await page.getByRole("button", { name: /Sistema/i }).click();
  await expect(page.getByRole("button", { name: "Exportar pendentes" })).toBeVisible();
}

test.describe("Obsidian export (mock SSE)", () => {
  test("exporta pendentes com stream mockado", async ({ page }) => {
    await page.route("**/api/backfill/status", (route) =>
      route.fulfill({
        json: {
          obsidian_unmarked: 2,
          legacy_enrichment_pending: 0,
        },
      }),
    );
    await page.route("**/api/news?**", (route) =>
      route.fulfill({ json: MOCK_NEWS }),
    );
    await page.route("**/api/obsidian/export/stream", (route) =>
      route.fulfill({
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
        body: sseBody([
          {
            type: "step",
            step_id: "fetch",
            status: "done",
            article_index: 1,
            article_total: 2,
            title: "Nota teste A",
          },
          {
            type: "step",
            step_id: "write",
            status: "done",
            article_index: 1,
            article_total: 2,
            detail: "Gravado",
          },
          {
            type: "step",
            step_id: "write",
            status: "done",
            article_index: 2,
            article_total: 2,
            detail: "Gravado",
          },
          { type: "complete", result: MOCK_EXPORT_RESULT },
        ]),
      }),
    );

    await openSystemPanel(page);
    await page.getByRole("button", { name: "Exportar pendentes" }).click();

    await expect(page.getByText(/2 nota\(s\) enviadas/i)).toBeVisible({
      timeout: 15_000,
    });
  });
});
