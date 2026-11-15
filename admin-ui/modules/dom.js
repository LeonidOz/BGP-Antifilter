// DOM helpers, icon refresh and preservation of expanded/scrolled content.
import { t } from "./i18n.js";


function $(id) { return document.getElementById(id); }

function setStatusTone(element, tone = "") {
  element.classList.remove("status-ok", "status-warn", "status-fail");
  if (tone) {
    element.classList.add(`status-${tone}`);
  }
}

function renderIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function copyControl(value) {
  return `<button type="button" class="copy-button" data-copy="${escapeHtml(value)}" aria-label="${t("copy")}: ${escapeHtml(value)}" title="${t("copy")}"><i data-lucide="copy"></i></button>`;
}

function downloadText(text, name, type = "text/plain;charset=utf-8") {
  const url = URL.createObjectURL(new Blob([text], {type}));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function copyText(value) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  // Clipboard API is unavailable on the HTTP addresses used by LAN installs.
  const active = document.activeElement;
  const field = document.createElement("textarea");
  field.value = value;
  field.readOnly = true;
  field.style.cssText = "position:fixed;top:0;left:0;opacity:0;pointer-events:none;font-size:16px";
  document.body.append(field);
  try {
    field.focus({preventScroll: true});
    field.select();
    if (!document.execCommand("copy")) throw new Error("Copy failed");
  } finally {
    field.remove();
    active?.focus({preventScroll: true});
  }
}

function bindCopyEvents() {
  document.addEventListener("click", async event => {
    const button = event.target.closest("[data-copy]");
    if (!button) return;
    try {
      await copyText(button.dataset.copy);
      button.title = t("copied");
      button.setAttribute("aria-label", t("copied"));
      button.innerHTML = `<span role="status">${t("copied")}</span>`;
    } catch {
      button.title = t("copyFailed");
      button.innerHTML = `<span role="status">${t("copyFailed")}</span>`;
    }
  });
}

function captureContainerState(container) {
  if (!container) return {detailsOpen: [], scrollables: []};
  const scrollSelectors = [
    ".source-detail-list",
    ".timeline",
    ".data-table",
    ".route-lines",
    ".route-table",
    ".text-lines",
  ];
  return {
    detailsOpen: Array.from(container.querySelectorAll("details")).map(item => item.open),
    scrollables: scrollSelectors.flatMap(selector =>
      Array.from(container.querySelectorAll(selector)).map((item, index) => ({
        selector,
        index,
        top: item.scrollTop,
        left: item.scrollLeft,
      }))
    ),
  };
}

function restoreContainerState(container, state) {
  if (!container || !state) return;
  Array.from(container.querySelectorAll("details")).forEach((item, index) => {
    if (index < state.detailsOpen.length) item.open = state.detailsOpen[index];
  });
  state.scrollables.forEach(({selector, index, top, left}) => {
    const items = container.querySelectorAll(selector);
    const target = items[index];
    if (!target) return;
    target.scrollTop = top;
    target.scrollLeft = left;
  });
}

function replaceHtmlPreservingState(container, html) {
  const state = captureContainerState(container);
  container.innerHTML = html;
  restoreContainerState(container, state);
}

export { $, escapeHtml, renderIcons, replaceHtmlPreservingState, setStatusTone, copyControl, downloadText, bindCopyEvents };
