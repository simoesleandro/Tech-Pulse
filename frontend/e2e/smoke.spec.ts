import { test, expect } from "@playwright/test";

test.describe("Tech-Pulse dashboard", () => {
  test("carrega o header e as abas do feed", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { name: /TECH\[PULSE\]/i })).toBeVisible();
    await expect(page.getByRole("link", { name: "Fila" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Lidas" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Salvos" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Lixo" })).toBeVisible();
  });

  test("aba Lixo navega com view=lixo", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Lixo" }).click();
    await expect(page).toHaveURL(/view=lixo/);
  });
});
