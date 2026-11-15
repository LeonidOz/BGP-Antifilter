// Network/IP diagnostics, routes and logs pages.
import { api } from "./api.js";
import { $, escapeHtml, renderIcons, copyControl, downloadText } from "./dom.js";
import { formatDateTime, yesNo } from "./format.js";
import { t, sourceStatus } from "./i18n.js";
import { renderCommandResult, renderDataTree, renderErrorView } from "./results.js";
import { loadUpdateStatus, renderUpdateStatus, updateState } from "./updates.js";

const toolState = {
  checkIpPending: false,
  routes: [], routeQuery: "", routePage: 0,
  logs: "", logQuery: "", logLevel: "all",
  network: null, checkResponse: null, checkError: null,
};

function renderCheckIpResult(result) {
  if (!result) return "";
  const status = result.matched ? t("matched") : t("notMatched");
  const okClass = result.matched ? "ok" : "fail";
  const routes = (result.routes || []).map(route => `<span class="route-pill">${escapeHtml(route)}</span>`).join("");
  const sources = (result.sources || []).map(source => `
    <div class="kv">
      <span>${escapeHtml(t({url: "sourceUrl", asn: "sourceAsn", country: "countries", google: "sourceGoogle", "domain-list-url": "sourceDomainListUrl", "include-domain": "sourceIncludeDomain", "exclude-domain": "sourceExcludeDomain"}[source.kind] || source.kind))} · ${escapeHtml(sourceStatus(source.status))}</span>
      <strong>${escapeHtml(source.name || "-")}</strong>
      <div class="route-list">${(source.matches || []).map(match => `<span class="route-pill">${escapeHtml(match)}</span>`).join("")}</div>
    </div>
  `).join("");
  return `
    <div class="result-card">
      <p class="decision-banner ${result.decision === "included" ? "ok" : "warn"}"><strong>${t("routeDecision")}: ${t({included: "decisionIncluded", excluded: "decisionExcluded", absent: "decisionAbsent"}[result.decision] || "decisionAbsent")}</strong></p>
      <div class="result-head">
        <span class="status-pill ${okClass}">${status}</span>
        <span class="result-title">${escapeHtml(result.ip)}</span>
      </div>
      <h3>${t("generatedRoutes")}</h3>
      <div class="route-list">${routes || "—"}</div>
      <h3>${t("sources")}</h3>
      <div class="kv-grid">${sources || `<div class="kv"><strong>—</strong></div>`}</div>
      <p class="muted">${result.confirmed ? `${t("confirmedSnapshot")}: ${formatDateTime((result.snapshot_applied_at_unix || 0) * 1000)}` : t("provenanceUnavailable")}</p>
      ${(result.sources || []).some(source => source.domains?.length) ? `<h3>${t("domains")}</h3><div class="route-list">${result.sources.flatMap(source => source.domains || []).map(domain => `<span class="route-pill">${escapeHtml(domain)}</span>`).join("")}</div>` : ""}
      ${(result.exclusions || []).length ? `<h3>${t("exclusions")}</h3>${result.exclusions.map(source => `<p>${escapeHtml(source.name)}: ${source.matches.map(escapeHtml).join(", ")}</p>`).join("")}` : ""}
      <details><summary>${t("ipDetails")}</summary>${renderDataTree(result)}</details>
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
      <details><summary>${t("lookupDetails")}</summary>${renderDataTree(response)}</details>
    </div>`;
}

