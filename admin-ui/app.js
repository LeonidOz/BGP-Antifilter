// Application startup and coordination between admin features.
import { api } from "./modules/api.js";
import {
  bindDashboardEvents,
  dashboardState,
  renderPipeline,
  renderStatus,
  tickCountdown
} from "./modules/dashboard.js";
import { $, escapeHtml, renderIcons, setStatusTone, bindCopyEvents } from "./modules/dom.js";
import { locale, t } from "./modules/i18n.js";
import {
  bindListsEvents,
  listState,
  loadList,
  refreshListDirtyState,
  renderDomainListSourcesPanel,
  renderListTiles,
  setupLists,
  toggleCountry
} from "./modules/lists.js";
import { canvasState } from "./modules/login-canvas.js";
import { operationState } from "./modules/operations.js";
import { renderAcceptedCommandResult, renderCommandResult, renderErrorView } from "./modules/results.js";
import { setVersion, showAdmin, showLogin } from "./modules/session.js";
import {
  applySettingsFormValues,
  bindSettingsEvents,
  loadSettings,
  markSettingsDirty,
  renderSettings,
  saveSettings,
  settingLabel,
  settingsFormValues,
  settingsState
} from "./modules/settings.js";
import { bindToolsEvents, loadToolTab, refreshToolLanguage } from "./modules/tools.js";
import { bindPreviewEvents, preparePreview } from "./modules/preview.js";
import { bindBackupEvents, loadHistory } from "./modules/backups.js";
import { bindUpdatesEvents, loadUpdateStatus, renderUpdateStatus, updateState } from "./modules/updates.js";

const STATUS_POLL_INTERVAL_MS = 2000;

const UPDATE_STATUS_POLL_INTERVAL_MS = 15 * 60 * 1000;

let statusTimer = null;

let updateStatusTimer = null;

function hasUnsavedChanges() {
  return listState.listDirty || listState.domainListUrlDirty || settingsState.settingsDirty;
}

function applyLang() {
  document.documentElement.lang = locale.lang;
  document.querySelectorAll("[data-i18n]").forEach(el => el.textContent = t(el.dataset.i18n));
  document.querySelectorAll("[data-placeholder]").forEach(el => el.placeholder = t(el.dataset.placeholder));
  for (const [id, key] of [["refresh-btn", "refresh"], ["logout-btn", "logout"], ["open-updates-btn", "updateStatus"]]) {
    $(id).title = t(key);
    $(id).setAttribute("aria-label", t(key));
  }
  $("lang-ru").classList.toggle("active", locale.lang === "ru");
  $("lang-en").classList.toggle("active", locale.lang === "en");
  if (settingsState.settingsPayload && !$("settings").classList.contains("hidden")) {
    const values = settingsState.settingsDirty ? settingsFormValues() : null;
    renderSettings(settingsState.settingsPayload);
    if (values) {
      applySettingsFormValues(values);
      markSettingsDirty();
    }
  }
  if (!$("lists").classList.contains("hidden")) {
    if (listState.currentList === "include-domains") {
      renderDomainListSourcesPanel();
    }
    renderListTiles();
  }
  refreshListDirtyState();
  refreshToolLanguage();
  document.querySelectorAll("[data-list]").forEach(button => button.querySelector("span").textContent = t(button.dataset.list));
  $("list-title").textContent = t(listState.currentList);
  if (dashboardState.lastStatusPayload) renderStatus(dashboardState.lastStatusPayload);
  if (!$("backups").classList.contains("hidden")) loadHistory();
  renderUpdateStatus(updateState.updateStatusPayload);
  renderIcons();
}

function applyActionStatus(status) {
  if (!status || typeof status !== "object") return false;
  if (!dashboardState.lastStatusPayload) {
    dashboardState.lastStatusPayload = {version: $("version").textContent.replace(/^v/, ""), status: {}, runtime: {}};
  }
  const previousStatus = dashboardState.lastStatusPayload.status || {};
  dashboardState.lastStatusPayload.status = {
    ...previousStatus,
    sources: Array.isArray(status.sources) ? status.sources : previousStatus.sources,
    source_check_success: status.success,
    source_check_errors: status.errors || [],
    source_check_updated_at: status.updated_at,
  };
  renderPipeline(dashboardState.lastStatusPayload);
  if (!$("lists").classList.contains("hidden")) {
    renderListTiles();
  }
  return true;
}

