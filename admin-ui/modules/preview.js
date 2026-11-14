// Review an immutable route candidate and apply that exact candidate.
import { api } from "./api.js";
import { $, escapeHtml } from "./dom.js";
import { t } from "./i18n.js";
import { operationState } from "./operations.js";
import { renderErrorView } from "./results.js";

const previewState = {id: null, offset: 0, pending: false};

function renderPreview(data) {
  previewState.id = data.id;
  previewState.offset = data.offset;
  $("preview-summary").textContent = `${t("finalRoutes")}: ${data.total} · +${data.added_count} / −${data.removed_count}`;
  $("preview-diff").innerHTML = [["addedRoutes", data.added, data.added_matches], ["removedRoutes", data.removed, data.removed_matches]].map(([label, prefixes, count]) => `
    <div><h3>${t(label)} (${count})</h3><div class="route-lines">${prefixes.map(prefix => `<code>${escapeHtml(prefix)}</code>`).join("") || "—"}</div></div>`).join("");
  $("apply-preview-btn").classList.remove("hidden");
  $("apply-preview-btn").disabled = false;
  $("preview-search-form").classList.remove("hidden");
  $("preview-pages").classList.remove("hidden");
  $("preview-prev").disabled = data.offset === 0;
  $("preview-next").disabled = data.offset + data.page_size >= Math.max(data.added_matches, data.removed_matches);
  $("preview-page").textContent = `${Math.floor(data.offset / data.page_size) + 1} / ${Math.max(1, Math.ceil(Math.max(data.added_matches, data.removed_matches) / data.page_size))}`;
}

async function preparePreview() {
  if (previewState.pending) return;
  previewState.pending = true;
  previewState.id = null;
  $("prepare-preview-btn").disabled = true;
  $("apply-preview-btn").classList.add("hidden");
  $("preview-pages").classList.add("hidden");
  $("preview-search-form").classList.add("hidden");
  $("preview-diff").innerHTML = "";
  $("preview-search").value = "";
  $("preview-summary").textContent = t("preparingPreview");
  try {
    renderPreview(await api("/api/routes/preview", {method: "POST", body: "{}"}));
  } catch (err) {
    $("preview-summary").innerHTML = renderErrorView(err);
  } finally {
    previewState.pending = false;
    $("prepare-preview-btn").disabled = false;
  }
}

async function loadPage(offset) {
  if (!previewState.id || previewState.pending) return;
  previewState.pending = true;
  try {
    const query = new URLSearchParams({id: previewState.id, search: $("preview-search").value, offset: String(offset)});
    renderPreview(await api(`/api/routes/preview?${query}`));
  } catch (err) {
    $("preview-summary").innerHTML = renderErrorView(err);
    $("apply-preview-btn").disabled = true;
  } finally {
    previewState.pending = false;
  }
}

function bindPreviewEvents() {
  $("prepare-preview-btn").addEventListener("click", preparePreview);
  $("preview-search-form").addEventListener("submit", event => { event.preventDefault(); loadPage(0); });
  $("preview-prev").addEventListener("click", () => loadPage(Math.max(0, previewState.offset - 100)));
  $("preview-next").addEventListener("click", () => loadPage(previewState.offset + 100));
  $("apply-preview-btn").addEventListener("click", async () => {
    if (!previewState.id || previewState.pending) return;
    previewState.pending = true;
    $("apply-preview-btn").disabled = true;
    try {
      await api("/api/routes/apply-preview", {method: "POST", body: JSON.stringify({id: previewState.id})});
      operationState.pendingReloadOperation = true;
      operationState.pendingReloadStartedAtUnix = Math.floor(Date.now() / 1000);
      previewState.id = null;
      $("preview-summary").textContent = t("reloadStarted");
      $("apply-preview-btn").classList.add("hidden");
    } catch (err) {
      $("preview-summary").innerHTML = renderErrorView(err);
    } finally {
      previewState.pending = false;
    }
  });
}

export { bindPreviewEvents, preparePreview, renderPreview };
