// Source list editors, domain-list URLs and their unsaved changes.
import { api } from "./api.js";
import { dashboardState } from "./dashboard.js";
import { $, escapeHtml, renderIcons, setStatusTone } from "./dom.js";
import { formatBytes } from "./format.js";
import { locale, t } from "./i18n.js";
import { eventLevel } from "./results.js";
import { sourceCacheFact } from "./runtime.js";
import { settingLabel, settingsState } from "./settings.js";

const listState = {
  currentList: "urls",
  listSavedContent: "",
  listSavedPath: "",
  listDirty: false,
  domainListUrlSavedContent: "",
  domainListUrlDraftContent: "",
  domainListUrlSavedPath: "",
  domainListUrlDirty: false,
  listEditIndex: null,
  domainListEditIndex: null,
};

const countryOptions = [
  {code: "RU", ru: "Россия", en: "Russia"},
  {code: "BY", ru: "Беларусь", en: "Belarus"},
  {code: "KZ", ru: "Казахстан", en: "Kazakhstan"},
  {code: "KG", ru: "Кыргызстан", en: "Kyrgyzstan"},
  {code: "UZ", ru: "Узбекистан", en: "Uzbekistan"},
  {code: "TJ", ru: "Таджикистан", en: "Tajikistan"},
  {code: "AM", ru: "Армения", en: "Armenia"},
  {code: "AZ", ru: "Азербайджан", en: "Azerbaijan"},
  {code: "GE", ru: "Грузия", en: "Georgia"},
  {code: "MD", ru: "Молдова", en: "Moldova"},
  {code: "UA", ru: "Украина", en: "Ukraine"},
  {code: "PL", ru: "Польша", en: "Poland"},
  {code: "DE", ru: "Германия", en: "Germany"},
  {code: "NL", ru: "Нидерланды", en: "Netherlands"},
  {code: "FI", ru: "Финляндия", en: "Finland"},
  {code: "EE", ru: "Эстония", en: "Estonia"},
  {code: "LV", ru: "Латвия", en: "Latvia"},
  {code: "LT", ru: "Литва", en: "Lithuania"},
  {code: "GB", ru: "Великобритания", en: "United Kingdom"},
  {code: "FR", ru: "Франция", en: "France"},
  {code: "CH", ru: "Швейцария", en: "Switzerland"},
  {code: "TR", ru: "Турция", en: "Turkey"},
  {code: "IL", ru: "Израиль", en: "Israel"},
  {code: "US", ru: "США", en: "United States"},
];

const listLabels = {
  "urls": "URLs",
  "asns": "ASNs",
  "countries": "Countries",
  "google-ranges": "Google ranges",
  "include-domains": "Include domains",
  "exclude-domains": "Exclude domains"
};

const listIcons = {
  "urls": "link-2",
  "asns": "hash",
  "countries": "flag",
  "google-ranges": "globe",
  "include-domains": "circle-plus",
  "exclude-domains": "circle-minus"
};

function listUnsavedLabel() {
  return t("unsavedChanges");
}

function refreshListDirtyState(message = "", tone = "") {
  $("save-list-btn").disabled = !listState.listDirty;
  if (message) {
    $("list-save-status").textContent = message;
    setStatusTone($("list-save-status"), tone);
    return;
  }
  $("list-save-status").textContent = listState.listDirty ? listUnsavedLabel() : listState.listSavedPath;
  setStatusTone($("list-save-status"), listState.listDirty ? "warn" : "");
}

function markListDirty(dirty) {
  listState.listDirty = dirty;
  refreshListDirtyState();
}

function setupLists() {
  const tabs = $("list-tabs");
  tabs.innerHTML = Object.entries(listLabels)
    .map(([name, label]) => `
      <button data-list="${name}">
        <i data-lucide="${listIcons[name]}"></i>
        <span>${label}</span>
      </button>`)
    .join("");
  renderIcons();
  tabs.addEventListener("click", event => {
    const name = event.target.closest("[data-list]")?.dataset.list;
    if (name) loadList(name);
  });
}

