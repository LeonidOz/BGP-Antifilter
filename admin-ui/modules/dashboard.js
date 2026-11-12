// Dashboard snapshots, pipeline stages and countdown rendering.
import { $, escapeHtml, replaceHtmlPreservingState } from "./dom.js";
import { formatCountdown, formatDateTime, formatDurationSeconds, formatSecondsShort } from "./format.js";
import { t } from "./i18n.js";
import {
  operationState,
  renderActiveOperationLog,
  renderCompletedReloadOperation,
  renderStoredReloadResult
} from "./operations.js";
import { renderDataTree, renderRouteMath, renderSourceDetails, renderStageOutput } from "./results.js";
import { birdUptime, renderRuntimeBanner, runtimeGenerationLabel, runtimeGenerationState } from "./runtime.js";
import { setVersion } from "./session.js";

const dashboardState = {
  lastStatusPayload: null,
  selectedStage: "sources",
};

function sourceCounts(sources = []) {
  return sources.reduce((acc, source) => {
    acc[source.status] = (acc[source.status] || 0) + 1;
    return acc;
  }, {});
}

function stageState(level, title, subtitle, rows, raw) {
  return {level, title, subtitle, rows, raw};
}

function rowLevel(key) {
  const normalized = String(key).toLowerCase();
  if (["fresh", "свежие", "ok"].includes(normalized)) return "ok";
  if (["skipped", "пропущено", "cache", "попадания в кеш", "invalid", "невалидные"].includes(normalized)) return "warn";
  if (["failed", "ошибки", "stderr"].includes(normalized)) return "fail";
  return "";
}

function buildStages(payload) {
  const status = payload?.status || {};
  const runtimeState = runtimeGenerationState(payload);
  const sources = status.sources || [];
  const counts = sourceCounts(sources);
  const routes = status.routes || {};
  const birdOk = payload?.bird?.ok;
  const bgpText = payload?.bgp?.stdout || "";
  const bgpOk = bgpText.includes("Established");
  const failed = counts.failed || 0;
  const skipped = counts.skipped || 0;
  const cached = counts.cache || 0;

  return {
    sources: stageState(
      failed ? "fail" : skipped || cached ? "warn" : "ok",
      t("sources"),
      `${sources.length} ${t("total").toLowerCase()} · ${counts.fresh || 0} ${t("fresh").toLowerCase()} · ${cached} ${t("cachedCount").toLowerCase()} · ${skipped} ${t("skipped").toLowerCase()} · ${failed} ${t("failedCount").toLowerCase()}`,
      [
        [t("fresh"), counts.fresh || 0],
        [t("cachedCount"), cached],
        [t("skipped"), skipped],
        [t("failedCount"), failed],
      ],
      sources
    ),
    cache: stageState(
      failed ? "fail" : "ok",
      t("cache"),
      cached ? `${cached} ${t("cacheUsed").toLowerCase()}` : t("noCacheUsed"),
      [
        [t("cacheHits"), cached],
        [t("freshDownloads"), counts.fresh || 0],
        [t("skippedSources"), skipped],
        [t("cacheTtl"), formatDurationSeconds(status.cache_max_age_seconds ?? 604800)],
      ],
      sources.filter(source => source.cache_file)
    ),
    generator: stageState(
      runtimeState ? "warn" : status.degraded ? "warn" : status.success === false ? "fail" : routes.invalid ? "warn" : "ok",
      t("generator"),
      runtimeState ? t("generatorBusy") : status.degraded ? (status.degraded_reason || t("degradedState")) : `${routes.final ?? 0} final routes`,
      runtimeState ? [
        [t("elapsed"), formatSecondsShort(runtimeState.elapsedSeconds)],
        [t("startedAt"), runtimeState.startedAt ? formatDateTime(runtimeState.startedAt * 1000) : "-"],
      ] : [],
      routes
    ),
    bird: stageState(
      birdOk ? "ok" : runtimeState?.initial ? "warn" : "fail",
      t("bird"),
      birdOk ? "birdc show status OK" : runtimeState?.initial ? t("birdWaitingInitial") : "birdc show status failed",
      [
        ["returncode", payload?.bird?.returncode ?? "-"],
        ["duration", formatSecondsShort(payload?.bird?.duration_seconds)],
      ],
      payload?.bird
    ),
    mikrotik: stageState(
      bgpOk ? "ok" : runtimeState?.initial ? "warn" : "fail",
      t("mikrotik"),
      bgpOk ? "BGP Established" : runtimeState?.initial ? t("mikrotikWaitingInitial") : "BGP not established",
      [
        ["protocol", "mikrotik"],
        ["returncode", payload?.bgp?.returncode ?? "-"],
      ],
      payload?.bgp
    ),
  };
}