function renderNetworkView(data) {
  const addressPill = address => `<span class="route-pill">${escapeHtml(address)}${copyControl(address)}</span>`;
  const localAddresses = (data.local_ipv4 || []).map(addressPill).join("");
  const resolvers = (data.dns?.nameservers || []).map(addressPill).join("");
  const customResolvers = (data.custom_dns?.nameservers || []).map(addressPill).join("");
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
    [t("endpointAddress"), window.location.origin],
  ];
  const settingsRows = [
    ["Router ID", data.bird?.router_id || "-"],
    ["BIRD IP", data.bird?.bird_ip || "-"],
    [t("peer") + " IP", data.bird?.peer_ip || data.bird?.mikrotik_ip || "-"],
    ["BGP protocol", data.bird?.bgp_protocol || "-"],
    ["My AS", data.bird?.my_as || "-"],
    ["Peer AS", data.bird?.peer_as || data.bird?.mt_as || "-"],
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
      <p class="muted">${t("networkScope")}</p>
      ${data.bird?.bird_ip_check?.bird_ip_assigned === false ? `<p class="decision-banner warn">${t("networkIpWarning")}</p>` : ""}
      <div class="kv-grid">
        ${networkRows.map(([key, value]) => `
          <div class="kv"><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong>${copyControl(value)}</div>
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
      <div class="kv-grid">${settingsRows.map(([key, value]) => `<div class="kv"><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong>${copyControl(value)}</div>`).join("")}</div>
      <h3>${t("externalNetwork")}</h3>
      <div class="kv-grid">
        ${externalRows.map(([key, value]) => `
          <div class="kv ${externalStatus}"><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong>${copyControl(value)}</div>
        `).join("")}
      </div>
      <details><summary>${t("rawLookup")}</summary>${renderDataTree(data)}</details>
    </div>`;
}

function ipv4Range(value) {
  const match = String(value).match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?:\/(\d{1,2}))?$/);
  if (!match) return null;
  const octets = match.slice(1, 5).map(Number);
  const bits = match[5] == null ? 32 : Number(match[5]);
  if (octets.some(part => part > 255) || bits > 32) return null;
  const ip = octets.reduce((acc, part) => acc * 256 + part, 0);
  const size = 2 ** (32 - bits), start = Math.floor(ip / size) * size;
  return [start, start + size - 1];
}

function matchingRoutes(routes, query) {
  if (!query.trim()) return routes;
  const range = ipv4Range(query.trim());
  if (!range) return [];
  return routes.filter(route => {
    const candidate = ipv4Range(route.match(/^route\s+(\S+)/)?.[1] || "");
    return candidate && candidate[0] <= range[1] && range[0] <= candidate[1];
  });
}

function renderRouteMatches() {
  const filtered = matchingRoutes(toolState.routes, toolState.routeQuery);
  const pages = Math.max(1, Math.ceil(filtered.length / 250));
  toolState.routePage = Math.max(0, Math.min(toolState.routePage, pages - 1));
  $("routes-filter-count").textContent = toolState.routeQuery.trim() && !ipv4Range(toolState.routeQuery.trim())
    ? t("invalidRouteSearch") : `${t("shown")}: ${filtered.length} / ${toolState.routes.length}`;
  $("route-results").innerHTML = filtered.slice(toolState.routePage * 250, (toolState.routePage + 1) * 250).map(route => `<code>${escapeHtml(route)}</code>`).join("") || t("noMatches");
  $("routes-page").textContent = `${toolState.routePage + 1} / ${pages}`;
  $("routes-prev").disabled = toolState.routePage === 0;
  $("routes-next").disabled = toolState.routePage >= pages - 1;
}

function renderRoutesView(text) {
  toolState.routes = String(text || "").split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  return `
    <div class="result-card">
      <div class="result-head">
        <span class="status-pill ok">${toolState.routes.length} ${t("routes").toLowerCase()}</span>
        <a class="button-link" href="/api/routes/download" download="routes.conf">
          <i data-lucide="download"></i><span>${t("downloadRoutes")}</span>
        </a>
      </div>
      <form action="/api/routes/address-list.rsc" method="get" class="inline-form address-list-form">
        <label for="address-list-name">${t("addressListName")}</label>
        <input id="address-list-name" name="list" value="bgp-antifilter" required pattern="[A-Za-z0-9_.\\-]{1,64}" maxlength="64">
        <button type="submit"><i data-lucide="download"></i><span>${t("downloadAddressList")}</span></button>
      </form>
      <label class="search-label">${t("routeSearch")}<input id="routes-search" type="search" value="${escapeHtml(toolState.routeQuery)}" placeholder="1.1.1.1 / 192.0.2.0/24"></label>
      <p class="muted">${t("routeSearchHint")}</p>
      <span id="routes-filter-count" role="status"></span>
      <div class="route-lines" id="route-results"></div>
      <div class="pagination"><button type="button" id="routes-prev">${t("previousPage")}</button><span id="routes-page"></span><button type="button" id="routes-next">${t("nextPage")}</button></div>
    </div>`;
}

