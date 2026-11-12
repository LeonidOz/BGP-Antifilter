// Network/IP diagnostics, metrics, routes and logs tabs.
import { api } from "./api.js";
import { dashboardState } from "./dashboard.js";
import { $, escapeHtml, renderIcons } from "./dom.js";
import { formatDateTime, formatDurationSeconds, formatSecondsShort, yesNo } from "./format.js";
import { locale, t } from "./i18n.js";
import { renderCommandResult, renderDataTree, renderErrorView, renderRows } from "./results.js";
import { runtimeDegradedSummary, runtimeStartupRefreshSummary } from "./runtime.js";
import { loadUpdateStatus, renderUpdateStatus, updateState } from "./updates.js";

const toolState = {
  checkIpPending: false,
};

function renderCheckIpResult(result) {
  if (!result) return "";
  const status = result.matched ? t("matched") : t("notMatched");
  const okClass = result.matched ? "ok" : "fail";
  const routes = (result.routes || []).map(route => `<span class="route-pill">${escapeHtml(route)}</span>`).join("");
  const sources = (result.sources || []).map(source => `
    <div class="kv">
      <span>${escapeHtml(source.kind)} · ${escapeHtml(source.status)}</span>
      <strong>${escapeHtml(source.name || "-")}</strong>
      <div class="route-list">${(source.matches || []).map(match => `<span class="route-pill">${escapeHtml(match)}</span>`).join("")}</div>
    </div>
  `).join("");
  return `
    <div class="result-card">
      <div class="result-head">
        <span class="status-pill ${okClass}">${status}</span>
        <span class="result-title">${escapeHtml(result.ip)}</span>
      </div>
      <h3>${t("generatedRoutes")}</h3>
      <div class="route-list">${routes || "—"}</div>
      <h3>${t("sources")}</h3>
      <div class="kv-grid">${sources || `<div class="kv"><strong>—</strong></div>`}</div>
      <details><summary>${t("rawDetails")}</summary>${renderDataTree(result)}</details>
    </div>`;
}

function renderCheckTargetResult(response) {
  const results = response.results || [];
  if (response.result && !results.length) return renderCheckIpResult(response.result);
  const cards = results.map(item => renderCheckIpResult(item.result)).join("");
  const matched = results.filter(item => item.result?.matched).length;
  return `
    <div class="result-card">
      <div class="result-head">
        <span class="status-pill ${matched ? "ok" : "fail"}">${matched}/${results.length} ${t("matched").toLowerCase()}</span>
        <span class="result-title">${escapeHtml(response.target || "")}</span>
        <span class="chip">${t("checkedAddresses")}: ${(response.addresses || []).length}</span>
      </div>
      <div class="ip-result-list">${cards || "—"}</div>
      <details><summary>${t("rawDetails")}</summary>${renderDataTree(response)}</details>
    </div>`;
}

function renderNetworkView(data) {
  const localAddresses = (data.local_ipv4 || []).map(address => `<span class="route-pill">${escapeHtml(address)}</span>`).join("");
  const resolvers = (data.dns?.nameservers || []).map(server => `<span class="route-pill">${escapeHtml(server)}</span>`).join("");
  const customResolvers = (data.custom_dns?.nameservers || []).map(server => `<span class="route-pill">${escapeHtml(server)}</span>`).join("");
  const searchDomains = (data.dns?.search || []).join(", ");
  const external = data.external || {};
  const externalStatus = external.ok ? "ok" : "warn";
  const locationParts = [external.country, external.regionName, external.city].filter(Boolean).join(" / ");
  const coords = external.lat != null && external.lon != null ? `${external.lat}, ${external.lon}` : "-";
  const networkRows = [
    [t("hostName"), data.hostname || "-"],
    [t("fqdn"), data.fqdn || "-"],
    [t("primaryAddress"), data.primary_ipv4 || "-"],
    [t("adminPort"), data.admin?.port || "-"],
  ];
  const settingsRows = [
    ["Router ID", data.bird?.router_id || "-"],
    ["BIRD IP", data.bird?.bird_ip || "-"],
    ["MikroTik IP", data.bird?.mikrotik_ip || "-"],
    ["BGP protocol", data.bird?.bgp_protocol || "-"],
    ["My AS", data.bird?.my_as || "-"],
    ["MT AS", data.bird?.mt_as || "-"],
  ];
  const externalRows = external.ok ? [
    [t("externalNetwork"), external.query || "-"],
    [t("location"), locationParts || "-"],
    [t("provider"), external.isp || "-"],
    [t("organization"), external.org || external.asname || "-"],
    [t("timezone"), external.timezone || "-"],
    [t("coordinates"), coords],
    [t("proxy"), yesNo(external.proxy)],
    [t("hosting"), yesNo(external.hosting)],
    [t("mobile"), yesNo(external.mobile)],
  ] : [
    [t("externalNetwork"), external.error || t("failed")],
  ];
  return `
    <div class="result-card">
      <div class="result-head">
        <span class="status-pill ok">${t("networkSummary")}</span>
        <span class="chip">${formatDateTime((data.fetched_at || 0) * 1000)}</span>
      </div>
      <div class="kv-grid">
        ${networkRows.map(([key, value]) => `
          <div class="kv"><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>
        `).join("")}
      </div>
      <h3>${t("localAddresses")}</h3>
      <div class="route-list">${localAddresses || "—"}</div>
      <h3>${t("dnsResolvers")}</h3>
      <div class="route-list">${resolvers || "—"}</div>
      ${searchDomains ? `<div class="muted">${escapeHtml(searchDomains)}</div>` : ""}
      <h3>${t("customDnsResolvers")}</h3>
      <div class="route-list">${customResolvers || "—"}</div>
      ${data.custom_dns?.enabled ? `<div class="muted">${t("dnsQueryTimeout")}: ${escapeHtml(String(data.custom_dns?.timeout_seconds ?? "-"))}s</div>` : `<div class="muted">${t("systemDnsResolvers")}</div>`}
      <h3>${t("networkSettings")}</h3>
      ${renderRows(settingsRows)}
      <h3>${t("externalNetwork")}</h3>
      <div class="kv-grid">
        ${externalRows.map(([key, value]) => `
          <div class="kv ${externalStatus}"><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>
        `).join("")}
      </div>
      <details><summary>${t("rawLookup")}</summary>${renderDataTree(data)}</details>
    </div>`;
}