async function loadList(name) {
  if (name !== listState.currentList && (listState.listDirty || listState.domainListUrlDirty) && !window.confirm(t("discardListChanges"))) {
    return;
  }
  listState.currentList = name;
  listState.listEditIndex = null;
  listState.domainListEditIndex = null;
  document.querySelectorAll("[data-list]").forEach(button => button.classList.toggle("active", button.dataset.list === name));
  $("list-title").textContent = listLabels[name];
  const special = isSpecialList(name);
  const showHintPanel = special || name === "asns" || name === "include-domains";
  $("add-list-form").classList.toggle("hidden", special);
  $("list-source-settings").classList.toggle("hidden", !showHintPanel);
  $("list-tiles").classList.toggle("hidden", false);
  $("dry-after-save-btn").closest(".list-actions").classList.toggle("hidden", name === "google-ranges");
  $("list-editor").closest(".raw-list-editor").classList.toggle("hidden", special);
  if (name === "google-ranges") {
    listState.listSavedContent = "";
    listState.listSavedPath = settingsState.settingsPayload?.settings_env_file || "";
    $("list-editor").value = "";
    $("add-list-input").value = "";
    markListDirty(false);
    renderListTiles();
    refreshListDirtyState(listState.listSavedPath);
    return;
  }
  const data = await api(`/api/lists/${name}`);
  listState.listSavedContent = data.content || "";
  listState.listSavedPath = data.path || "";
  $("list-editor").value = listState.listSavedContent;
  $("add-list-input").value = "";
  $("add-list-input").placeholder = `${t("itemPlaceholder")}: ${listLabels[name]}`;
  $("add-list-name-input").value = "";
  $("add-list-name-input").placeholder = `${t("domainListName")} (${t("optional")})`;
  $("add-list-name-input").classList.toggle("hidden", name !== "urls");
  $("add-list-form").classList.toggle("named-url-form", name === "urls");
  setListEditForm();
  markListDirty(false);
  if (name === "include-domains") {
    await loadDomainListUrls();
  } else {
    listState.domainListUrlSavedContent = "";
    listState.domainListUrlDraftContent = "";
    listState.domainListUrlSavedPath = "";
    listState.domainListUrlDirty = false;
  }
  renderListHint(name);
  renderListTiles();
}

async function saveList() {
  try {
    let content = $("list-editor").value;
    if (content && !content.endsWith("\n")) {
      content += "\n";
      $("list-editor").value = content;
    }
    const result = await api(`/api/lists/${listState.currentList}`, {
      method: "PUT",
      body: JSON.stringify({content})
    });
    listState.listSavedContent = content;
    markListDirty(false);
    refreshListDirtyState(
      `${t("saved")}: ${result.bytes} bytes${result.backup ? ` · ${t("backupSaved")}: ${result.backup}` : ""}`,
      "ok"
    );
    renderListTiles();
  } catch (err) {
    refreshListDirtyState(`${t("failed")}: ${typeof err === "string" ? err : (err.error || err.message || "request failed")}`, "fail");
  }
}

function parseListLines(content) {
  return String(content || "").split(/\r?\n/).map((line, index) => {
    const trimmed = line.trim();
    return {
      index,
      raw: line,
      value: trimmed,
      active: Boolean(trimmed && !trimmed.startsWith("#")),
      comment: Boolean(trimmed.startsWith("#")),
    };
  });
}

function normalizeAsn(value) {
  const trimmed = String(value || "").trim().toUpperCase();
  return trimmed.startsWith("AS") ? trimmed : `AS${trimmed}`;
}

function normalizeCountryCode(value) {
  return String(value || "").trim().toUpperCase();
}

function selectedCountriesFromEditor() {
  return new Set(
    parseListLines($("list-editor").value)
      .filter(line => line.active)
      .map(line => normalizeCountryCode(line.value))
  );
}