function logSeverity(line) {
  try {
    const event = JSON.parse(line);
    if (event.level) return /^(error|fatal|critical)$/i.test(event.level) ? "error" : /^warn(ing)?$/i.test(event.level) ? "warning" : "info";
  } catch { /* Plain container and BIRD output. */ }
  if (/<ERR>|\b(error|fatal|critical)\b|\bfailed\b(?![=:]\s*0\b)/i.test(line)) return "error";
  if (/<WARN>|\bwarn(ing)?\b/i.test(line)) return "warning";
  return "info";
}

function groupLogLines(lines) {
  const groups = [];
  for (const line of lines) {
    const key = line.replace(/^bird:\s+\d{4}-\d\d-\d\d\s+[\d:.]+\s+\[\d+\]\s*/, "");
    const previous = groups.at(-1);
    if (previous?.key === key) { previous.count++; previous.last = line; }
    else groups.push({key, first: line, last: line, count: 1, level: logSeverity(line)});
  }
  return groups;
}

function renderLogMatches() {
  const all = toolState.logs.split(/\r?\n/).filter(Boolean);
  const lines = all.filter(line => line.toLowerCase().includes(toolState.logQuery.toLowerCase()) && (toolState.logLevel === "all" || logSeverity(line) === toolState.logLevel));
  const groups = groupLogLines(lines);
  $("logs-count").textContent = `${t("shown")}: ${lines.length} / ${all.length} ${t("lines")} · ${groups.length} ${t("events")}`;
  $("log-results").innerHTML = groups.map(group => `<div class="log-event ${group.level}"><code>${escapeHtml(group.first)}</code>${group.count > 1 ? `<span class="chip">${group.count} ${t("repeats")}</span><code class="muted">${escapeHtml(group.last)}</code>` : ""}</div>`).join("") || t("noMatches");
}

function renderLogsView(text) {
  toolState.logs = String(text || "");
  return `
    <div class="result-card">
      <div class="filter-toolbar">
        <label>${t("logSearch")}<input id="logs-search" type="search" value="${escapeHtml(toolState.logQuery)}"></label>
        <label>${t("logLevel")}<select id="logs-level"><option value="all">${t("allLevels")}</option><option value="error" ${toolState.logLevel === "error" ? "selected" : ""}>${t("errorsOnly")}</option><option value="warning" ${toolState.logLevel === "warning" ? "selected" : ""}>${t("warningsOnly")}</option></select></label>
        <button id="logs-latest" type="button">${t("latestEvents")}</button><button id="logs-download" type="button">${t("downloadLogs")}</button>
      </div>
      <span id="logs-count" role="status"></span>
      <div class="log-view" id="log-results" tabindex="0" aria-label="${t("containerLogs")}"></div>
    </div>`;
}

async function loadToolTab(tabName) {
  if (tabName === "network") {
    $("network-view").textContent = t("loading");
    toolState.network = await api("/api/tools/network");
    $("network-view").innerHTML = renderNetworkView(toolState.network);
    renderIcons();
  } else if (tabName === "updates") {
    if (!updateState.updateStatusPayload) {
      await loadUpdateStatus();
    } else {
      renderUpdateStatus(updateState.updateStatusPayload);
    }
  } else if (tabName === "routes") {
    $("routes-view").textContent = t("loading");
    $("routes-view").innerHTML = renderRoutesView(await api("/api/routes", {headers: {"Content-Type": "text/plain"}}));
    renderRouteMatches();
    renderIcons();
  } else if (tabName === "logs") {
    $("logs-view").textContent = t("loading");
    $("logs-view").innerHTML = renderLogsView(await api("/api/logs", {headers: {"Content-Type": "text/plain"}}));
    renderLogMatches();
  }
}

