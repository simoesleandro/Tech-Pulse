import { test, expect } from "@playwright/test";

test.describe("Filtros e layout", () => {
  test("drawer de administração expande e mostra ingestão", async ({ page }) => {
    await page.goto("/");

    const adminToggle = page.getByRole("button", { name: /Administração/i });
    await expect(adminToggle).toBeVisible();
    await adminToggle.click();

    await expect(page.getByText("Atualizar feed")).toBeVisible();
  });

  test("filtro Lixo atualiza URL", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Lixo" }).click();
    await expect(page).toHaveURL(/view=lixo/);
  });

  test("aba Obsidian atualiza URL", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Obsidian" }).click();
    await expect(page).toHaveURL(/view=obsidian/);
  });

  test("busca no feed expõe campo acessível", async ({ page }) => {
    await page.goto("/");

    const search = page.getByRole("searchbox", {
      name: /Buscar no feed por título/i,
    });
    await expect(search).toBeVisible();
    await search.fill("python");
    await page.getByRole("button", { name: "Buscar" }).click();
    await expect(page).toHaveURL(/q=python/);
  });

  test("limpar filtros remove parâmetros da URL", async ({ page }) => {
    await page.goto("/?source=dev.to&q=teste");

    await page.getByRole("link", { name: "Limpar filtros" }).click();
    await expect(page).not.toHaveURL(/source=/);
    await expect(page).not.toHaveURL(/q=/);
  });
});
