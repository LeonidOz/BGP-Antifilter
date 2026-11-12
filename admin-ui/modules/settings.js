// Settings form, its saved values and unsaved-change tracking.
import { api } from "./api.js";
import { $, escapeHtml, renderIcons, setStatusTone } from "./dom.js";
import { locale, t } from "./i18n.js";

const settingsState = {
  settingsPayload: null,
  settingsSavedValues: {},
  settingsDirty: false,
};

const settingLabels = {
  UPDATE_INTERVAL: {ru: "Интервал автообновления", en: "Auto refresh interval"},
  CACHE_MAX_AGE: {ru: "Время жизни кеша", en: "Cache lifetime"},
  FETCH_TIMEOUT: {ru: "Таймаут загрузки", en: "Fetch timeout"},
  FETCH_ATTEMPTS: {ru: "Попыток загрузки", en: "Fetch attempts"},
  FETCH_RETRY_DELAY: {ru: "Пауза между попытками", en: "Retry delay"},
  DNS_RESOLVERS: {ru: "Пользовательские DNS", en: "Custom DNS resolvers"},
  DNS_RESOLVE_TIMEOUT: {ru: "Таймаут DNS-запроса", en: "DNS query timeout"},
  INCLUDE_GOOGLE_RANGES: {ru: "Добавлять Google ranges", en: "Include Google ranges"},
  MIN_PREFIX_LENGTH: {ru: "Минимальная длина префикса", en: "Minimum prefix length"},
  ALLOW_BROAD_ROUTES: {ru: "Разрешить широкие маршруты", en: "Allow broad routes"},
  MY_AS: {ru: "AS контейнера", en: "Local AS"},
  MT_AS: {ru: "AS MikroTik", en: "MikroTik AS"},
  MT_IP: {ru: "IP MikroTik", en: "MikroTik IP"},
  BIRD_IP: {ru: "IP BIRD", en: "BIRD IP"},
  ROUTER_ID: {ru: "Router ID", en: "Router ID"},
  BGP_COMMUNITY: {ru: "BGP community", en: "BGP community"},
  BGP_PROTOCOL: {ru: "Имя BGP-протокола", en: "BGP protocol name"},
  HEALTHCHECK_REQUIRE_BGP: {ru: "Healthcheck требует BGP", en: "Healthcheck requires BGP"},
};

const settingsSectionLabels = {
  update: "updateSettings",
  security: "securitySettings",
  bird: "birdSettings",
};

function settingsPendingLabel(count) {
  return locale.lang === "ru"
    ? `Изменено полей: ${count}`
    : `Changed fields: ${count}`;
}

function settingsFormValues() {
  const values = {};
  document.querySelectorAll("[data-setting-key]").forEach(input => {
    values[input.dataset.settingKey] = input.type === "checkbox" ? (input.checked ? "1" : "0") : input.value;
  });
  return values;
}

function applySettingsFormValues(values) {
  document.querySelectorAll("[data-setting-key]").forEach(input => {
    const value = values[input.dataset.settingKey];
    if (value == null) return;
    if (input.type === "checkbox") {
      input.checked = value === "1";
    } else {
      input.value = value;
    }
  });
}

function changedSettingsCount() {
  const values = settingsFormValues();
  return Object.keys(values).filter(key => values[key] !== settingsState.settingsSavedValues[key]).length;
}

function refreshSettingsDirtyState(message = "", tone = "") {
  $("save-settings-btn").disabled = !settingsState.settingsDirty;
  if (message) {
    $("settings-save-status").textContent = message;
    setStatusTone($("settings-save-status"), tone);
    return;
  }
  $("settings-save-status").textContent = settingsState.settingsDirty
    ? settingsPendingLabel(changedSettingsCount())
    : (settingsState.settingsPayload?.settings_file || "");
  setStatusTone($("settings-save-status"), settingsState.settingsDirty ? "warn" : "");
}

function markSettingsDirty() {
  settingsState.settingsDirty = changedSettingsCount() > 0;
  refreshSettingsDirtyState();
}

function settingLabel(key) {
  return settingLabels[key]?.[locale.lang] || settingLabels[key]?.en || key;
}