function refreshToolLanguage() {
  if (!$("network").classList.contains("hidden") && toolState.network) $("network-view").innerHTML = renderNetworkView(toolState.network);
  if (!$("check").classList.contains("hidden") && toolState.checkResponse) $("check-ip-result").innerHTML = renderCheckTargetResult(toolState.checkResponse);
  if (!$("check").classList.contains("hidden") && toolState.checkError) $("check-ip-result").innerHTML = renderErrorView(toolState.checkError);
  if (!$("routes").classList.contains("hidden") && $("routes-search")) {
    const text = toolState.routes.join("\n"); $("routes-view").innerHTML = renderRoutesView(text); renderRouteMatches();
  }
  if (!$("logs").classList.contains("hidden") && $("logs-search")) { $("logs-view").innerHTML = renderLogsView(toolState.logs); renderLogMatches(); }
}

function bindToolsEvents() {
  $("routes-view").addEventListener("input", event => {
    if (event.target.id !== "routes-search") return;
    toolState.routeQuery = event.target.value; toolState.routePage = 0; renderRouteMatches();
  });
  $("routes-view").addEventListener("click", event => {
    const id = event.target.closest("button")?.id;
    if (!["routes-prev", "routes-next"].includes(id)) return;
    toolState.routePage += id === "routes-next" ? 1 : -1; renderRouteMatches();
    $("route-results").scrollTop = 0;
  });
  $("logs-view").addEventListener("input", event => {
    if (event.target.id !== "logs-search") return;
    toolState.logQuery = event.target.value; renderLogMatches();
  });
  $("logs-view").addEventListener("change", event => {
    if (event.target.id !== "logs-level") return;
    toolState.logLevel = event.target.value; renderLogMatches();
  });
  $("logs-view").addEventListener("click", event => {
    const id = event.target.closest("button")?.id;
    if (id === "logs-latest") { $("log-results").scrollTop = $("log-results").scrollHeight; $("log-results").focus(); }
    if (id === "logs-download") downloadText(toolState.logs, "bgp-antifilter.log");
  });
  $("check-ip-form").addEventListener("submit", async event => {
    event.preventDefault();
    const form = $("check-ip-form");
    const input = $("check-ip-input");
    const button = $("check-ip-submit");
    if (toolState.checkIpPending) return;
    toolState.checkIpPending = true;
    toolState.checkResponse = null;
    toolState.checkError = null;
    form.classList.add("busy");
    input.disabled = true;
    button.disabled = true;
    button.innerHTML = `<span class="spinner" aria-hidden="true"></span><span data-i18n="loading">${t("loading")}</span>`;
    $("check-ip-result").innerHTML = `<div class="result-card"><div class="result-head"><span class="status-pill warn">${t("loading")}</span></div></div>`;
    try {
      const result = await api("/api/tools/check-ip", {
        method: "POST",
        body: JSON.stringify({target: $("check-ip-input").value})
      });
      toolState.checkResponse = result;
      $("check-ip-result").innerHTML = renderCheckTargetResult(result) || renderCommandResult("check-ip", result);
    } catch (err) {
      toolState.checkError = err;
      $("check-ip-result").innerHTML = renderErrorView(err);
    } finally {
      toolState.checkIpPending = false;
      form.classList.remove("busy");
      input.disabled = false;
      button.disabled = false;
      button.innerHTML = `<i data-lucide="search"></i><span data-i18n="check">${t("check")}</span>`;
      renderIcons();
    }
  });
  $("load-logs-btn").addEventListener("click", () => loadToolTab("logs"));
}

export { bindToolsEvents, loadToolTab, ipv4Range, matchingRoutes, groupLogLines, logSeverity, refreshToolLanguage };