function countryLabel(option) {
  return locale.lang === "ru" ? option.ru : option.en;
}

function isSpecialList(name) {
  return name === "google-ranges" || name === "countries";
}

function renderListHint(name) {
  if (name === "include-domains") {
    renderDomainListSourcesPanel();
    return;
  }
  const key = name === "asns"
    ? "listHintAsns"
    : name === "countries"
      ? "listHintCountries"
      : name === "google-ranges"
        ? "listHintGoogleRanges"
        : "";
  if (!key) {
    $("list-source-settings").innerHTML = "";
    return;
  }
  $("list-source-settings").innerHTML = `
    <article class="panel settings-section">
      <h2>${escapeHtml(listLabels[name] || name)}</h2>
      <p class="muted">${escapeHtml(t(key))}</p>
    </article>
  `;
}

function listSourceRecord(listName, value) {
  const sources = dashboardState.lastStatusPayload?.status?.sources || [];
  if (listName === "google-ranges") {
    const googleSources = sources.filter(source => source.kind === "google");
    if (!googleSources.length) {
      return null;
    }
    const firstFailed = googleSources.find(source => source.status === "failed");
    const firstCached = googleSources.find(source => source.status === "cache");
    const firstDisabled = googleSources.find(source => source.status === "disabled");
    const totalRoutes = googleSources.reduce((sum, source) => sum + (Number(source.routes) || 0), 0);
    const totalBytes = googleSources.reduce((sum, source) => sum + (Number(source.bytes) || 0), 0);
    const cacheAges = googleSources
      .map(source => Number(source.cache_age_seconds))
      .filter(value => Number.isFinite(value));
    return {
      kind: "google",
      name: "google-ranges",
      status: firstFailed ? "failed" : firstCached ? "cache" : firstDisabled ? "disabled" : "fresh",
      error: firstFailed?.error || null,
      routes: totalRoutes || null,
      bytes: totalBytes || null,
      cache_age_seconds: cacheAges.length ? Math.min(...cacheAges) : null,
    };
  }
  if (listName === "urls") {
    const entry = parseNamedUrlSourceLine(value);
    if (!entry) return null;
    return sources.find(source => source.kind === "url" && source.url === entry.url);
  }
  if (listName === "domain-list-urls") {
    const entry = parseNamedUrlSourceLine(value);
    if (!entry) return null;
    return sources.find(source => source.kind === "domain-list-url" && source.url === entry.url);
  }
  if (listName === "asns") {
    const asn = normalizeAsn(value);
    return sources.find(source => source.kind === "asn" && String(source.name || "").toUpperCase() === asn);
  }
  if (listName === "countries") {
    const country = String(value || "").trim().toUpperCase();
    return sources.find(source => source.kind === "country" && String(source.name || "").toUpperCase() === country);
  }
  if (listName === "include-domains") {
    return sources.find(source => source.kind === "include-domain" && source.name === value);
  }
  if (listName === "exclude-domains") {
    return sources.find(source => source.kind === "exclude-domain" && source.name === value);
  }
  return null;
}

function renderGoogleRangesTab() {
  const enabled = String(settingsState.settingsPayload?.values?.INCLUDE_GOOGLE_RANGES || "0") === "1";
  const record = listSourceRecord("google-ranges", "");
  const level = record ? eventLevel(record) : (enabled ? "warn" : "");
  const statusCard = record ? `<div class="list-card ${level} google-ranges-status-card">${renderListSourceStats(record)}</div>` : "";
  $("list-source-settings").innerHTML = `
    <article class="panel settings-section">
      <h2>${escapeHtml(t("googleRangesSourceTitle"))}</h2>
      <p class="muted">${escapeHtml(t("listHintGoogleRanges"))}</p>
      <div class="google-ranges-layout">
        <div class="google-ranges-left">
          <label class="setting-card google-ranges-toggle-card">
            <span class="setting-head">
              <strong>${escapeHtml(settingLabel("INCLUDE_GOOGLE_RANGES"))}</strong>
              <span class="setting-badges">
                <span class="chip ${enabled ? "ok" : "warn"}">${enabled ? t("yes") : t("no")}</span>
              </span>
            </span>
            <span class="setting-control">
              <span class="toggle">
                <input type="checkbox" id="list-include-google-ranges" ${enabled ? "checked" : ""}>
                <span></span>
              </span>
            </span>
          </label>
        </div>
        <div class="google-ranges-right">
          ${statusCard}
        </div>
      </div>
    </article>
  `;
}

