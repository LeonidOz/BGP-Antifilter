// Release checks, update actions and their display state.
import { api } from "./api.js";
import { $ } from "./dom.js";
import { formatDateTime } from "./format.js";
import { t } from "./i18n.js";

const updateState = {
  updateStatusPayload: null,
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
    completed: "updateStageCompleted",
    failed: "updateStageFailed",
  };
  return t(map[stage] || "updateUnknown");
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
  if (runtime.success === false && runtime.rollback) {
    summary += runtime.rollback.ok ? ` · ${t("updateRollbackOk")}` : ` · ${t("updateRollbackFailed")}`;
  }
  $("update-summary").textContent = summary;
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
  const noticeVisible = Boolean(runtime.active) || Boolean(data?.update_available);
  $("update-notice").classList.toggle("hidden", !noticeVisible);
  $("update-notice-pill").textContent = runtime.active
    ? t("updateApplying")
    : data?.latest_tag || t("updateAvailableShort");
  $("update-notice-summary").textContent = runtime.active
    ? summary
    : data?.latest_tag
    ? `${t("latestReleaseAvailable")} ${data.latest_tag}`
    : t("latestReleaseAvailable");
}

async function loadUpdateStatus(force = false) {
  const path = force ? "/api/update/status?force=1" : "/api/update/status";
  const data = await api(path);
  renderUpdateStatus(data);
}

async function applyUpdate() {
  const version = updateState.updateStatusPayload?.latest_version;
  if (!version) return;
  $("update-summary").textContent = t("updateStarting");
  $("apply-update-btn").disabled = true;
  try {
    await api("/api/update/apply", {
      method: "POST",
      body: JSON.stringify({version})
    });
    await loadUpdateStatus(true);
  } catch (err) {
    renderUpdateStatus({
      ...(updateState.updateStatusPayload || {}),
      ok: updateState.updateStatusPayload?.ok ?? false,
      runtime: {
        active: false,
        success: false,
        stage: "failed",
        error: typeof err === "string" ? err : (err.error || err.message || "request failed"),
      },
    });
  }
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

export { bindUpdatesEvents, loadUpdateStatus, renderUpdateStatus, updateState };