function renderMetricsView(text) {
  const labels = {
    bgp_antifilter_routes_total: locale.lang === "ru" ? "Активные маршруты" : "Active routes",
    bgp_antifilter_last_update_timestamp_seconds: locale.lang === "ru" ? "Время последнего обновления" : "Last update time",
    bgp_antifilter_update_success: locale.lang === "ru" ? "Последняя генерация успешна" : "Last update success",
    bgp_antifilter_update_duration_seconds: locale.lang === "ru" ? "Время генерации" : "Update duration",
    bgp_antifilter_invalid_entries_total: locale.lang === "ru" ? "Невалидные записи" : "Invalid entries",
    bgp_antifilter_exclude_rules_applied_total: locale.lang === "ru" ? "Срабатывания исключений" : "Exclusion rule hits",
    bgp_antifilter_source_status_total: locale.lang === "ru" ? "Источники по статусам" : "Sources by status",
    bgp_antifilter_source_cache_age_seconds: locale.lang === "ru" ? "Возраст использованного кеша" : "Used cache age",
  };
  const rows = String(text || "").split(/\r?\n/)
    .filter(line => line.trim() && !line.startsWith("#"))
    .map(line => {
      const match = line.match(/^([^{\s]+)(?:\{([^}]*)\})?\s+(.+)$/);
      if (!match) return {name: line, label: line, tags: "", value: ""};
      const value = Number(match[3]);
      const rawValue = Number.isFinite(value) ? value : match[3];
      return {
        name: match[1],
        label: labels[match[1]] || match[1].replace(/^bgp_antifilter_/, "").replaceAll("_", " "),
        tags: match[2] || "",
        rawValue,
        value: formatMetricValue(match[1], rawValue),
      };
    })
    .filter(row => row.rawValue !== 0);
  const runtime = dashboardState.lastStatusPayload?.runtime || {};
  const status = dashboardState.lastStatusPayload?.status || {};
  const snapshotSummary = runtime?.startup_snapshot_used
    ? `${t("startupSnapshot")}: ${formatSecondsShort(runtime.startup_snapshot_age_seconds)}`
    : "";
  const runtimeSummary = runtimeStartupRefreshSummary(runtime);
  const degradedSummary = runtimeDegradedSummary(runtime, status);
  const extraSummary = [snapshotSummary, runtimeSummary, degradedSummary].filter(Boolean);
  return `
    <div class="result-card">
      <div class="result-head"><span class="status-pill ok">${rows.length} ${locale.lang === "ru" ? "значимых метрик" : "non-zero metrics"}</span></div>
      ${extraSummary.length ? `
        <div class="muted-box">${extraSummary.map(item => escapeHtml(item)).join("<br>")}</div>
      ` : ""}
      <div class="data-table">
        ${rows.map(row => `
          <div class="data-table-row">
            <strong>${escapeHtml(row.label)}</strong>
            <span>${escapeHtml(row.tags || "—")}</span>
            <code>${escapeHtml(row.value)}</code>
          </div>
        `).join("") || "—"}
      </div>
    </div>`;
}

