// Release checks, update actions and their display state.
import { api } from "./api.js";
import { $ } from "./dom.js";
import { formatDateTime } from "./format.js";
import { t } from "./i18n.js";

const updateState = {
  updateStatusPayload: null,
  applyPending: false,
  statusRequestId: 0,
};

function updateStatusLevel(data) {
  if (!data) return "warn";
  if (data.runtime?.active) return "warn";
  if (data.runtime?.success === false) return "fail";
  if (!data.ok) return "fail";
  return data.update_available ? "warn" : "ok";
}

function updateStageLabel(stage) {
  const map = {
    preparing: "updateStagePreparing",
    pulling: "updateStagePulling",
    restarting: "updateStageRestarting",
    verifying: "updateStageVerifying",
    rolling_back: "updateStageRollingBack",
    completed: "updateStageCompleted",
    failed: "updateStageFailed",
  };
  return t(map[stage] || "updateUnknown");
}

function releaseExcerpt(notes) {
  const lines = String(notes || "").split(/\r?\n/);
  const start = lines.findIndex(line => /^##\s+/.test(line));
  const selected = start >= 0 ? lines.slice(start) : lines;
  const end = selected.findIndex((line, index) => index > 0 && /^##\s+/.test(line));
  return (end >= 0 ? selected.slice(0, end) : selected).slice(0, 35).join("\n").trim().slice(0, 4000);
}

function renderUpdateStatus(data) {
  updateState.updateStatusPayload = data;
  const level = updateStatusLevel(data);
  const runtime = data?.runtime || {};
  $("update-pill").textContent = !data
    ? t("loading")
    : runtime.active
    ? t("updateApplying")
    : runtime.success === false
    ? t("updateStageFailed")
    : !data.ok
    ? t("updateCheckFailed")
    : data.update_available
    ? t("updateAvailableShort")
    : t("upToDate");
  $("update-pill").className = `status-pill ${level}`;
  $("update-current-version").textContent = data?.current_version ? `v${data.current_version}` : t("updateUnknown");
  $("update-latest-version").textContent = data?.latest_tag || (data?.latest_version ? `v${data.latest_version}` : t("updateUnknown"));
  $("update-published-at").textContent = data?.published_at ? formatDateTime(data.published_at) : t("never");
  let summary = !data
    ? t("loading")
    : runtime.active
    ? `${updateStageLabel(runtime.stage)}: ${runtime.target_version ? `v${runtime.target_version}` : ""}`.trim()
    : runtime.success === false
    ? `${t("updateStageFailed")}: ${runtime.error || t("failed")}`
    : !data.ok
    ? `${t("updateCheckFailed")}: ${data.error || t("failed")}`
    : data.update_available
    ? t("latestReleaseAvailable")
    : t("latestReleaseNotAvailable");
  if (runtime.success === false && typeof runtime.rollback?.ok === "boolean") {
    summary += runtime.rollback.ok ? ` · ${t("updateRollbackOk")}` : ` · ${t("updateRollbackFailed")}`;
  }
  if (data?.update_available && !data?.updater_ok && data?.updater_error && !runtime.active) {
    summary += ` · ${t("updaterUnavailable")}: ${data.updater_error}`;
  }
  $("update-summary").textContent = summary;
  $("release-notes-text").textContent = releaseExcerpt(data?.release_notes) || t("noReleaseNotes");
  $("update-release-link").href = data?.repository_url || "https://github.com/LeonidOz/BGP-Antifilter";
  $("open-release-link").href = data?.release_url || data?.repository_url || "https://github.com/LeonidOz/BGP-Antifilter";
  $("open-release-link").classList.toggle("hidden", !data?.ok);
  $("apply-update-btn").classList.toggle("hidden", !(data?.apply_available || runtime.active));
  $("apply-update-btn").disabled = Boolean(runtime.active) || !data?.apply_available;
  $("apply-update-btn").querySelector("span").textContent = runtime.active
    ? t("updateApplying")
    : data?.latest_tag
    ? `${t("applyUpdate")} ${data.latest_tag}`
    : t("applyUpdate");
  $("check-updates-btn").disabled = Boolean(runtime.active);
  const button = $("open-updates-btn");
  button?.classList.toggle("update-available", Boolean(runtime.active || data?.update_available));
  if (button) {
    button.title = runtime.active ? t("updateApplying") : data?.update_available ? `${t("updateAvailableShort")} ${data.latest_tag || ""}` : t("updateStatus");
    button.setAttribute("aria-label", button.title);
  }
}

async function loadUpdateStatus(force = false) {
  const requestId = ++updateState.statusRequestId;
  const path = force ? "/api/update/status?force=1" : "/api/update/status";
  try {
    const data = await api(path);
    if (requestId === updateState.statusRequestId && !updateState.applyPending) renderUpdateStatus(data);
  } catch (err) {
    if (updateState.updateStatusPayload?.runtime?.active && err?.error === "unauthorized") {
      window.location.reload();
    }
    throw err;
  }
}

async function applyUpdate() {
  const version = updateState.updateStatusPayload?.latest_version;
  if (!version || updateState.applyPending || !updateState.updateStatusPayload?.apply_available || updateState.updateStatusPayload?.runtime?.active) return;
  const previous = updateState.updateStatusPayload;
  updateState.applyPending = true;
  ++updateState.statusRequestId;
  renderUpdateStatus({...previous, apply_available: false,
    runtime: {active: true, stage: "preparing", target_version: version}});
  try {
    await api("/api/update/apply", {
      method: "POST",
      body: JSON.stringify({version})
    });
  } catch (err) {
    updateState.applyPending = false;
    // A disconnected POST may already have started the independent worker.
    if (err instanceof Error) {
      $("update-summary").textContent = t("updateReconnecting");
      return;
    }
    renderUpdateStatus({
      ...previous,
      runtime: {
        active: false,
        success: false,
        stage: "failed",
        error: typeof err === "string" ? err : (err.error || err.message || "request failed"),
      },
    });
    await loadUpdateStatus().catch(() => {});
    return;
  }
  updateState.applyPending = false;
  // Service downtime after an accepted request is expected; keep polling.
  await loadUpdateStatus().catch(() => {});
}

function bindUpdatesEvents() {
  $("check-updates-btn").addEventListener("click", () => {
    $("update-summary").textContent = t("loading");
    loadUpdateStatus(true).catch(err => {
      renderUpdateStatus({
        ok: false,
        current_version: $("version").textContent.replace(/^v/, "") || "",
        latest_version: "",
        latest_tag: "",
        repository_url: "https://github.com/LeonidOz/BGP-Antifilter",
        release_url: "https://github.com/LeonidOz/BGP-Antifilter",
        published_at: "",
        update_available: false,
        error: typeof err === "string" ? err : (err.error || err.message || "request failed"),
      });
    });
  });
  $("apply-update-btn").addEventListener("click", () => {
    applyUpdate().catch(() => {});
  });
}

export { applyUpdate, bindUpdatesEvents, loadUpdateStatus, renderUpdateStatus, updateState, releaseExcerpt };
