// DOM helpers, icon refresh and preservation of expanded/scrolled content.


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

export { $, escapeHtml, renderIcons, replaceHtmlPreservingState, setStatusTone };