function renderCountriesTab() {
  const selected = selectedCountriesFromEditor();
  const cards = countryOptions.map(option => {
    const record = listSourceRecord("countries", option.code);
    const level = record ? eventLevel(record) : (selected.has(option.code) ? "warn" : "");
    return `
      <label class="country-card ${level}">
        <span class="country-card-head">
          <span class="country-card-copy">
            <strong>${escapeHtml(countryLabel(option))}</strong>
            <small>${escapeHtml(option.code)}</small>
          </span>
          <span class="toggle">
            <input type="checkbox" data-country-code="${option.code}" ${selected.has(option.code) ? "checked" : ""}>
            <span></span>
          </span>
        </span>
        <span class="country-card-body">
          ${record || selected.has(option.code) ? renderListSourceStats(record) : ""}
        </span>
      </label>`;
  }).join("");

  $("list-source-settings").innerHTML = `
    <article class="panel settings-section">
      <h2>${escapeHtml(listLabels.countries)}</h2>
      <p class="muted">${escapeHtml(t("listHintCountries"))}</p>
      <div class="country-grid">
        ${cards}
      </div>
    </article>
  `;
}

function deriveUrlSourceName(url) {
  try {
    const parsed = new URL(url);
    const fileName = parsed.pathname.split("/").filter(Boolean).pop() || "";
    return fileName ? `${parsed.hostname} · ${fileName}` : parsed.hostname;
  } catch {
    return String(url || "").trim();
  }
}

function parseNamedUrlSourceLine(value) {
  const raw = String(value || "").trim();
  if (!raw || raw.startsWith("#")) return null;
  const separator = raw.indexOf("|");
  if (separator >= 0 && !/^[a-z][a-z0-9+.-]*:\/\//i.test(raw)) {
    const name = raw.slice(0, separator).trim();
    const url = raw.slice(separator + 1).trim();
    if (!url) return null;
    return {name: name || deriveUrlSourceName(url), url, explicitName: Boolean(name)};
  }
  return {name: deriveUrlSourceName(raw), url: raw, explicitName: false};
}

function serializeNamedUrlSource(name, url) {
  const cleanName = String(name || "").replaceAll("|", "-").trim();
  const cleanUrl = String(url || "").trim();
  return cleanName ? `${cleanName} | ${cleanUrl}` : cleanUrl;
}

function currentDomainListUrlContent() {
  return listState.domainListUrlDraftContent;
}

function domainListUrlLines(content = currentDomainListUrlContent()) {
  return parseListLines(content).filter(line => line.active);
}

async function loadDomainListUrls() {
  const data = await api("/api/lists/domain-list-urls");
  listState.domainListUrlSavedContent = data.content || "";
  listState.domainListUrlDraftContent = listState.domainListUrlSavedContent;
  listState.domainListUrlSavedPath = data.path || "";
  listState.domainListUrlDirty = false;
}

