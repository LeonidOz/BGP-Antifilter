// Runtime stages, startup snapshots and degraded-state presentation.
import { $, escapeHtml, renderIcons } from "./dom.js";
import { formatBytes, formatDateTime, formatDurationSeconds, formatSecondsShort } from "./format.js";
import { t } from "./i18n.js";

function sourceCacheFact(source) {
  if (source.status !== "cache" || source.cache_age_seconds == null) return "";
  return `${t("cache")}: ${formatDurationSeconds(source.cache_age_seconds)}`;
}

function parseBirdTime(value) {
  const match = String(value || "").match(/(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})/);
  if (!match) return null;
  const [, year, month, day, hour, minute, second] = match.map(Number);
  return Date.UTC(year, month - 1, day, hour, minute, second) / 1000;
}

function birdUptime(stdout) {
  const text = String(stdout || "");
  const current = text.match(/Current server time is ([^\n]+)/);
  const reboot = text.match(/Last reboot on ([^\n]+)/);
  const currentTime = parseBirdTime(current?.[1]);
  const rebootTime = parseBirdTime(reboot?.[1]);
  if (currentTime == null || rebootTime == null || currentTime < rebootTime) return "-";
  return formatDurationSeconds(currentTime - rebootTime);
}

function runtimeGenerationState(payload) {
  const runtime = payload?.runtime || {};
  if (!runtime.generation_active) return null;
  const startedAt = Number(runtime.generation_started_at_unix || 0) || null;
  return {
    active: true,
    kind: runtime.generation_kind || "manual",
    initial: (runtime.generation_kind || "") === "initial",
    message: runtime.generation_message || "",
    startedAt,
    elapsedSeconds: startedAt ? Math.max(0, Math.floor(Date.now() / 1000) - startedAt) : null,
    itemsDone: Number.isFinite(Number(runtime.generation_items_done)) ? Number(runtime.generation_items_done) : null,
    itemsTotal: Number.isFinite(Number(runtime.generation_items_total)) ? Number(runtime.generation_items_total) : null,
  };
}

function runtimeGenerationLabel(state) {
  return state?.initial ? t("initializing") : t("updateInProgress");
}

function runtimeStageLabel(stage) {
  const labels = {
    "bootstrap": t("stageBootstrap"),
    "collecting-sources": t("stageCollectingSources"),
    "building-routes": t("stageBuildingRoutes"),
    "writing-routes": t("stageWritingRoutes"),
    "writing-status": t("stageWritingStatus"),
    "completed": t("stageCompleted"),
  };
  return labels[stage] || stage || t("stageRunning");
}

function runtimeSourceKindLabel(kind) {
  const labels = {
    "url": t("sourceUrl"),
    "domain-list-url": t("sourceDomainListUrl"),
    "asn": t("sourceAsn"),
    "google": t("sourceGoogle"),
    "include-domain": t("sourceIncludeDomain"),
    "exclude-domain": t("sourceExcludeDomain"),
  };
  return labels[kind] || kind || "";
}

function runtimeSnapshotChip(runtime) {
  if (!runtime?.startup_snapshot_used) return "";
  const details = [];
  const age = runtime.startup_snapshot_age_seconds;
  const size = runtime.startup_snapshot_size_bytes;
  if (age != null) details.push(`${t("snapshotAge")}: ${formatSecondsShort(age)}`);
  if (Number.isFinite(Number(size)) && Number(size) > 0) details.push(formatBytes(size));
  const label = details.length ? `${t("snapshotActive")} · ${details.join(" · ")}` : t("snapshotActive");
  return `<span class="chip warn">${escapeHtml(label)}</span>`;
}

function runtimeStartupRefreshSummary(runtime) {
  if ((runtime?.last_update_reason || "") !== "startup") return "";
  const success = runtime?.last_update_success;
  if (success == null) return "";
  const label = success ? t("startupRefreshOk") : t("startupRefreshFailed");
  const finishedAt = runtime?.last_update_finished_at_unix
    ? formatDateTime(runtime.last_update_finished_at_unix * 1000)
    : t("unknownTime");
  return `${label} · ${t("lastUpdateFinished")}: ${finishedAt}`;
}

