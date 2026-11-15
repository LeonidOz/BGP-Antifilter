import { test, expect } from "@playwright/test";

async function openMenu(page) {
  const toggle = page.locator("#menu-toggle");
  if (await toggle.isVisible() && await toggle.getAttribute("aria-expanded") === "false") await toggle.click();
}
async function navigate(page, view) {
  await openMenu(page);
  await page.locator(`[data-view="${view}"]`).click();
}
async function language(page, lang) {
  await openMenu(page);
  await page.locator(`#lang-${lang}`).click();
  const toggle = page.locator("#menu-toggle");
  if (await toggle.isVisible() && await toggle.getAttribute("aria-expanded") === "true") await toggle.click();
}

test.beforeEach(async ({page, request}) => {
  await request.post("/__test/reset");
  await page.goto("/");
  await page.locator("#password").fill("browser-test");
  await page.locator("#login-form button").click();
  await expect(page.locator("#admin-view")).toBeVisible();
});

test("BGP settings show neutral labels and accept legacy API values", async ({page}) => {
  const response=await page.request.put("/api/settings",{data:{values:{MT_IP:"198.51.100.77",MT_AS:"64577"}}});
  expect(response.ok()).toBeTruthy();
  await page.locator('.flow-node[data-stage="peer"]').click();
  await expect(page.locator("#stage-title")).toHaveText("BGP peer");
  await navigate(page, "settings");
  await expect(page.locator('[data-setting-key="PEER_IP"]')).toHaveValue("198.51.100.77");
  await expect(page.locator('[data-setting-key="PEER_AS"]')).toHaveValue("64577");
  await expect(page.locator('[data-setting-key="MT_IP"]')).toHaveCount(0);
  await page.locator('[data-setting-key="PEER_IP"]').fill("198.51.100.88");
  await page.locator("#save-settings-btn").click();
  await expect(page.locator("#settings-save-status")).toContainText("Saved");
  const values=(await (await page.request.get("/api/settings")).json()).values;
  expect(values.PEER_IP).toBe("198.51.100.88");
  expect(values.PEER_AS).toBe("64577");
  expect(values.MT_IP).toBeUndefined();
  await language(page, "ru");
  await expect(page.getByLabel("IP BGP peer",{exact:true})).toHaveValue("198.51.100.88");
});