function domainListSourceCardsHtml(content = currentDomainListUrlContent()) {
  const lines = domainListUrlLines(content);
  return lines.length ? lines.map(line => {
    const entry = parseNamedUrlSourceLine(line.value);
    if (!entry) return "";
    const record = listSourceRecord("domain-list-urls", line.value);
    const level = record ? eventLevel(record) : "warn";
    return `
      <article class="list-card ${level}">
        <div class="list-card-head domain-list-card-head">
          <div class="named-url-card-copy">
            <strong>${escapeHtml(entry.name)}</strong>
            <small title="${escapeHtml(entry.url)}">${escapeHtml(entry.url)}</small>
          </div>
          <div class="list-card-actions">
            <button type="button" class="icon-button list-edit-btn" data-domain-list-edit-index="${line.index}" title="${t("editItem")}" aria-label="${t("editItem")}">
              <i data-lucide="square-pen"></i>
            </button>
            <button type="button" class="icon-button list-remove-btn" data-domain-list-remove-index="${line.index}" title="${t("remove")}" aria-label="${t("remove")}">
              <i data-lucide="trash-2"></i>
            </button>
          </div>
        </div>
        ${renderListSourceStats(record)}
      </article>`;
  }).join("") : `<div class="muted-box">${t("domainListEmpty")}</div>`;
}

function refreshDomainListSourceCards() {
  const container = document.querySelector(".domain-list-url-cards");
  if (!container) return;
  container.innerHTML = domainListSourceCardsHtml();
  renderIcons();
}

function renderDomainListSourcesPanel() {
  const content = currentDomainListUrlContent();
  const wasOpen = Boolean(document.querySelector(".domain-list-url-raw")?.open);
  listState.domainListUrlDraftContent = content;

  $("list-source-settings").innerHTML = `
    <article class="panel settings-section domain-list-source-panel">
      <div class="domain-list-source-head">
        <div>
          <h2>${escapeHtml(t("domainListSources"))}</h2>
          <p class="muted">${escapeHtml(t("listHintDomainListUrls"))}</p>
        </div>
        <span class="chip">URL → domains → DNS → /32</span>
      </div>
      <form id="domain-list-url-form" class="inline-form domain-list-url-form">
        <input id="domain-list-name-input" type="text" autocomplete="off" placeholder="${escapeHtml(t("domainListName"))} (${escapeHtml(t("optional"))})">
        <input id="domain-list-url-input" type="url" autocomplete="off" placeholder="${escapeHtml(t("domainListUrl"))}: https://example.com/list.txt">
        <button type="submit">
          <i data-lucide="${listState.domainListEditIndex === null ? "plus" : "save"}"></i>
          <span>${escapeHtml(listState.domainListEditIndex === null ? t("addSource") : t("save"))}</span>
        </button>
        <button type="button" id="cancel-domain-list-edit-btn" class="${listState.domainListEditIndex === null ? "hidden" : ""}" title="${escapeHtml(t("cancel"))}" aria-label="${escapeHtml(t("cancel"))}">
          <i data-lucide="x"></i>
        </button>
      </form>
      <div class="list-tiles domain-list-url-cards">${domainListSourceCardsHtml(content)}</div>
      <details class="raw-list-editor domain-list-url-raw">
        <summary>${escapeHtml(t("domainListRawEditor"))}</summary>
        <textarea id="domain-list-url-editor" spellcheck="false">${escapeHtml(content)}</textarea>
        <div class="editor-actions">
          <button type="button" id="save-domain-list-urls-btn" ${listState.domainListUrlDirty ? "" : "disabled"}>
            <i data-lucide="save"></i><span>${escapeHtml(t("save"))}</span>
          </button>
        </div>
      </details>
      <p id="domain-list-url-status" class="${listState.domainListUrlDirty ? "status-warn" : ""}">${escapeHtml(listState.domainListUrlDirty ? t("unsavedChanges") : listState.domainListUrlSavedPath)}</p>
    </article>`;
  const rawEditor = document.querySelector(".domain-list-url-raw");
  if (rawEditor && wasOpen) rawEditor.open = true;
  renderIcons();
}

