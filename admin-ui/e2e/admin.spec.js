import { test, expect } from "@playwright/test";

test.beforeEach(async ({page, request}) => {
  await request.post("/__test/reset");
  await page.goto("/");
  await page.locator("#password").fill("browser-test");
  await page.locator("#login-form button").click();
  await expect(page.locator("#admin-view")).toBeVisible();
});

test("menu pages and header update button work without a tools or metrics page", async ({page}, testInfo) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await expect(page.locator('[data-view="tools"]')).toHaveCount(0);
  await expect(page.locator("#metrics-view")).toHaveCount(0);
  await expect(page.locator("#open-updates-btn")).toHaveClass(/update-available/);
  expect(await page.locator(".top-actions button").evaluateAll(buttons => buttons.map(button => button.id))).toEqual(["open-updates-btn", "refresh-btn", "logout-btn"]);
  for (const view of ["check", "network", "routes", "logs", "backups", "settings", "dashboard"]) {
    await page.locator(`[data-view="${view}"]`).click();
    await expect(page.locator(`#${view}`)).toBeVisible();
  }
  await page.locator("#open-updates-btn").click();
  await expect(page.locator("#updates")).toBeVisible();
  await expect(page.locator("#update-summary")).toContainText("newer release");
  await expect(page.locator("#open-updates-btn")).toHaveAttribute("aria-label", /Update/);
  await page.locator('[data-view="dashboard"]').click();
  await page.screenshot({path: testInfo.outputPath("dashboard.png"), fullPage: true});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  expect(errors).toEqual([]);
});

test("route reload and polling never expand the operation log", async ({page}) => {
  const log = page.locator("#operation-log-details");
  await expect(log).not.toHaveAttribute("open", "");
  await page.locator('[data-action="reload"]').click();
  await expect(page.locator("#operation-log")).toContainText("Command completed", {timeout: 10000});
  await expect(log).not.toHaveAttribute("open", "");
  await log.locator(":scope > summary").click();
  await expect(log).toHaveAttribute("open", "");
  await page.locator("#refresh-btn").click();
  await expect(log).toHaveAttribute("open", "");
  await log.locator(":scope > summary").click();
  await page.locator("#refresh-btn").click();
  await expect(log).not.toHaveAttribute("open", "");
});

test("preview applies the reviewed snapshot even when the source later changes", async ({page, request}) => {
  await request.post("/__test/source", {data: {content: "198.51.100.0/24\n"}});
  await page.locator("[data-preview-routes]").first().click();
  await expect(page.locator("#preview-diff")).toContainText("198.51.100.0/24");
  await expect(page.locator("#preview-diff")).toContainText("192.0.2.0/24");
  await request.post("/__test/source", {data: {content: "203.0.113.0/24\n"}});
  await page.locator("#apply-preview-btn").click();
  await expect.poll(async () => (await (await page.request.get("/api/routes")).text())).toContain("198.51.100.0/24");
  await page.locator('[data-view="routes"]').click();
  await expect(page.locator("#routes-view")).toContainText("198.51.100.0/24");
  await expect(page.locator("#routes-view")).not.toContainText("203.0.113.0/24");
  await page.locator('[data-view="check"]').click();
  await page.locator("#check-ip-input").fill("198.51.100.1");
  await page.locator("#check-ip-submit").click();
  await expect(page.locator("#check-ip-result")).toContainText("Confirmed route snapshot");
  await expect(page.locator("#check-ip-result")).toContainText("Example");
});

test("list edits have reviewable history and can be restored", async ({page}) => {
  await page.locator('[data-view="lists"]').click();
  await page.locator(".raw-list-editor summary").click();
  const previous = await page.locator("#list-editor").inputValue();
  await page.locator("#list-editor").fill(previous + "# browser edit\n");
  await page.locator("#save-list-btn").click();
  await expect(page.locator("#list-save-status")).toContainText("Saved");
  await page.locator('[data-view="backups"]').click();
  await expect(page.locator("[data-history-version]").first()).toBeVisible();
  await page.locator("[data-history-version]").first().click();
  await expect(page.locator("#history-review")).toContainText("-# browser edit");
  await page.locator("#restore-list-btn").click();
  await expect(page.locator("#backup-status")).toContainText("List restored");
  await page.locator('[data-view="lists"]').click();
  await expect(page.locator("#list-editor")).toHaveValue(previous);
});

test("configuration import requires review and invalid uploads preserve settings", async ({page}) => {
  await page.locator('[data-view="backups"]').click();
  const exported = await (await page.request.get("/api/backups/export")).json();
  exported.settings.FETCH_TIMEOUT = "45";
  const upload = async backup => page.locator("#config-upload").setInputFiles({name: "config.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(backup))});
  await upload(exported);
  await expect(page.locator("#config-import-review")).toContainText("FETCH_TIMEOUT");
  await expect(page.locator("#restore-config-btn")).toBeVisible();
  expect((await (await page.request.get("/api/settings")).json()).values.FETCH_TIMEOUT).toBe("30");
  await page.locator("#restore-config-btn").click();
  await expect(page.locator("#backup-status")).toContainText("Configuration restored");
  expect((await (await page.request.get("/api/settings")).json()).values.FETCH_TIMEOUT).toBe("45");
  exported.settings.MT_IP = "bad";
  await upload(exported);
  await expect(page.locator("#backup-status")).toContainText("MT_IP must be a valid");
  await expect(page.locator("#restore-config-btn")).toBeHidden();
});

test("update screen survives a status disconnect and displays an expired session after restart", async ({page, request}) => {
  await page.locator("#open-updates-btn").click();
  let calls = 0;
  await page.route("**/api/update/status?force=1", route => ++calls === 1 ? route.abort("connectionreset") : route.continue());
  await page.locator("#check-updates-btn").click();
  await expect(page.locator("#update-summary")).toContainText("Update check failed");
  await page.locator("#check-updates-btn").click();
  await expect(page.locator("#update-summary")).toContainText("newer release");
  await request.post("/__test/expire");
  await page.reload();
  await expect(page.locator("#login-view")).toBeVisible();
});

test("an interrupted update launch keeps polling and returns to login after session loss", async ({page, request}) => {
  const available = await (await page.request.get("/api/update/status")).json();
  let interrupted = false;
  let launches = 0;
  await page.route("**/api/update/status*", route => interrupted ? route.continue() : route.fulfill({json: {
    ...available, updater_ok: true, updater_error: "", apply_available: true,
  }}));
  await page.route("**/api/update/apply", async route => {
    launches++;
    interrupted = true;
    await request.post("/__test/expire");
    await route.abort("connectionreset");
  });
  await page.locator("#open-updates-btn").click();
  await page.locator("#check-updates-btn").click();
  await expect(page.locator("#apply-update-btn")).toBeVisible();
  await page.locator("#apply-update-btn").click();
  await expect(page.locator("#login-view")).toBeVisible({timeout: 10000});
  expect(launches).toBe(1);
});