test("menu pages and header update button work without a tools or metrics page", async ({page}, testInfo) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await expect(page.locator('[data-view="tools"]')).toHaveCount(0);
  await expect(page.locator('[data-view="updates"]')).toHaveCount(0);
  await expect(page.locator("#service-health")).toHaveCount(0);
  await expect(page.locator("#metrics-view")).toHaveCount(0);
  await expect(page.locator("#open-updates-btn")).toHaveClass(/update-available/);
  expect(await page.locator(".top-actions button").evaluateAll(buttons => buttons.map(button => button.id))).toEqual(["open-updates-btn", "refresh-btn", "logout-btn"]);
  for (const view of ["check", "network", "routes", "logs", "backups", "settings", "dashboard"]) {
    await navigate(page, view);
    await expect(page.locator(`#${view}`)).toBeVisible();
  }
  await page.locator("#open-updates-btn").click();
  await expect(page.locator("#updates")).toBeVisible();
  await expect(page.locator("#update-summary")).toContainText("newer release");
  await expect(page.locator("#open-updates-btn")).toHaveAttribute("aria-label", /Update/);
  await navigate(page, "dashboard");
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

test("route search and readable settings preserve seconds when saved", async ({page}) => {
  await navigate(page, "routes");
  await page.locator("#routes-search").fill("192.0.2.10");
  await expect(page.locator("#route-results")).toContainText("192.0.2.0/24");
  await page.locator("#routes-search").fill("300.0.0.1");
  await expect(page.locator("#routes-filter-count")).toContainText("valid IPv4");
  await navigate(page, "settings");
  await expect(page.locator('[data-setting-key="UPDATE_INTERVAL"]')).toHaveValue("30");
  await page.locator('[data-setting-key="UPDATE_INTERVAL"]').fill("45");
  await page.locator('[data-setting-key="CACHE_MAX_AGE"]').fill("2");
  await page.locator("#save-settings-btn").click();
  await expect(page.locator("#settings-save-status")).toContainText("Saved");
  const settings = await (await page.request.get("/api/settings")).json();
  expect(settings.values.UPDATE_INTERVAL).toBe("2700");
  expect(settings.values.CACHE_MAX_AGE).toBe("172800");
  expect((await page.locator('[data-setting-key="DNS_RESOLVERS"]').boundingBox()).height).toBeLessThan(160);
});

test("Google toggling and settings saves preserve unrelated and hidden overrides", async ({page}) => {
  await page.request.put("/api/settings", {data: {values: {FETCH_TIMEOUT: "45"}}});
  await navigate(page, "lists");
  await page.locator('[data-list="google-ranges"]').click();
  await page.locator(".google-ranges-toggle-card").click();
  await expect(page.locator("#list-save-status")).toContainText("Saved");
  await expect.poll(async () => (await (await page.request.get("/api/settings")).json()).values.INCLUDE_GOOGLE_RANGES).toBe("1");
  await navigate(page, "settings");
  await expect(page.locator('[data-setting-key="FETCH_TIMEOUT"]')).toHaveValue("45");
  await page.locator('[data-setting-key="FETCH_TIMEOUT"]').fill("60");
  await page.locator("#save-settings-btn").click();
  await expect(page.locator("#settings-save-status")).toContainText("Saved");
  const {values} = await (await page.request.get("/api/settings")).json();
  expect(values.FETCH_TIMEOUT).toBe("60");
  expect(values.INCLUDE_GOOGLE_RANGES).toBe("1");
});

test("copy works without Clipboard API and restores focus", async ({page}) => {
  await navigate(page, "lists");
  await page.locator('[data-list="urls"]').click();
  const button = page.locator("#list-tiles [data-copy]").first();
  const value = await button.getAttribute("data-copy");
  await page.evaluate(() => Object.defineProperty(navigator, "clipboard", {value: undefined, configurable: true}));
  await button.focus();
  await button.click();
  await expect(button).toHaveText("Copied");
  await expect(button).toBeFocused();
  await expect(page.locator('textarea[readonly]')).toHaveCount(0);
  await page.locator("#list-search").focus();
  await page.keyboard.press("Control+V");
  await expect(page.locator("#list-search")).toHaveValue(value);
});

test("failed IP checks stay failed when changing language", async ({page}) => {
  await navigate(page, "check");
  await page.locator("#check-ip-input").fill("192.0.2.1");
  await page.locator("#check-ip-submit").click();
  await expect(page.locator("#check-ip-result")).toContainText("192.0.2.1");
  await page.locator("#check-ip-input").fill("invalid target");
  await page.locator("#check-ip-submit").click();
  await expect(page.locator("#check-ip-result")).toContainText("target must be an IPv4 address or domain");
  await language(page, "ru");
  await expect(page.locator("#check-ip-result")).toContainText("target must be an IPv4 address or domain");
  await expect(page.locator("#check-ip-result")).not.toContainText("192.0.2.1");
  await expect(page.locator("#check-ip-result .status-pill")).toHaveText("Ошибка");
  await expect(page.locator("#check-ip-submit")).toHaveText("Проверить");
  await language(page, "en");
  await expect(page.locator("#check-ip-submit")).toHaveText("Check");
  await expect(page.locator("#check-ip-result .status-pill")).toHaveText("Failed");
});

test("Google controls stay separate and all localized list tabs fit phones", async ({page}) => {
  const status = await (await page.request.get("/api/status")).json();
  await page.route("**/api/status", route => route.fulfill({json: {...status, status: {...status.status, sources: [{kind: "google", name: "goog.json", status: "fresh", routes: 100, bytes: 1000}]}}}));
  await page.locator("#refresh-btn").click();
  await language(page, "ru");
  await navigate(page, "lists");
  await page.locator('[data-list="google-ranges"]').click();
  const left = await page.locator(".google-ranges-toggle-card").boundingBox();
  const right = await page.locator(".google-ranges-status-card").boundingBox();
  expect(Math.min(left.x+left.width,right.x+right.width)>Math.max(left.x,right.x) && Math.min(left.y+left.height,right.y+right.height)>Math.max(left.y,right.y)).toBe(false);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.locator('[data-list="urls"]').click();
  await page.locator("#list-search").fill("no-such-source");
  await expect(page.locator("#list-count")).toContainText("Показано: 0");
  await expect(page.locator("#list-tiles .list-card:visible")).toHaveCount(0);
  await page.setViewportSize({width: 901, height: 1000});
  expect((await page.locator("#add-list-input").boundingBox()).width).toBeGreaterThan(200);
});

test("preview applies the reviewed snapshot even when the source later changes", async ({page, request}) => {
  await request.post("/__test/source", {data: {content: "198.51.100.0/24\n"}});
  await page.locator("[data-preview-routes]").first().click();
  await expect(page.locator("#preview-diff")).toContainText("198.51.100.0/24");
  await expect(page.locator("#preview-diff")).toContainText("192.0.2.0/24");
  await request.post("/__test/source", {data: {content: "203.0.113.0/24\n"}});
  await page.locator("#apply-preview-btn").click();
  await expect.poll(async () => (await (await page.request.get("/api/routes")).text())).toContain("198.51.100.0/24");
  await navigate(page, "routes");
  await expect(page.locator("#routes-view")).toContainText("198.51.100.0/24");
  await expect(page.locator("#routes-view")).not.toContainText("203.0.113.0/24");
  await navigate(page, "check");
  await page.locator("#check-ip-input").fill("198.51.100.1");
  await page.locator("#check-ip-submit").click();
  await expect(page.locator("#check-ip-result")).toContainText("Confirmed route snapshot");
  await expect(page.locator("#check-ip-result")).toContainText("Example");
});

test("list edits have reviewable history and can be restored", async ({page}) => {
  await navigate(page, "lists");
  await page.locator(".raw-list-editor summary").click();
  const previous = await page.locator("#list-editor").inputValue();
  await page.locator("#list-editor").fill(previous + "# browser edit\n");
  await page.locator("#save-list-btn").click();
  await expect(page.locator("#list-save-status")).toContainText("Saved");
  await navigate(page, "backups");
  await expect(page.locator("[data-history-version]").first()).toBeVisible();
  await page.locator("[data-history-version]").first().click();
  await expect(page.locator("#history-review")).toContainText("-# browser edit");
  await page.locator("#restore-list-btn").click();
  await expect(page.locator("#backup-status")).toContainText("List restored");
  await navigate(page, "lists");
  await expect(page.locator("#list-editor")).toHaveValue(previous);
});

test("empty history explains when copies are created and loading errors stay visible", async ({page}) => {
  await navigate(page, "backups");
  await page.locator("#history-list").selectOption("exclude-domains");
  await expect(page.locator("#history-versions")).toContainText("This list has no saved versions yet");
  await expect(page.locator('[data-i18n="listHistoryHint"]')).toContainText("previous version is saved automatically");
  await expect(page.locator("#history-review")).toBeHidden();
  await page.route("**/api/backups/lists?*", route => route.fulfill({status: 500, json: {error: "History storage unavailable"}}));
  await page.locator("#load-history-btn").click();
  await expect(page.locator("#history-versions")).toContainText("History storage unavailable");
  await expect(page.locator("#history-versions")).not.toContainText("no saved versions");
  await expect(page.locator("#restore-list-btn")).toBeHidden();
  await page.unroute("**/api/backups/lists?*");
  await page.locator("#load-history-btn").click();
  await expect(page.locator("#history-versions")).toContainText("This list has no saved versions yet");
  await language(page, "ru");
  await expect(page.locator("#history-list option:checked")).toHaveText("Исключаемые домены");
  await expect(page.locator("#history-versions")).toContainText("Для этого списка");
});

test("navigation collapses on phones and expanded rows fit narrow screens", async ({page}, testInfo) => {
  await language(page, "ru");
  for (const width of testInfo.project.name === "mobile" ? [390, 320] : [1366, 901]) {
    await page.setViewportSize({width, height: 1000});
    if (width <= 900) {
      expect((await page.locator("#sidebar").boundingBox()).height).toBeLessThan(90);
      await openMenu(page);
    }
    const layout = await page.locator("#sidebar").evaluate(sidebar => {
      const nav=sidebar.querySelector("nav");
      const rows=[...nav.querySelectorAll(".nav-item")].map(button => {
        const box=button.getBoundingClientRect(), style=getComputedStyle(button);
        return {left:box.left,right:box.right,top:box.top,bottom:box.bottom,height:box.height,radius:style.borderRadius,overflow:button.scrollWidth>button.clientWidth};
      });
      return {sidebar:sidebar.getBoundingClientRect().toJSON(), nav:nav.getBoundingClientRect().toJSON(), rows, overflow:document.documentElement.scrollWidth>innerWidth};
    });
    expect(layout.overflow).toBe(false);
    expect(layout.nav.left).toBeCloseTo(layout.sidebar.left, 0);
    expect(layout.nav.right).toBeCloseTo(layout.sidebar.right - (width>900 ? 1 : 0), 0);
    for (const row of layout.rows) {
      expect(row.radius).toBe("0px");
      expect(row.height).toBeGreaterThanOrEqual(44);
      expect(row.overflow).toBe(false);
    }
    const columns=width>900 ? 1 : 2;
    for(let index=columns;index<layout.rows.length;index++) expect(layout.rows[index].top).toBeCloseTo(layout.rows[index-columns].bottom, 0);
    if(columns===2) expect(layout.rows[1].left).toBeCloseTo(layout.rows[0].right,0);
    if (width <= 900) await page.locator("#menu-toggle").click();
  }
  await navigate(page, "backups");
  await page.locator("#history-list").selectOption("exclude-domains");
  await expect(page.locator("#history-versions")).toContainText("Для этого списка");
  const clipped=await page.locator(".topbar h1, .top-actions button, #backups .button-link, .backup-transfer, #choose-config-btn, #history-list, #load-history-btn").evaluateAll(elements=>elements.filter(element=>{
    const box=element.getBoundingClientRect();
    return box.left<0 || box.right>innerWidth || element.scrollWidth>element.clientWidth+1;
  }).map(element=>element.id||element.className||element.tagName));
  expect(clipped).toEqual([]);
  await page.screenshot({path:testInfo.outputPath("sections-and-history.png"), fullPage:true});
});

test("configuration import requires review and invalid uploads preserve settings", async ({page}) => {
  await navigate(page, "backups");
  const exported = await (await page.request.get("/api/backups/export")).json();
  exported.settings.FETCH_TIMEOUT = "45";
  const upload = async backup => {
    const choosing = page.waitForEvent("filechooser");
    await page.locator("#choose-config-btn").click();
    await (await choosing).setFiles({name: "config.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(backup))});
    await expect(page.locator("#config-file-name")).toHaveText("config.json");
  };
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