function formatMetricValue(name, value) {
  if (name === "bgp_antifilter_update_success") {
    return value === 1 ? (locale.lang === "ru" ? "да" : "yes") : (locale.lang === "ru" ? "нет" : "no");
  }
  if (name === "bgp_antifilter_update_duration_seconds" || name === "bgp_antifilter_source_cache_age_seconds") {
    return formatDurationSeconds(value);
  }
  if (name === "bgp_antifilter_last_update_timestamp_seconds") {
    return formatDateTime(Number(value) * 1000);
  }
  return value;
}

function renderRoutesView(text) {
  const routes = String(text || "").split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  return `
    <div class="result-card">
      <div class="result-head">
        <span class="status-pill ok">${routes.length} ${t("routes").toLowerCase()}</span>
        <a class="button-link" href="/api/routes/download" download="routes.conf">
          <i data-lucide="download"></i><span>${t("downloadRoutes")}</span>
        </a>
      </div>
      <form action="/api/routes/address-list.rsc" method="get" class="inline-form">
        <label for="address-list-name">${t("addressListName")}</label>
        <input id="address-list-name" name="list" value="bgp-antifilter" required pattern="[A-Za-z0-9_.\\-]{1,64}" maxlength="64">
        <button type="submit"><i data-lucide="download"></i><span>${t("downloadAddressList")}</span></button>
      </form>
      <div class="route-lines">
        ${routes.map(route => `<code>${escapeHtml(route)}</code>`).join("") || "—"}
      </div>
    </div>`;
}

function renderLogsView(text) {
  const lines = String(text || "").split(/\r?\n/).filter(Boolean);
  return `
    <div class="result-card">
      <div class="result-head"><span class="status-pill ok">${t("containerLogs")}</span><span class="chip">${lines.length} lines</span></div>
      <pre class="log-view">${escapeHtml(lines.join("\n") || "—")}</pre>
    </div>`;
}

async function loadToolTab(tabName) {
  if (tabName === "network") {
    $("network-view").innerHTML = renderNetworkView(await api("/api/tools/network"));
  } else if (tabName === "updates") {
    if (!updateState.updateStatusPayload) {
      await loadUpdateStatus();
    } else {
      renderUpdateStatus(updateState.updateStatusPayload);
    }
  } else if (tabName === "metrics") {
    $("metrics-view").innerHTML = renderMetricsView(await api("/api/metrics", {headers: {"Content-Type": "text/plain"}}));
  } else if (tabName === "routes") {
    $("routes-view").innerHTML = renderRoutesView(await api("/api/routes", {headers: {"Content-Type": "text/plain"}}));
    renderIcons();
  } else if (tabName === "logs") {
    $("logs-view").innerHTML = renderLogsView(await api("/api/logs", {headers: {"Content-Type": "text/plain"}}));
  }
}

function switchToolTab(tabName) {
  document.querySelectorAll("[data-tool-tab]").forEach(button => {
    button.classList.toggle("active", button.dataset.toolTab === tabName);
  });
  document.querySelectorAll(".tool-tab").forEach(panel => panel.classList.add("hidden"));
  $(`tool-${tabName}`).classList.remove("hidden");
  loadToolTab(tabName).catch(err => {
    $(`tool-${tabName}`).querySelector(".result-view").innerHTML = renderErrorView(err);
  });
}

function bindToolsEvents() {
  $("check-ip-form").addEventListener("submit", async event => {
    event.preventDefault();
    const form = $("check-ip-form");
    const input = $("check-ip-input");
    const button = $("check-ip-submit");
    if (toolState.checkIpPending) return;
    toolState.checkIpPending = true;
    form.classList.add("busy");
    input.disabled = true;
    button.disabled = true;
    button.innerHTML = `<span class="spinner" aria-hidden="true"></span><span>${t("loading")}</span>`;
    $("check-ip-result").innerHTML = `<div class="result-card"><div class="result-head"><span class="status-pill warn">${t("loading")}</span></div></div>`;
    try {
      const result = await api("/api/tools/check-ip", {
        method: "POST",
        body: JSON.stringify({target: $("check-ip-input").value})
      });
      $("check-ip-result").innerHTML = renderCheckTargetResult(result) || renderCommandResult("check-ip", result);
    } catch (err) {
      $("check-ip-result").innerHTML = renderErrorView(err);
    } finally {
      toolState.checkIpPending = false;
      form.classList.remove("busy");
      input.disabled = false;
      button.disabled = false;
      button.innerHTML = `<i data-lucide="search"></i><span>${t("check")}</span>`;
      renderIcons();
    }
  });
  $("tool-tabs").addEventListener("click", event => {
    const tabName = event.target.closest("[data-tool-tab]")?.dataset.toolTab;
    if (tabName) switchToolTab(tabName);
  });
  $("load-logs-btn").addEventListener("click", () => loadToolTab("logs"));
}

export { bindToolsEvents, switchToolTab };
