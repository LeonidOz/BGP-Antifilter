import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import { test } from "node:test";

globalThis.localStorage = {getItem: () => "en"};
const modulesUrl = new URL("../../admin-ui/modules/", import.meta.url);
const { api } = await import(new URL("api.js", modulesUrl));
const { locale, t } = await import(new URL("i18n.js", modulesUrl));
const { escapeHtml } = await import(new URL("dom.js", modulesUrl));
const { formatDurationSeconds } = await import(new URL("format.js", modulesUrl));
const { buildStages } = await import(new URL("dashboard.js", modulesUrl));
const { runtimeGenerationState } = await import(new URL("runtime.js", modulesUrl));
const { parseListLines, parseNamedUrlSourceLine, serializeNamedUrlSource } = await import(new URL("lists.js", modulesUrl));
const { operationState, renderStoredReloadResult } = await import(new URL("operations.js", modulesUrl));

test("all feature modules resolve and their import graph has no cycles", async () => {
  const graph = new Map();
  for (const name of await readdir(modulesUrl)) {
    if (!name.endsWith(".js")) continue;
    const url = new URL(name, modulesUrl);
    const source = await readFile(url, "utf8");
    const imports = [...source.matchAll(/from\s+"(\.\.?\/[^"\n]+)"/g)].map(match => new URL(match[1], url).href);
    graph.set(url.href, imports);
    await import(url);
  }
  function visit(url, ancestors = []) {
    assert.ok(!ancestors.includes(url), `Circular import: ${[...ancestors, url].join(" -> ")}`);
    assert.ok(graph.has(url), `Feature imports outside its module graph: ${url}`);
    for (const dependency of graph.get(url)) visit(dependency, [...ancestors, url]);
  }
  for (const url of graph.keys()) visit(url);
});

test("API requests preserve credentials, JSON bodies and parsed responses", async context => {
  const requests = [];
  context.mock.method(globalThis, "fetch", async (...args) => {
    requests.push(args);
    return new Response(JSON.stringify({accepted: true}), {headers: {"Content-Type": "application/json"}});
  });
  assert.deepEqual(await api("/api/actions/reload", {method: "POST", body: "{}"}), {accepted: true});
  assert.deepEqual(requests, [["/api/actions/reload", {
    credentials: "same-origin", headers: {"Content-Type": "application/json"}, method: "POST", body: "{}",
  }]]);
});

test("API requests preserve text and structured error payloads", async context => {
  context.mock.method(globalThis, "fetch", async () => new Response("route 192.0.2.0/24 blackhole;"));
  assert.equal(await api("/api/routes"), "route 192.0.2.0/24 blackhole;");
  globalThis.fetch = async () => new Response(JSON.stringify({error: "reload already running"}), {
    status: 409, headers: {"Content-Type": "application/json"},
  });
  await assert.rejects(api("/api/actions/reload"), error => error.error === "reload already running");
});

test("translations and duration formatting follow the selected language", () => {
  locale.lang = "en";
  assert.equal(t("unsavedChanges"), "Unsaved changes");
  assert.equal(formatDurationSeconds(3660), "1 h 1 m");
  locale.lang = "ru";
  assert.equal(t("unsavedChanges"), "Есть несохраненные изменения");
  assert.equal(formatDurationSeconds(3660), "1 ч 1 мин");
  assert.equal(t("unknown-key"), "unknown-key");
  locale.lang = "en";
});

test("list parsing retains comments and original row indices for edits", () => {
  const lines = parseListLines("# comment\r\n First | https://example.test/a \r\n\r\nAS64500\n");
  assert.deepEqual(lines.map(line => [line.index, line.value, line.active, line.comment]), [
    [0, "# comment", false, true], [1, "First | https://example.test/a", true, false],
    [2, "", false, false], [3, "AS64500", true, false], [4, "", false, false],
  ]);
});

test("named URL sources distinguish labels from pipes in URL queries", () => {
  assert.deepEqual(parseNamedUrlSourceLine(" First | https://example.test/list.txt "), {
    name: "First", url: "https://example.test/list.txt", explicitName: true,
  });
  const queryUrl = "https://example.test/list.txt?source=a|b";
  assert.deepEqual(parseNamedUrlSourceLine(queryUrl), {
    name: "example.test · list.txt", url: queryUrl, explicitName: false,
  });
  assert.equal(serializeNamedUrlSource(" First | second ", " https://example.test/list "), "First - second | https://example.test/list");
  assert.equal(parseNamedUrlSourceLine("# ignored"), null);
});

test("runtime stages retain elapsed time, counts and initial startup state", context => {
  context.mock.method(Date, "now", () => 1700000042000);
  assert.equal(runtimeGenerationState({runtime: {generation_active: false}}), null);
  const payload = {runtime: {
    generation_active: true, generation_kind: "initial", generation_started_at_unix: 1700000000,
    generation_items_done: "2", generation_items_total: "5",
  }};
  const state = runtimeGenerationState(payload);
  assert.equal(state.elapsedSeconds, 42);
  assert.equal(state.initial, true);
  assert.equal(state.itemsDone, 2);
  assert.equal(state.itemsTotal, 5);
  const stages = buildStages(payload);
  assert.equal(stages.generator.level, "warn");
  assert.equal(stages.bird.level, "warn");
  assert.equal(stages.mikrotik.level, "warn");
});

test("pipeline stages preserve source failures and BGP establishment", () => {
  const stages = buildStages({status: {success: true, routes: {final: 10}, sources: [
    {status: "fresh"}, {status: "cache", cache_file: "cached"}, {status: "failed"},
  ]}, bird: {ok: true}, bgp: {stdout: "mikrotik BGP master up Established"}});
  assert.equal(stages.sources.level, "fail");
  assert.equal(stages.cache.level, "fail");
  assert.equal(stages.generator.level, "ok");
  assert.equal(stages.bird.level, "ok");
  assert.equal(stages.mikrotik.level, "ok");
});

test("an old or active reload result cannot replace a pending operation", () => {
  operationState.pendingReloadStartedAtUnix = 200;
  assert.equal(renderStoredReloadResult({reload_result: {started_at_unix: 199, active: false}}), "");
  assert.equal(renderStoredReloadResult({reload_result: {started_at_unix: 201, active: true}}), "");
  const html = renderStoredReloadResult({reload_result: {
    started_at_unix: 201, active: false, ok: true, returncode: 0, stdout: "done <script>", duration_seconds: 1,
  }});
  assert.match(html, /Command completed/);
  assert.match(html, /&lt;script&gt;/);
  operationState.pendingReloadStartedAtUnix = 0;
});

test("rendered text escapes HTML and attribute delimiters", () => {
  assert.equal(escapeHtml('<img src="x"> &'), "&lt;img src=&quot;x&quot;&gt; &amp;");
});