function renderPipeline(payload) {
  if (!payload) return;
  const stages = buildStages(payload);
  document.querySelectorAll(".flow-node").forEach(node => {
    const stage = stages[node.dataset.stage];
    node.classList.remove("ok", "warn", "fail", "active");
    node.classList.add(stage.level);
    node.classList.toggle("active", node.dataset.stage === dashboardState.selectedStage);
    node.title = stage.subtitle;
  });
  renderStageDetails(stages[dashboardState.selectedStage] || stages.sources);
}

function renderStageDetails(stage) {
  const stageDetails = $("stage-details");
  $("stage-title").textContent = stage.title;
  $("stage-pill").textContent = stage.level === "ok" ? t("statusOk") : stage.level === "warn" ? t("statusWarn") : t("statusFail");
  $("stage-pill").className = `status-pill ${stage.level}`;
  const rowsClass = stage.rows.length >= 4 ? "kv-grid compact" : "kv-grid";
  const isRouteStats = stage.raw && typeof stage.raw === "object" && "final" in stage.raw && "base" in stage.raw;
  const details = isRouteStats
    ? renderRouteMath(stage.raw)
    : Array.isArray(stage.raw)
    ? `<details class="source-details-collapsed"><summary>${t("sourceDetails")}</summary>${renderSourceDetails(stage.raw)}</details>`
    : `<details><summary>${t("rawDetails")}</summary>${renderDataTree(stage.raw)}</details>`;
  replaceHtmlPreservingState(stageDetails, `
    <p>${escapeHtml(stage.subtitle)}</p>
    ${stage.rows.length ? `<div class="${rowsClass}">${stage.rows.map(([key, value]) => `
      <div class="kv ${rowLevel(key)}"><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>
    `).join("")}</div>` : ""}
    ${renderStageOutput(stage)}
    ${details}
  `);
}

function tickCountdown() {
  const label = $("next-update").dataset.label || "";
  if (label) {
    $("next-update").textContent = label;
    return;
  }
  $("next-update").textContent = formatCountdown(Number($("next-update").dataset.next || 0));
}

function renderStatus(data) {
  dashboardState.lastStatusPayload = data;
  setVersion(data.version);
  const status = data.status || {};
  const runtime = data.runtime || {};
  const runtimeState = runtimeGenerationState(data);
  const routes = status.routes || {};
  $("routes-count").textContent = routes.final ?? data.routes_file_count ?? "-";
  const resultCard = $("last-result").closest(".metric-card");
  resultCard.classList.remove("ok", "fail", "warn");
  if (runtimeState) {
    $("last-result").textContent = runtimeGenerationLabel(runtimeState);
    resultCard.classList.add("warn");
  } else if (runtime.degraded || status.degraded) {
    $("last-result").textContent = t("statusWarn");
    resultCard.classList.add("warn");
  } else if (status.success === true) {
    $("last-result").textContent = "OK";
    resultCard.classList.add("ok");
  } else if (status.success === false) {
    $("last-result").textContent = t("failed");
    resultCard.classList.add("fail");
  } else {
    $("last-result").textContent = "-";
    resultCard.classList.add("warn");
  }
  $("duration").textContent = formatSecondsShort(runtimeState?.elapsedSeconds ?? status.duration_seconds);
  $("last-update").textContent = `${t("lastGeneration")}: ${formatDateTime(status.updated_at)}`;
  $("bird-uptime").textContent = `${t("birdUptime")}: ${birdUptime(data.bird?.stdout)}`;
  if (runtimeState?.initial) {
    $("next-update").dataset.next = "";
    $("next-update").dataset.label = t("afterStartup");
  } else if (runtimeState && !runtime.next_scheduled_update_unix) {
    $("next-update").dataset.next = "";
    $("next-update").dataset.label = t("afterCurrentRun");
  } else {
    $("next-update").dataset.next = runtime.next_scheduled_update_unix || "";
    $("next-update").dataset.label = "";
  }
  tickCountdown();
  renderRuntimeBanner(data);
  renderPipeline(data);
  if (runtimeState) {
    $("operation-log-details").open = true;
    replaceHtmlPreservingState($("operation-log"), renderActiveOperationLog(data));
  } else if (operationState.pendingReloadOperation) {
    const completedReload = renderCompletedReloadOperation(data);
    const storedReload = completedReload || renderStoredReloadResult(data);
    if (storedReload) {
      operationState.pendingReloadOperation = false;
      operationState.pendingReloadStartedAtUnix = 0;
      $("operation-log-details").open = true;
      replaceHtmlPreservingState($("operation-log"), storedReload);
    }
  }
}

function bindDashboardEvents() {
  document.querySelectorAll(".flow-node").forEach(button => {
    button.addEventListener("click", () => {
      dashboardState.selectedStage = button.dataset.stage;
      renderPipeline(dashboardState.lastStatusPayload);
    });
  });
}

export { bindDashboardEvents, buildStages, dashboardState, renderPipeline, renderStatus, tickCountdown };
