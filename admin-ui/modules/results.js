// Command output, source records, route statistics and error rendering.
import { escapeHtml } from "./dom.js";
import { formatBytes, formatSecondsShort } from "./format.js";
import { t } from "./i18n.js";
import { sourceCacheFact } from "./runtime.js";

function renderCommandResult(action, result) {
  const okClass = result.ok ? "ok" : "fail";
  const title = result.ok ? t("commandOk") : t("commandFailed");
  const events = parseJsonLines(result.stdout || "");
  return `
    <div class="result-card">
      <div class="result-head">
        <span class="status-pill ${okClass}">${title}</span>
        <span class="chip">${escapeHtml(action)}</span>
      </div>
      <div class="kv-grid">
        <div class="kv"><span>${t("returnCode")}</span><strong>${result.returncode ?? "timeout"}</strong></div>
        <div class="kv"><span>${t("duration")}</span><strong>${formatSecondsShort(result.duration_seconds)}</strong></div>
        <div class="kv"><span>${t("stderr")}</span><strong>${result.stderr ? t("failed") : "OK"}</strong></div>
      </div>
      ${events.length ? renderEventTimeline(events) : result.stdout ? `<details><summary>${t("stdout")}</summary>${renderTextLines(result.stdout)}</details>` : ""}
      ${result.stderr ? renderErrorBlock(result.stderr) : ""}
      <details><summary>${t("rawDetails")}</summary>${renderDataTree(result)}</details>
    </div>`;
}

function renderAcceptedCommandResult(action, result) {
  return `
    <div class="result-card">
      <div class="result-head">
        <span class="status-pill warn">${escapeHtml(t("applying"))}</span>
        <span class="chip">${escapeHtml(action)}</span>
      </div>
      <div class="kv-grid">
        <div class="kv"><span>${t("statusWarn")}</span><strong>${escapeHtml(result.message || t("reloadStarted"))}</strong></div>
      </div>
    </div>`;
}

function parseJsonLines(stdout) {
  const events = [];
  for (const line of stdout.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("{")) continue;
    try {
      events.push(JSON.parse(trimmed));
    } catch {
      continue;
    }
  }
  return events;
}

function eventLevel(event) {
  const status = event.status || "";
  const message = event.message || "";
  if (status === "failed" || message.includes("failed")) return "fail";
  if (status === "cache" || status === "skipped" || status === "disabled" || event.skipped_domains > 0 || message.includes("skipping")) return "warn";
  return "ok";
}

function renderEventTimeline(events) {
  const compact = compactSourceEvents(events);
  return `
    <div class="timeline">
      ${compact.summary.length ? `
        <div class="timeline-summary">
          ${compact.summary.map(event => `<span class="chip ${eventLevel(event)}">${escapeHtml(event.message || event.stage || "event")}</span>`).join("")}
        </div>` : ""}
      ${compact.sources.map(source => {
        const progress = source.index && source.total ? `${source.index}/${source.total}` : "";
        return `
          <div class="timeline-item source-card ${source.level}">
            <div class="timeline-dot"></div>
            <div class="timeline-main">
              <div class="timeline-title">
                <strong>${escapeHtml(source.name)}</strong>
                <span class="chip ${source.level}">${escapeHtml(source.status)}</span>
                ${source.kind ? `<span class="chip">${escapeHtml(source.kind)}</span>` : ""}
                ${progress ? `<span class="chip">${escapeHtml(progress)}</span>` : ""}
              </div>
              <div class="timeline-meta">${escapeHtml([source.startedAt, source.finishedAt && source.finishedAt !== source.startedAt ? source.finishedAt : "", source.detail].filter(Boolean).join(" · "))}</div>
              <div class="source-events">
                ${source.events.map(event => `<span>${escapeHtml(event.message || event.stage || "event")}</span>`).join("")}
              </div>
            </div>
          </div>`;
      }).join("")}
    </div>`;
}

function sourceEventKey(event) {
  return event.url || event.name || event.domain || event.asn || "";
}

function compactSourceEvents(events) {
  const groups = new Map();
  const summary = [];
  for (const event of events) {
    const key = sourceEventKey(event);
    if (!key) {
      summary.push(event);
      continue;
    }
    if (!groups.has(key)) {
      groups.set(key, {
        name: key,
        detail: "",
        kind: event.kind || "",
        status: event.status || event.level || "progress",
        level: eventLevel(event),
        index: event.index,
        total: event.total,
        startedAt: event.ts || "",
        finishedAt: event.ts || "",
        events: []
      });
    }
    const group = groups.get(key);
    group.events.push(event);
    group.kind = event.kind || group.kind;
    group.status = event.status || group.status;
    group.level = eventLevel(event);
    group.index = event.index || group.index;
    group.total = event.total || group.total;
    group.detail = event.url && event.name && event.url !== event.name ? event.url : group.detail;
    group.startedAt = group.startedAt || event.ts || "";
    group.finishedAt = event.ts || group.finishedAt;
  }
  return {summary, sources: Array.from(groups.values())};
}