async function runAction(action) {
  const buttons = document.querySelectorAll("button");
  buttons.forEach(button => button.disabled = true);

  $("operation-log").innerHTML = `<span class="chip">Running ${escapeHtml(action)}...</span>`;
  try {
    const result = await api(`/api/actions/${action}`, {method: "POST", body: "{}"});

    if (action === "reload" && result.accepted) {
      operationState.pendingReloadOperation = true;
      operationState.pendingReloadStartedAtUnix = Math.floor(Date.now() / 1000);
      $("operation-log").innerHTML = renderAcceptedCommandResult(action, result);
      await loadStatus();
      return;
    }
    $("operation-log").innerHTML = renderCommandResult(action, result);
    if (action === "check-sources" && applyActionStatus(result.status)) {
      return;
    }
    await loadStatus();
  } catch (err) {

    $("operation-log").innerHTML = renderErrorView(err);
  } finally {
    buttons.forEach(button => button.disabled = false);
  }
}

function switchView(view) {
  if (view !== "lists" && !$("lists").classList.contains("hidden") && (listState.listDirty || listState.domainListUrlDirty) && !window.confirm(t("discardListChanges"))) {
    return;
  }
  if (view !== "settings" && !$("settings").classList.contains("hidden") && settingsState.settingsDirty && !window.confirm(t("discardSettingsChanges"))) {
    return;
  }
  document.querySelectorAll(".view").forEach(el => el.classList.add("hidden"));
  $(view).classList.remove("hidden");
  document.querySelectorAll(".nav-item").forEach(button => button.classList.toggle("active", button.dataset.view === view));
  const titleKey = {check: "checkTarget", routes: "routeMenu", updates: "updateStatus"}[view] || view;
  $("view-title").dataset.i18n = titleKey;
  $("view-title").textContent = t(titleKey);
  $("sidebar").classList.remove("menu-open");
  $("menu-toggle").setAttribute("aria-expanded", "false");
  $("admin-view").scrollIntoView({block: "start"});
  if (["check", "network", "routes", "logs", "updates"].includes(view)) {
    loadToolTab(view).catch(err => {
      const result = $(view).querySelector(".result-view");
      if (result) result.innerHTML = renderErrorView(err);
    });
  }
  if (view === "backups") loadHistory().catch(() => {});
  if (view === "lists") {
    renderListTiles();
    if (!dashboardState.lastStatusPayload) {
      loadStatus().catch(() => {});
    }
  }
  if (view === "settings") {
    loadSettings().catch(err => {
      $("settings-form").innerHTML = renderErrorView(err);
    });
  }
}

async function applySettingsNow() {
  $("apply-settings-btn").disabled = true;
  $("save-settings-btn").disabled = true;
  $("settings-save-status").textContent = t("applying");
  setStatusTone($("settings-save-status"), "warn");
  try {
    if (!await saveSettings()) return;
    const result = await api("/api/actions/reload", {method: "POST", body: "{}"});
    await Promise.all([loadSettings(), loadStatus()]);
    $("settings-save-status").textContent = result.accepted ? t("reloadStarted") : t("commandOk");
    setStatusTone($("settings-save-status"), result.accepted ? "warn" : "ok");
  } catch (err) {
    $("settings-save-status").textContent = `${t("failed")}: ${typeof err === "string" ? err : (err.error || err.message || "request failed")}`;
    setStatusTone($("settings-save-status"), "fail");
  } finally {
    $("apply-settings-btn").disabled = false;
    $("save-settings-btn").disabled = !settingsState.settingsDirty;
  }
}

async function saveListSourceSetting(key, value) {
  try {
    $("list-save-status").textContent = "...";
    setStatusTone($("list-save-status"));
    const result = await api("/api/settings", {
      method: "PUT",
      body: JSON.stringify({values: {[key]: value}})
    });
    renderSettings(result);
    renderIcons();
    await loadStatus();
    if (listState.currentList === "google-ranges") {
      renderListTiles();
    }
    refreshListDirtyState(`${t("saved")}: ${settingLabel(key)}`, "ok");
  } catch (err) {
    if (listState.currentList === "google-ranges") {
      renderListTiles();
    }
    refreshListDirtyState(`${t("failed")}: ${typeof err === "string" ? err : (err.error || err.message || "request failed")}`, "fail");
  }
}

