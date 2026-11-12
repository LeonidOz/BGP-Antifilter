// Presentation and tracking of background route reloads.
import { escapeHtml } from "./dom.js";
import { formatDateTime, formatSecondsShort } from "./format.js";
import { t } from "./i18n.js";
import { renderCommandResult, renderDataTree, renderSourceDetails } from "./results.js";
import { runtimeGenerationState, runtimeSourceKindLabel, runtimeStageLabel } from "./runtime.js";

const operationState = {
  pendingReloadOperation: false,
  pendingReloadStartedAtUnix: 0,
};

function renderStoredReloadResult(payload) {
  const result = payload?.reload_result;
  if (!result || result.active || !result.started_at_unix) return "";
  if (operationState.pendingReloadStartedAtUnix && result.started_at_unix < operationState.pendingReloadStartedAtUnix) return "";
  return renderCommandResult("reload", result);
}

function renderCompletedReloadOperation(payload) {
  const runtime = payload?.runtime || {};
  const status = payload?.status || {};
  const finishedAt = Number(runtime.last_update_finished_at_unix || 0) || 0;
  const updatedAt = Number(status.updated_at_unix || 0) || 0;
  const completedAt = Math.max(finishedAt, updatedAt);
  if (!completedAt || completedAt < operationState.pendingReloadStartedAtUnix) return "";

  const success = runtime.last_update_success === true && !runtime.degraded && status.success !== false;
  const degraded = runtime.degraded || status.degraded;
  const pillClass = success ? "ok" : degraded ? "warn" : "fail";
  const title = success ? t("commandOk") : t("commandFailed");
  const runReason = runtime.last_update_reason || status.run_reason || "manual";
  const runMessage = status.run_message || runtime.last_update_message || "";
  const degradedReason = status.degraded_reason || runtime.degraded_reason || "";
  const sources = Array.isArray(status.sources) ? status.sources : [];
  const errors = Array.isArray(status.errors) ? status.errors : [];

  return `
    <div class="result-card">
      <div class="result-head">
        <span class="status-pill ${pillClass}">${escapeHtml(title)}</span>
        <span class="chip">${escapeHtml(runReason)}</span>
      </div>
      <div class="kv-grid">
        <div class="kv"><span>${t("lastUpdateFinished")}</span><strong>${escapeHtml(formatDateTime(finishedAt || updatedAt) || t("unknownTime"))}</strong></div>
        <div class="kv"><span>${t("duration")}</span><strong>${escapeHtml(formatSecondsShort(status.duration_seconds))}</strong></div>
        <div class="kv"><span>${t("sources")}</span><strong>${escapeHtml(`${sources.length}`)}</strong></div>
      </div>
      ${runMessage ? `<div class="text-lines"><div class="text-line">${escapeHtml(runMessage)}</div></div>` : ""}
      ${degradedReason ? `<div class="error-inline">${escapeHtml(degradedReason)}</div>` : ""}
      ${sources.length ? `<details open><summary>${t("sourceDetails")}</summary>${renderSourceDetails(sources)}</details>` : ""}
      ${errors.length ? `<details open><summary>${t("errors")}</summary>${renderDataTree(errors)}</details>` : ""}
    </div>`;
}

function renderActiveOperationLog(payload) {
  const runtime = payload?.runtime || {};
  const status = payload?.status || {};
  const runtimeState = runtimeGenerationState(payload);
  if (!runtimeState) return "";
  const stageTitle = runtimeStageLabel(runtime.generation_stage || "");
  const stageMessage = runtime.generation_stage_message || runtimeState.message || "";
  const currentKind = runtime.generation_current_kind || "";
  const currentName = runtime.generation_current_name || "";
  const currentIndex = Number(runtime.generation_current_index || 0) || null;
  const currentAttempt = Number(runtime.generation_current_attempt || 0) || null;
  const currentAttemptTotal = Number(runtime.generation_current_attempt_total || 0) || null;
  const itemsLabel = runtimeState.itemsDone != null && runtimeState.itemsTotal != null && runtimeState.itemsTotal > 0
    ? `${runtimeState.itemsDone} / ${runtimeState.itemsTotal}`
    : "";
  const sourceLabel = currentName
    ? `${runtimeSourceKindLabel(currentKind)}${currentIndex ? ` ${currentIndex}/${runtimeState.itemsTotal || "?"}` : ""}: ${currentName}${currentAttempt && currentAttemptTotal ? ` · ${t("attempt")} ${currentAttempt}/${currentAttemptTotal}` : ""}`
    : "";
  const sources = Array.isArray(status.sources) ? status.sources : [];
  const errors = Array.isArray(status.errors) ? status.errors : [];
  return `
    <div class="result-card">
      <div class="result-head">
        <span class="status-pill warn">${escapeHtml(t("applying"))}</span>
        <span class="chip">${escapeHtml(runtime.generation_kind || "reload")}</span>
      </div>
      <div class="kv-grid">
        <div class="kv"><span>${escapeHtml(t("stageRunning"))}</span><strong>${escapeHtml(stageTitle)}</strong></div>
        ${runtimeState.elapsedSeconds != null ? `<div class="kv"><span>${escapeHtml(t("elapsed"))}</span><strong>${escapeHtml(formatSecondsShort(runtimeState.elapsedSeconds))}</strong></div>` : ""}
        ${itemsLabel ? `<div class="kv"><span>${escapeHtml(t("sources"))}</span><strong>${escapeHtml(itemsLabel)}</strong></div>` : ""}
      </div>
      ${stageMessage ? `<div class="text-lines"><div class="text-line">${escapeHtml(stageMessage)}</div></div>` : ""}
      ${sourceLabel ? `<div class="timeline-summary"><span class="chip warn">${escapeHtml(t("currentSource"))}: ${escapeHtml(sourceLabel)}</span></div>` : ""}
      ${sources.length ? `<details open><summary>${t("sourceDetails")}</summary>${renderSourceDetails(sources)}</details>` : ""}
      ${errors.length ? `<details open><summary>${t("errors")}</summary>${renderDataTree(errors)}</details>` : ""}
    </div>`;
}

export { operationState, renderActiveOperationLog, renderCompletedReloadOperation, renderStoredReloadResult };