async function saveDomainListUrls() {
  const editor = $("domain-list-url-editor");
  let content = editor ? editor.value : listState.domainListUrlDraftContent;
  if (content && !content.endsWith("\n")) content += "\n";
  listState.domainListUrlDraftContent = content;
  try {
    const result = await api("/api/lists/domain-list-urls", {
      method: "PUT",
      body: JSON.stringify({content})
    });
    listState.domainListUrlSavedContent = content;
    listState.domainListUrlDraftContent = content;
    listState.domainListUrlDirty = false;
    renderDomainListSourcesPanel();
    const status = $("domain-list-url-status");
    if (status) {
      status.textContent = `${t("saved")}: ${result.bytes} bytes${result.backup ? ` · ${t("backupSaved")}: ${result.backup}` : ""}`;
      setStatusTone(status, "ok");
    }
    return true;
  } catch (err) {
    const status = $("domain-list-url-status");
    if (status) {
      status.textContent = `${t("failed")}: ${typeof err === "string" ? err : (err.error || err.message || "request failed")}`;
      setStatusTone(status, "fail");
    }
    return false;
  }
}

function startDomainListEdit(index) {
  const line = parseListLines(currentDomainListUrlContent()).find(item => item.index === index && item.active);
  const entry = line ? parseNamedUrlSourceLine(line.value) : null;
  if (!entry) return;
  listState.domainListEditIndex = index;
  renderDomainListSourcesPanel();
  $("domain-list-name-input").value = entry.explicitName ? entry.name : "";
  $("domain-list-url-input").value = entry.url;
  $("domain-list-url-input").focus();
}

function cancelDomainListEdit() {
  listState.domainListEditIndex = null;
  renderDomainListSourcesPanel();
}

async function addDomainListUrl(value, name = "") {
  const url = String(value || "").trim();
  if (!url) return;
  const item = serializeNamedUrlSource(name, url);
  const content = currentDomainListUrlContent();
  const lines = String(content).split(/\r?\n/).filter((line, index, all) => index < all.length - 1 || line.trim());
  const duplicate = lines.some((line, index) =>
    index !== listState.domainListEditIndex && parseNamedUrlSourceLine(line)?.url === url
  );
  if (duplicate) {
    const status = $("domain-list-url-status");
    if (status) {
      status.textContent = t("noChanges");
      setStatusTone(status, "warn");
    }
    return;
  }
  if (listState.domainListEditIndex === null) {
    lines.push(item);
  } else {
    lines[listState.domainListEditIndex] = item;
  }
  listState.domainListEditIndex = null;
  listState.domainListUrlDraftContent = `${lines.join("\n")}\n`;
  listState.domainListUrlDirty = listState.domainListUrlDraftContent !== listState.domainListUrlSavedContent;
  renderDomainListSourcesPanel();
  await saveDomainListUrls();
}

async function removeDomainListUrl(index) {
  const lines = String(currentDomainListUrlContent()).split(/\r?\n/);
  lines.splice(index, 1);
  listState.domainListUrlDraftContent = lines.join("\n");
  listState.domainListUrlDirty = listState.domainListUrlDraftContent !== listState.domainListUrlSavedContent;
  renderDomainListSourcesPanel();
  await saveDomainListUrls();
}

function renderListSourceStats(record) {
  if (!record) {
    return `
      <div class="list-card-stats">
        <span class="chip warn">${t("notSeen")}</span>
      </div>`;
  }
  const stats = [
    record.bytes != null ? `${t("downloaded")}: ${formatBytes(record.bytes)}` : "",
    record.domains != null ? `${t("domains")}: ${record.domains}` : "",
    record.resolved_domains != null ? `${t("resolvedDomains")}: ${record.resolved_domains}` : "",
    record.skipped_domains ? `${t("skippedDomains")}: ${record.skipped_domains}` : "",
    record.routes != null ? `${t("resolvedRoutes")}: ${record.routes}` : "",
    sourceCacheFact(record),
  ].filter(Boolean);
  return `
    <div class="list-card-stats">
      <span class="chip ${escapeHtml(record.status || "")}">${escapeHtml(record.status || "unknown")}</span>
      ${stats.map(item => `<span>${escapeHtml(item)}</span>`).join("")}
      ${record.error ? `<div class="error-inline">${escapeHtml(record.error)}</div>` : ""}
    </div>`;
}