function runtimeDegradedSummary(runtime, status) {
  const degraded = Boolean(runtime?.degraded || status?.degraded);
  if (!degraded) return "";
  const reason = runtime?.degraded_reason || status?.degraded_reason || "";
  return reason ? `${t("degradedState")} · ${t("degradedReason")}: ${reason}` : t("degradedState");
}

function renderRuntimeBanner(payload) {
  const banner = $("runtime-banner");
  const runtimeState = runtimeGenerationState(payload);
  if (!runtimeState) {
    banner.classList.add("hidden");
    banner.innerHTML = "";
    return;
  }
  const message = runtimeState.initial ? t("startupGenerationBanner") : t("refreshGenerationBanner");
  const percent = Math.max(0, Math.min(100, Number(payload?.runtime?.generation_progress_percent || 0)));
  const stageTitle = runtimeStageLabel(payload?.runtime?.generation_stage || "");
  const stageMessage = payload?.runtime?.generation_stage_message || runtimeState.message || "";
  const currentKind = payload?.runtime?.generation_current_kind || "";
  const currentName = payload?.runtime?.generation_current_name || "";
  const currentIndex = Number(payload?.runtime?.generation_current_index || 0) || null;
  const currentAttempt = Number(payload?.runtime?.generation_current_attempt || 0) || null;
  const currentAttemptTotal = Number(payload?.runtime?.generation_current_attempt_total || 0) || null;
  const snapshotChip = runtimeSnapshotChip(payload?.runtime || {});
  const itemsLabel = runtimeState.itemsDone != null && runtimeState.itemsTotal != null && runtimeState.itemsTotal > 0
    ? `${runtimeState.itemsDone} / ${runtimeState.itemsTotal}`
    : "";
  const attemptLabel = currentAttempt && currentAttemptTotal ? `${t("attempt")} ${currentAttempt}/${currentAttemptTotal}` : "";
  const currentSourceLabel = currentName
    ? `${runtimeSourceKindLabel(currentKind)}${currentIndex ? ` ${currentIndex}/${runtimeState.itemsTotal || "?"}` : ""}: ${currentName}${attemptLabel ? ` · ${attemptLabel}` : ""}`
    : "";
  const meta = [
    runtimeState.startedAt ? `<span class="chip warn">${escapeHtml(t("startedAt"))}: ${escapeHtml(formatDateTime(runtimeState.startedAt * 1000))}</span>` : "",
    runtimeState.elapsedSeconds != null ? `<span class="chip warn">${escapeHtml(t("elapsed"))}: ${escapeHtml(formatSecondsShort(runtimeState.elapsedSeconds))}</span>` : "",
    itemsLabel ? `<span class="chip warn">${escapeHtml(t("sources"))}: ${escapeHtml(itemsLabel)}</span>` : "",
    snapshotChip,
  ].filter(Boolean).join("");
  banner.innerHTML = `
    <div class="runtime-banner-head">
      <div class="runtime-banner-title">
        <i data-lucide="loader-circle"></i>
        <span>${escapeHtml(runtimeGenerationLabel(runtimeState))}</span>
      </div>
      <span class="status-pill warn">${escapeHtml(t("stageRunning"))}</span>
    </div>
    <div class="runtime-banner-body">${escapeHtml(message)}</div>
    <div class="runtime-progress">
      <div class="runtime-progress-head">
        <span>${escapeHtml(stageTitle)}${stageMessage ? ` · ${escapeHtml(stageMessage)}` : ""}</span>
        <strong>${escapeHtml(t("progress"))}: ${percent}%</strong>
      </div>
      ${currentSourceLabel ? `<div class="runtime-progress-head"><span>${escapeHtml(t("currentSource"))}: ${escapeHtml(currentSourceLabel)}</span></div>` : ""}
      <div class="runtime-progress-track"><div class="runtime-progress-bar" style="width:${percent}%"></div></div>
    </div>
    ${meta ? `<div class="runtime-banner-meta">${meta}</div>` : ""}
  `;
  banner.classList.remove("hidden");
  renderIcons();
}

export {
  birdUptime,
  renderRuntimeBanner,
  runtimeDegradedSummary,
  runtimeGenerationLabel,
  runtimeGenerationState,
  runtimeSourceKindLabel,
  runtimeStageLabel,
  runtimeStartupRefreshSummary,
  sourceCacheFact
};