function renderSettingInput(item) {
  const key = escapeHtml(item.key);
  if (item.type === "bool") {
    return `
      <span class="toggle">
        <input type="checkbox" data-setting-key="${key}" ${item.value === "1" ? "checked" : ""}>
        <span></span>
      </span>`;
  }
  if (item.type === "dns_list") {
    return `<textarea data-setting-key="${key}" rows="4" spellcheck="false" placeholder="1.1.1.1&#10;8.8.8.8">${escapeHtml(String(item.value || "").replaceAll(",", "\n"))}</textarea>`;
  }
  const inputType = item.type === "int" || item.type === "number" || item.type === "asn" ? "number" : "text";
  const attrs = [
    `type="${inputType}"`,
    `data-setting-key="${key}"`,
    `value="${escapeHtml(item.value)}"`,
    item.min != null ? `min="${escapeHtml(item.min)}"` : "",
    item.max != null ? `max="${escapeHtml(item.max)}"` : "",
    item.type === "number" ? `step="0.1"` : "",
  ].filter(Boolean).join(" ");
  return `<input ${attrs}>`;
}

function renderSettingCard(item, sectionItems) {
  if (item.key === "DNS_RESOLVE_TIMEOUT") {
    const hasDnsList = (sectionItems || []).some(candidate => candidate.key === "DNS_RESOLVERS");
    if (hasDnsList) {
      return "";
    }
  }
  const embeddedDnsTimeout = item.key === "DNS_RESOLVERS"
    ? (sectionItems || []).find(candidate => candidate.key === "DNS_RESOLVE_TIMEOUT")
    : null;
  return `
    <label class="setting-card">
      <span class="setting-head">
        <strong>${escapeHtml(settingLabel(item.key))}</strong>
        <span class="setting-badges">
          ${item.overridden ? `<span class="chip">${t("overridden")}</span>` : ""}
          ${item.requires_restart ? `<span class="chip warn">${t("restartRequired")}</span>` : ""}
        </span>
      </span>
      <span class="setting-control">
        ${renderSettingInput(item)}
        ${item.unit ? `<span class="unit">${escapeHtml(item.unit)}</span>` : ""}
      </span>
      ${embeddedDnsTimeout ? `
        <span class="setting-head">
          <strong>${escapeHtml(settingLabel(embeddedDnsTimeout.key))}</strong>
          <span class="setting-badges">
            ${embeddedDnsTimeout.overridden ? `<span class="chip">${t("overridden")}</span>` : ""}
            ${embeddedDnsTimeout.requires_restart ? `<span class="chip warn">${t("restartRequired")}</span>` : ""}
          </span>
        </span>
        <span class="setting-control">
          ${renderSettingInput(embeddedDnsTimeout)}
          ${embeddedDnsTimeout.unit ? `<span class="unit">${escapeHtml(embeddedDnsTimeout.unit)}</span>` : ""}
        </span>
      ` : ""}
    </label>
  `;
}

function renderSettings(data) {
  settingsState.settingsPayload = data;
  settingsState.settingsSavedValues = Object.fromEntries((data.sections || []).flatMap(section =>
    (section.items || []).map(item => [item.key, String(item.value)])
  ));
  settingsState.settingsDirty = false;
  $("settings-form").innerHTML = (data.sections || []).map(section => `
    <article class="panel settings-section">
      <h2>${escapeHtml(t(settingsSectionLabels[section.id] || section.title))}</h2>
      <div class="settings-grid">
        ${(section.items || []).map(item => renderSettingCard(item, section.items || [])).join("")}
      </div>
    </article>
  `).join("");
  refreshSettingsDirtyState();
}

async function loadSettings() {
  renderSettings(await api("/api/settings"));
  renderIcons();
}

async function saveSettings() {
  const values = settingsFormValues();
  if (!settingsState.settingsDirty) {
    refreshSettingsDirtyState(t("noChanges"), "ok");
    return true;
  }
  $("save-settings-btn").disabled = true;
  $("settings-save-status").textContent = "...";
  try {
    const result = await api("/api/settings", {
      method: "PUT",
      body: JSON.stringify({values})
    });
    renderSettings(result);
    renderIcons();
    refreshSettingsDirtyState(t("saved"), "ok");
    return true;
  } catch (err) {
    refreshSettingsDirtyState(`${t("failed")}: ${typeof err === "string" ? err : (err.error || err.message || "request failed")}`, "fail");
    return false;
  } finally {
    $("save-settings-btn").disabled = false;
  }
}

function bindSettingsEvents() {
  $("save-settings-btn").addEventListener("click", saveSettings);
  $("settings-form").addEventListener("input", () => {
    markSettingsDirty();
  });
  $("settings-form").addEventListener("change", () => {
    markSettingsDirty();
  });
}

export {
  applySettingsFormValues,
  bindSettingsEvents,
  loadSettings,
  markSettingsDirty,
  renderSettings,
  saveSettings,
  settingLabel,
  settingsFormValues,
  settingsState
};
