// List history and portable configuration import with a review step.
import { api } from "./api.js";
import { $, escapeHtml } from "./dom.js";
import { formatDateTime } from "./format.js";
import { t } from "./i18n.js";
import { renderErrorView } from "./results.js";

let importId = null;
let reviewedVersion = null;
let historyRequest = 0;

async function loadHistory() {
  const request = ++historyRequest;
  reviewedVersion = null;
  $("restore-list-btn").classList.add("hidden");
  $("history-review").innerHTML = "";
  const selected = $("history-list").value;
  const lists = await api("/api/lists");
  if (request !== historyRequest) return;
  $("history-list").innerHTML = Object.keys(lists).map(name => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
  if (selected && lists[selected]) $("history-list").value = selected;
  const name = $("history-list").value;
  const versions = await api(`/api/backups/lists?${new URLSearchParams({name})}`);
  if (request !== historyRequest) return;
  $("history-versions").innerHTML = versions.map(version => `<button data-history-version="${escapeHtml(version.id)}">${escapeHtml(formatDateTime(version.modified_at_unix * 1000))} · ${version.bytes} B</button>`).join("") || `<p class="muted">${t("noBackups")}</p>`;
}

function failure(error) {
  $("backup-status").innerHTML = renderErrorView(error);
}

function bindBackupEvents() {
  $("load-history-btn").addEventListener("click", () => loadHistory().catch(failure));
  $("history-list").addEventListener("change", () => loadHistory().catch(failure));
  $("history-versions").addEventListener("click", async event => {
    const version = event.target.closest("[data-history-version]")?.dataset.historyVersion;
    if (!version) return;
    reviewedVersion = null;
    $("restore-list-btn").classList.add("hidden");
    const name = $("history-list").value;
    const request = ++historyRequest;
    try {
      const data = await api(`/api/backups/list?${new URLSearchParams({name, version})}`);
      if (request !== historyRequest) return;
      reviewedVersion = {name, version, current_sha256: data.current_sha256};
      $("history-review").innerHTML = `<pre class="diff-view">${escapeHtml(data.diff || t("noChanges"))}</pre>`;
      $("restore-list-btn").classList.remove("hidden");
    } catch (err) { failure(err); }
  });
  $("restore-list-btn").addEventListener("click", async () => {
    if (!reviewedVersion) return;
    $("restore-list-btn").disabled = true;
    try {
      await api("/api/backups/list/restore", {method: "POST", body: JSON.stringify(reviewedVersion)});
      $("backup-status").textContent = t("restoredList");
      window.dispatchEvent(new Event("configuration-restored"));
      await loadHistory();
    } catch (err) { failure(err); }
    finally { $("restore-list-btn").disabled = false; }
  });
  $("config-upload").addEventListener("change", async () => {
    importId = null;
    $("restore-config-btn").classList.add("hidden");
    $("config-import-review").innerHTML = "";
    $("backup-status").textContent = "";
    const file = $("config-upload").files[0];
    if (!file) return;
    try {
      if (file.size > 7_000_000) throw new Error(t("backupTooLarge"));
      const data = await api("/api/backups/preview", {method: "POST", body: JSON.stringify({backup: JSON.parse(await file.text())})});
      importId = data.id;
      $("config-import-review").innerHTML = Object.entries(data.lists).map(([name, diff]) => `<h3>${escapeHtml(name)}</h3><pre class="diff-view">${escapeHtml(diff)}</pre>`).join("") +
        Object.entries(data.settings).map(([key, change]) => `<p><strong>${escapeHtml(key)}</strong>: ${escapeHtml(change.before)} → ${escapeHtml(change.after)}</p>`).join("");
      if (!Object.keys(data.lists).length && !Object.keys(data.settings).length) $("config-import-review").textContent = t("noChanges");
      $("restore-config-btn").classList.remove("hidden");
    } catch (err) { failure(err); }
  });
  $("restore-config-btn").addEventListener("click", async () => {
    if (!importId) return;
    $("restore-config-btn").disabled = true;
    try {
      await api("/api/backups/restore", {method: "POST", body: JSON.stringify({id: importId})});
      importId = null;
      $("restore-config-btn").classList.add("hidden");
      $("backup-status").textContent = t("restoredConfig");
      window.dispatchEvent(new Event("configuration-restored"));
      await loadHistory();
    } catch (err) { failure(err); }
    finally { $("restore-config-btn").disabled = false; }
  });
}

export { bindBackupEvents, loadHistory };