function renderListTiles() {
  if (listState.currentList === "include-domains") {
    refreshDomainListSourceCards();
  }
  if (listState.currentList === "google-ranges") {
    $("list-tiles").classList.remove("url-source-tiles");
    $("list-tiles").innerHTML = "";
    renderGoogleRangesTab();
    renderIcons();
    return;
  }
  if (listState.currentList === "countries") {
    $("list-tiles").classList.remove("url-source-tiles");
    $("list-tiles").innerHTML = "";
    renderCountriesTab();
    renderIcons();
    return;
  }
  $("list-tiles").classList.toggle("url-source-tiles", listState.currentList === "urls");
  const lines = parseListLines($("list-editor").value);
  const active = lines.filter(line => line.active);
  const comments = lines.filter(line => line.comment);
  $("list-tiles").innerHTML = active.length ? active.map(line => {
    const record = listSourceRecord(listState.currentList, line.value);
    const level = record ? eventLevel(record) : "warn";
    const namedUrl = listState.currentList === "urls" ? parseNamedUrlSourceLine(line.value) : null;
    const title = namedUrl ? namedUrl.name : line.value;
    const subtitle = namedUrl ? namedUrl.url : "";
    return `
      <article class="list-card ${level}">
        <div class="list-card-head">
          <div class="${namedUrl ? "named-url-card-copy" : ""}">
            <strong>${escapeHtml(title)}</strong>
            ${subtitle ? `<small title="${escapeHtml(subtitle)}">${escapeHtml(subtitle)}</small>` : ""}
          </div>
          <div class="list-card-actions">
            ${namedUrl ? `
              <button type="button" class="icon-button list-edit-btn" data-edit-index="${line.index}" title="${t("editItem")}" aria-label="${t("editItem")}">
                <i data-lucide="square-pen"></i>
              </button>` : ""}
            <button class="icon-button list-remove-btn" data-remove-index="${line.index}" title="${t("remove")}" aria-label="${t("remove")}">
              <i data-lucide="trash-2"></i>
            </button>
          </div>
        </div>
        ${renderListSourceStats(record)}
      </article>`;
  }).join("") : `<div class="muted-box">${t("emptyList")}</div>`;
  if (comments.length) {
    $("list-tiles").insertAdjacentHTML("beforeend", `<div class="list-comments muted">${t("comments")}: ${comments.length}</div>`);
  }
  renderIcons();
}

function setListEditForm(entry = null, index = null) {
  listState.listEditIndex = index;
  $("add-list-name-input").value = entry?.explicitName ? entry.name : "";
  $("add-list-input").value = entry?.url || "";
  $("add-list-submit-icon").setAttribute("data-lucide", index === null ? "plus" : "save");
  $("add-list-submit-text").textContent = index === null ? t("addItem") : t("save");
  $("cancel-list-edit-btn").classList.toggle("hidden", index === null);
  renderIcons();
}

function startListEdit(index) {
  if (listState.currentList !== "urls") return;
  const line = parseListLines($("list-editor").value).find(item => item.index === index && item.active);
  const entry = line ? parseNamedUrlSourceLine(line.value) : null;
  if (!entry) return;
  setListEditForm(entry, index);
  $("add-list-input").focus();
}

async function addListItem(value, name = "") {
  const rawValue = String(value || "").trim();
  if (!rawValue) return;
  const item = listState.currentList === "urls" ? serializeNamedUrlSource(name, rawValue) : rawValue;
  const lines = $("list-editor").value.split(/\r?\n/).filter((line, index, all) => index < all.length - 1 || line.trim());
  const duplicate = listState.currentList === "urls"
    ? lines.some((line, index) => index !== listState.listEditIndex && parseNamedUrlSourceLine(line)?.url === rawValue)
    : lines.some(line => line.trim() === item);
  if (duplicate) {
    $("list-save-status").textContent = t("noChanges");
    setStatusTone($("list-save-status"), "warn");
    return;
  }
  if (listState.currentList === "urls" && listState.listEditIndex !== null) {
    lines[listState.listEditIndex] = item;
  } else {
    lines.push(item);
  }
  $("list-editor").value = `${lines.join("\n")}\n`;
  await saveList();
  setListEditForm();
}

