import { test, expect } from "@playwright/test";

const MOCK_INGEST_RESULT = {
  fetched: 2,
  skipped_duplicate: 1,
  classified: 1,
  saved: 1,
  relevante: 1,
  lixo: 0,
  errors: [],
};

function sseBody(events: object[]): string {
  return events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join("");
}

async function openIngestPanel(page: import("@playwright/test").Page) {
  await page.goto("/");
  const adminToggle = page.getByRole("button", { name: /Administração/i });
  await adminToggle.click();
  await expect(page.getByRole("button", { name: "Atualizar feed" })).toBeVisible();
}

test.describe("Ingestão (mock SSE)", () => {
  test("conclui ingest mock e mostra resultado", async ({ page }) => {
    await page.route("**/api/health", (route) =>
      route.fulfill({ json: { status: "ok", service: "techpulse-api" } }),
    );
    await page.route("**/api/pipeline/steps", (route) =>
      route.fulfill({
        json: {
          ingest: [{ id: "fetch", label: "Buscar", estimated_seconds: 5, agent: null }],
          backfill: [],
        },
      }),
    );
    await page.route("**/api/ingest/stream", (route) =>
      route.fulfill({
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
        body: sseBody([
          { type: "step", step_id: "fetch", status: "done", detail: "2 artigos" },
          { type: "step", step_id: "dedup", status: "done", detail: "1 novo" },
          { type: "complete", result: MOCK_INGEST_RESULT },
        ]),
      }),
    );

    await openIngestPanel(page);
    await page.getByRole("button", { name: "Atualizar feed" }).click();

    await expect(page.getByText(/1 salvas/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: "Atualizar feed" })).toBeVisible();
  });

  test("cancela ingest em andamento", async ({ page }) => {
    await page.route("**/api/health", (route) =>
      route.fulfill({ json: { status: "ok", service: "techpulse-api" } }),
    );
    await page.route("**/api/pipeline/steps", (route) =>
      route.fulfill({
        json: {
          ingest: [{ id: "fetch", label: "Buscar", estimated_seconds: 5, agent: null }],
          backfill: [],
        },
      }),
    );
    await page.route("**/api/ingest/stream", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 8_000));
      await route.fulfill({
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
        body: sseBody([{ type: "complete", result: MOCK_INGEST_RESULT }]),
      });
    });

    await openIngestPanel(page);
    await page.getByRole("button", { name: "Atualizar feed" }).click();
    await expect(page.getByRole("button", { name: "Cancelar" })).toBeVisible();

    await page.getByRole("button", { name: "Cancelar" }).click();

    await expect(page.getByText(/cancelada/i)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: "Atualizar feed" })).toBeVisible();
  });
});