function renderErrorBlock(stderr) {
  return `
    <div class="error-block">
      <div class="result-head">
        <span class="status-pill fail">${t("stderr")}</span>
      </div>
      <pre>${escapeHtml(stderr)}</pre>
    </div>`;
}

function renderTextLines(text) {
  const lines = String(text || "").split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  const shown = lines.slice(0, 200);
  return `
    <div class="text-lines">
      ${shown.map(line => `<div class="text-line">${escapeHtml(line)}</div>`).join("") || "—"}
      ${lines.length > shown.length ? `<div class="text-line muted">… ${lines.length - shown.length} more</div>` : ""}
    </div>`;
}

function parseBirdStatus(text) {
  const value = String(text || "").replace(/\s+/g, " ").trim();
  if (!value) return [];
  const patterns = [
    ["version", /BIRD\s+([^\s]+)\s+ready/i],
    ["router ID", /Router ID is\s+([^\s]+)/i],
    ["hostname", /Hostname is\s+(.+?)\s+Current server time is/i],
    ["server time", /Current server time is\s+(.+?)\s+Last reboot/i],
    ["last reboot", /Last reboot on\s+(.+?)\s+Last reconfiguration/i],
    ["last reconfiguration", /Last reconfiguration on\s+(.+?)\s+Daemon/i],
    ["daemon", /(Daemon is .+)$/i],
  ];
  return patterns
    .map(([key, pattern]) => {
      const match = value.match(pattern);
      return match ? [key, match[1]] : null;
    })
    .filter(Boolean);
}

function parseWhitespaceTable(text) {
  const lines = String(text || "").split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  if (lines.length < 2) return null;
  const header = lines[0].split(/\s{2,}|\t+/).filter(Boolean);
  if (header.length < 2) return null;
  const rows = lines.slice(1).map(line => line.split(/\s{2,}|\t+/).filter(Boolean));
  if (!rows.length || rows.some(row => row.length < 2)) return null;
  return {header, rows};
}

function renderRows(rows) {
  return `
    <div class="kv-grid">
      ${rows.map(([key, value]) => `
        <div class="kv"><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>
      `).join("")}
    </div>`;
}

function renderOutputTable(table) {
  return `
    <div class="data-table command-table">
      <div class="data-table-row table-head">
        ${table.header.map(item => `<strong>${escapeHtml(item)}</strong>`).join("")}
      </div>
      ${table.rows.map(row => `
        <div class="data-table-row">
          ${table.header.map((_, index) => `<span>${escapeHtml(row[index] || "—")}</span>`).join("")}
        </div>
      `).join("")}
    </div>`;
}

function renderCommandDetails(raw) {
  if (!raw || typeof raw !== "object") return renderDataTree(raw);
  const stdout = raw.stdout || "";
  const birdRows = parseBirdStatus(stdout);
  const table = birdRows.length ? null : parseWhitespaceTable(stdout);
  const metaRows = [
    ["ok", raw.ok],
    ["returncode", raw.returncode ?? "timeout"],
    ["duration", formatSecondsShort(raw.duration_seconds)],
  ];
  if (raw.stderr) metaRows.push(["stderr", raw.stderr]);
  return `
    <div class="command-details">
      ${renderRows(metaRows)}
      ${birdRows.length ? `<h3>BIRD status</h3>${renderRows(birdRows)}` : ""}
      ${table ? `<h3>${t("stdout")}</h3>${renderOutputTable(table)}` : ""}
      ${!birdRows.length && !table && stdout ? `<h3>${t("stdout")}</h3>${renderTextLines(stdout)}` : ""}
      ${raw.stderr ? renderErrorBlock(raw.stderr) : ""}
    </div>`;
}

function renderStageOutput(stage) {
  const raw = stage.raw;
  if (!raw || typeof raw !== "object" || !("stdout" in raw || "stderr" in raw || "returncode" in raw)) {
    return "";
  }
  const stdout = raw.stdout || "";
  const birdRows = parseBirdStatus(stdout);
  const table = birdRows.length ? null : parseWhitespaceTable(stdout);
  if (birdRows.length) {
    return `<h3>BIRD status</h3>${renderRows(birdRows)}`;
  }
  if (table) {
    return `<h3>${t("stdout")}</h3>${renderOutputTable(table)}`;
  }
  if (stdout) {
    return `<h3>${t("stdout")}</h3>${renderTextLines(stdout)}`;
  }
  if (raw.stderr) {
    return renderErrorBlock(raw.stderr);
  }
  return "";
}