async function removeListItem(index) {
  const lines = $("list-editor").value.split(/\r?\n/);
  lines.splice(index, 1);
  $("list-editor").value = lines.join("\n");
  await saveList();
}

async function toggleCountry(code, enabled) {
  const normalized = normalizeCountryCode(code);
  const selected = selectedCountriesFromEditor();
  if (enabled) {
    selected.add(normalized);
  } else {
    selected.delete(normalized);
  }
  const next = countryOptions
    .map(option => option.code)
    .filter(optionCode => selected.has(optionCode));
  $("list-editor").value = next.length ? `${next.join("\n")}\n` : "";
  renderListTiles();
  await saveList();
}

function bindListsEvents() {
  $("save-list-btn").addEventListener("click", saveList);
  $("add-list-form").addEventListener("submit", event => {
    event.preventDefault();
    addListItem($("add-list-input").value, $("add-list-name-input").value);
  });
  $("list-tiles").addEventListener("click", event => {
    const editButton = event.target.closest("[data-edit-index]");
    if (editButton) {
      startListEdit(Number(editButton.dataset.editIndex));
      return;
    }
    const removeButton = event.target.closest("[data-remove-index]");
    if (removeButton) {
      removeListItem(Number(removeButton.dataset.removeIndex));
    }
  });
  $("cancel-list-edit-btn").addEventListener("click", () => setListEditForm());
  $("list-source-settings").addEventListener("submit", event => {
    if (event.target.id === "domain-list-url-form") {
      event.preventDefault();
      addDomainListUrl($("domain-list-url-input")?.value || "", $("domain-list-name-input")?.value || "");
    }
  });
  $("list-source-settings").addEventListener("click", event => {
    const editButton = event.target.closest("[data-domain-list-edit-index]");
    if (editButton) {
      startDomainListEdit(Number(editButton.dataset.domainListEditIndex));
      return;
    }
    const removeButton = event.target.closest("[data-domain-list-remove-index]");
    if (removeButton) {
      removeDomainListUrl(Number(removeButton.dataset.domainListRemoveIndex));
      return;
    }
    if (event.target.closest("#cancel-domain-list-edit-btn")) {
      cancelDomainListEdit();
      return;
    }
    if (event.target.closest("#save-domain-list-urls-btn")) {
      saveDomainListUrls();
    }
  });
  $("list-source-settings").addEventListener("input", event => {
    if (event.target.id === "domain-list-url-editor") {
      listState.domainListUrlDraftContent = event.target.value;
      listState.domainListUrlDirty = listState.domainListUrlDraftContent !== listState.domainListUrlSavedContent;
      const button = $("save-domain-list-urls-btn");
      if (button) button.disabled = !listState.domainListUrlDirty;
      const status = $("domain-list-url-status");
      if (status) {
        status.textContent = listState.domainListUrlDirty ? t("unsavedChanges") : listState.domainListUrlSavedPath;
        setStatusTone(status, listState.domainListUrlDirty ? "warn" : "");
      }
    }
  });
  $("list-editor").addEventListener("keydown", event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      saveList();
    }
  });
  $("list-editor").addEventListener("input", () => {
    markListDirty($("list-editor").value !== listState.listSavedContent);
    renderListTiles();
  });
}

export {
  bindListsEvents,
  listState,
  loadList,
  normalizeAsn,
  normalizeCountryCode,
  parseListLines,
  parseNamedUrlSourceLine,
  refreshListDirtyState,
  renderDomainListSourcesPanel,
  renderListTiles,
  serializeNamedUrlSource,
  setupLists,
  toggleCountry
};