async function init() {
  applyLang();
  const session = await api("/api/session");
  canvasState.loginNetworkLabels = session.login_network?.labels || [];
  setVersion(session.version);
  if (session.authenticated) {
    showAdmin();
    setupLists();
    await Promise.all([loadStatus(), loadList(listState.currentList), loadUpdateStatus(), loadSettings()]);
    statusTimer = setInterval(() => { loadStatus().catch(() => {}); }, STATUS_POLL_INTERVAL_MS);
    updateStatusTimer = setInterval(() => { loadUpdateStatus().catch(() => {}); }, UPDATE_STATUS_POLL_INTERVAL_MS);
    setInterval(tickCountdown, 1000);
  } else {
    showLogin();
  }
}

async function loadStatus() {
  if (updateState.updateStatusPayload?.runtime?.active) {
    loadUpdateStatus().catch(() => {});
  }
  const data = await api("/api/status");
  renderStatus(data);
  if (!$("lists").classList.contains("hidden")) {
    renderListTiles();
  }
}

bindListsEvents();
bindSettingsEvents();
bindToolsEvents();
bindUpdatesEvents();
bindDashboardEvents();
bindPreviewEvents();
bindBackupEvents();
bindCopyEvents();
$("menu-toggle").addEventListener("click", () => {
  const open = $("sidebar").classList.toggle("menu-open");
  $("menu-toggle").setAttribute("aria-expanded", String(open));
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape") {
    $("sidebar").classList.remove("menu-open");
    $("menu-toggle").setAttribute("aria-expanded", "false");
  }
});

$("login-form").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    await api("/api/login", {method: "POST", body: JSON.stringify({password: $("password").value})});
    $("login-error").textContent = "";
    await init();
  } catch {
    $("login-error").textContent = t("failed");
  }
});
$("logout-btn").addEventListener("click", async () => {
  if (hasUnsavedChanges() && !window.confirm(t(listState.listDirty ? "discardListChanges" : "discardSettingsChanges"))) {
    return;
  }
  await api("/api/logout", {method: "POST", body: "{}"});
  if (statusTimer) clearInterval(statusTimer);
  if (updateStatusTimer) clearInterval(updateStatusTimer);
  showLogin();
});
$("refresh-btn").addEventListener("click", () => {
  loadStatus().catch(() => {});
  const view = document.querySelector(".view:not(.hidden)")?.id;
  if (["network", "routes", "logs", "updates"].includes(view)) loadToolTab(view).catch(() => {});
});
$("open-updates-btn").addEventListener("click", () => switchView("updates"));
document.querySelectorAll("[data-preview-routes]").forEach(button => button.addEventListener("click", () => {
  switchView("preview");
  if (!$("preview").classList.contains("hidden")) preparePreview();
}));
document.querySelectorAll("[data-action]").forEach(button => {
  button.addEventListener("click", () => runAction(button.dataset.action));
});
document.querySelectorAll(".nav-item").forEach(button => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});
$("lang-ru").addEventListener("click", () => { locale.lang = "ru"; localStorage.setItem("lang", locale.lang); applyLang(); });
$("lang-en").addEventListener("click", () => { locale.lang = "en"; localStorage.setItem("lang", locale.lang); applyLang(); });
$("apply-settings-btn").addEventListener("click", applySettingsNow);
window.addEventListener("configuration-restored", () => {
  Promise.all([loadList(listState.currentList), loadSettings()]).catch(() => {});
});
$("list-source-settings").addEventListener("change", event => {
  const countryCheckbox = event.target.closest("[data-country-code]");
  if (countryCheckbox && listState.currentList === "countries") {
    toggleCountry(countryCheckbox.dataset.countryCode, countryCheckbox.checked);
    return;
  }
  if (event.target.id === "list-include-google-ranges") {
    saveListSourceSetting("INCLUDE_GOOGLE_RANGES", event.target.checked ? "1" : "0");
  }
});
window.addEventListener("beforeunload", event => {
  if (!hasUnsavedChanges()) return;
  event.preventDefault();
  event.returnValue = t("leavePageWarning");
});

init().catch(() => showLogin());