function renderErrorView(err) {
  if (err && typeof err === "object" && ("ok" in err || "returncode" in err || "stdout" in err || "stderr" in err)) {
    return renderCommandResult("request", err);
  }
  if (typeof err === "string") {
    return renderErrorBlock(err);
  }
  return `
    <div class="result-card">
      <div class="result-head"><span class="status-pill fail">${t("failed")}</span></div>
      ${renderDataTree(err)}
    </div>`;
}

function humanizeKey(key) {
  return String(key).replaceAll("_", " ");
}

function renderDataTree(value, depth = 0) {
  if (value == null || typeof value !== "object") {
    return `<span class="data-value">${escapeHtml(value ?? "—")}</span>`;
  }
  const entries = Array.isArray(value)
    ? value.map((item, index) => [`[${index + 1}]`, item])
    : Object.entries(value);
  if (!entries.length) return `<span class="muted">—</span>`;
  const limit = depth > 1 ? 30 : 80;
  const visible = entries.slice(0, limit);
  const extra = entries.length - visible.length;
  return `
    <div class="data-tree">
      ${visible.map(([key, item]) => {
        const complex = item && typeof item === "object";
        return `
          <div class="data-row ${complex ? "complex" : ""}">
            <span class="data-key">${escapeHtml(humanizeKey(key))}</span>
            <div class="data-cell">${complex ? renderDataTree(item, depth + 1) : renderDataTree(item, depth + 1)}</div>
          </div>`;
      }).join("")}
      ${extra > 0 ? `<div class="data-row"><span class="data-key">…</span><div class="data-cell">${extra} more</div></div>` : ""}
    </div>`;
}

function routeValue(value) {
  return value == null ? "-" : escapeHtml(value);
}

function routeCandidateCount(routes) {
  return routes.candidate ?? ((routes.base ?? 0) + (routes.include ?? 0));
}

function renderRouteMath(routes = {}) {
  const candidate = routeCandidateCount(routes);
  const afterExclusions = routes.after_exclusions;
  const collapsedRemoved = routes.collapsed_removed;
  const final = routes.final ?? "-";
  return `
    <div class="route-math">
      <div class="route-formula">
        <span><b>${routeValue(routes.base)}</b><small>${t("base")}</small></span>
        <em>+</em>
        <span><b>${routeValue(routes.include)}</b><small>${t("include")}</small></span>
        <em>=</em>
        <span><b>${routeValue(candidate)}</b><small>${t("routeCandidates")}</small></span>
        <em>→</em>
        <span><b>${routeValue(afterExclusions)}</b><small>${t("afterExclusions")}</small></span>
        <em>→</em>
        <span><b>${routeValue(final)}</b><small>${t("finalRoutes")}</small></span>
      </div>
      <div class="kv-grid compact">
        <div class="kv"><span>${t("exclude")}</span><strong>${routeValue(routes.exclude)}</strong></div>
        <div class="kv"><span>${t("excludeRules")}</span><strong>${routeValue(routes.exclude_rules_applied)}</strong></div>
        <div class="kv"><span>${t("collapsedRemoved")}</span><strong>${routeValue(collapsedRemoved)}</strong></div>
        <div class="kv ${routes.invalid ? "warn" : "ok"}"><span>${t("invalid")}</span><strong>${routeValue(routes.invalid ?? 0)}</strong></div>
      </div>
    </div>`;
}

function renderSourceDetails(sources = []) {
  return `
    <div class="timeline source-detail-list">
      ${sources.map(source => {
        const level = eventLevel(source);
        const facts = [
          source.kind,
          source.bytes != null ? `${t("downloaded")}: ${formatBytes(source.bytes)}` : "",
          source.routes != null ? `${t("resolvedRoutes")}: ${source.routes}` : "",
          sourceCacheFact(source),
        ].filter(Boolean).join(" · ");
        return `
          <div class="timeline-item source-card ${level}">
            <div class="timeline-dot"></div>
            <div class="timeline-main">
              <div class="timeline-title">
                <strong>${escapeHtml(source.name || source.url || source.kind || "source")}</strong>
                <span class="chip ${escapeHtml(source.status || "")}">${escapeHtml(source.status || "unknown")}</span>
                ${source.required === false ? `<span class="chip warn">optional</span>` : ""}
              </div>
              <div class="timeline-meta">${escapeHtml(facts)}</div>
              ${source.error ? `<div class="error-inline">${escapeHtml(source.error)}</div>` : ""}
            </div>
          </div>`;
      }).join("") || "—"}
    </div>`;
}

export {
  eventLevel,
  renderAcceptedCommandResult,
  renderCommandResult,
  renderDataTree,
  renderErrorView,
  renderRouteMath,
  renderRows,
  renderSourceDetails,
  renderStageOutput
};
