const dict = {
  en: {
    dashboard: "Dashboard", lists: "Lists", tools: "Tools", settings: "Settings", loginTitle: "Sign in",
    login: "Login", logout: "Logout", refresh: "Refresh", routes: "Active routes", lastResult: "Generation status",
    nextUpdate: "Until auto refresh", duration: "Generation time", actions: "Actions",
    dryRun: "Validate changes", checkSources: "Check sources", reload: "Reload routes", operationLog: "Operation log",
    save: "Save", checkIp: "Check IP", checkTarget: "Check IP / domain", network: "Network", check: "Check", rawStatus: "Diagnostics", saved: "Saved",
    failed: "Failed", never: "never", loadMetrics: "Load metrics", loadRoutes: "Load routes",
    commandOk: "Command completed", commandFailed: "Command failed", returnCode: "Return code",
    stdout: "Output", stderr: "Errors", matched: "Matched", notMatched: "Not matched",
    generatedRoutes: "Generated routes", sources: "Sources", rawDetails: "Details",
    cache: "Cache", generator: "Generator", bird: "BIRD", mikrotik: "MikroTik",
    statusOk: "OK", statusWarn: "Warning", statusFail: "Failed", lastGeneration: "Last generation", birdUptime: "BIRD uptime",
    cacheHits: "Used from cache", cachedCount: "From cache", freshDownloads: "Fresh downloads", skippedSources: "Skipped sources", cacheTtl: "Cache TTL",
    noCacheUsed: "All sources were freshly loaded", cacheUsed: "Sources served from cache",
    total: "Total", fresh: "Fresh", skipped: "Skipped", failedCount: "Failed", base: "From external sources",
    include: "Added by domains and ASNs", exclude: "Exclusion prefixes loaded", invalid: "Rejected as invalid", excludeRules: "Exclusion rule hits",
    mode: "Run mode", normalRun: "Regular update", updatedAt: "Updated",
    errors: "Generation errors", noErrors: "No errors", dryRunMode: "Validation run", checkSourcesMode: "Source check",
    sourceDetails: "Source details", downloaded: "Downloaded", resolvedRoutes: "Resolved routes",
    routeMath: "Route math", routeCandidates: "Before filtering", afterExclusions: "After exclusion rules",
    collapsedRemoved: "Merged duplicates and overlaps", finalRoutes: "Final active routes",
    addItem: "Add", rawEditor: "Raw editor", remove: "Remove", notSeen: "No status yet",
    comments: "Comments", emptyList: "No entries yet", itemPlaceholder: "New entry",
    logs: "Logs", containerLogs: "Container logs", checkedAddresses: "Checked addresses",
    downloadRoutes: "Download routes.conf", restartRequired: "restart", overridden: "changed",
    updateSettings: "Update", securitySettings: "Generation safety", birdSettings: "BIRD / BGP",
    applySettings: "Apply now", applying: "Applying...", unsavedChanges: "Unsaved changes",
    noChanges: "No changes", backupSaved: "Backup", discardListChanges: "Discard unsaved list changes?",
    discardSettingsChanges: "Discard unsaved settings changes?", leavePageWarning: "You have unsaved changes.",
    loading: "Loading...", networkSummary: "Network summary", dnsResolvers: "DNS resolvers",
    customDnsResolvers: "Custom DNS", dnsQueryTimeout: "DNS timeout", systemDnsResolvers: "System DNS",
    localAddresses: "Local IPv4", primaryAddress: "Primary IPv4", hostName: "Hostname", fqdn: "FQDN",
    externalNetwork: "External IP", provider: "Provider", organization: "Organization", location: "Location",
    timezone: "Timezone", coordinates: "Coordinates", proxy: "Proxy", hosting: "Hosting", mobile: "Mobile",
    networkSettings: "BGP / admin settings", adminPort: "Admin port", rawLookup: "Raw lookup", yes: "yes", no: "no"
    ,initializing: "Starting up", updateInProgress: "Update in progress", stageRunning: "In progress",
    startupGenerationBanner: "Initial route generation is still running. The admin UI is available already, but BIRD and BGP will become ready only after startup preparation finishes.",
    refreshGenerationBanner: "Route update is running. Dashboard metrics may still show the previous completed run until this update finishes.",
    elapsed: "Elapsed", startedAt: "Started", afterStartup: "after startup", afterCurrentRun: "after current run",
    generatorBusy: "Building the final route set", birdWaitingInitial: "BIRD will start after the initial route build",
    mikrotikWaitingInitial: "BGP session will appear after BIRD startup", progress: "Progress",
    stageBootstrap: "Preparing update", stageCollectingSources: "Collecting sources", stageBuildingRoutes: "Building routes",
    stageWritingRoutes: "Writing routes.conf", stageWritingStatus: "Writing status and metrics", stageCompleted: "Completed"
    ,currentSource: "Current source", sourceUrl: "URL", sourceAsn: "ASN", sourceGoogle: "Google ranges",
    sourceIncludeDomain: "Include domain", sourceExcludeDomain: "Exclude domain", attempt: "Attempt",
    startupSnapshot: "Startup snapshot", snapshotAge: "Snapshot age", snapshotActive: "Started with previous routes",
    startupRefreshOk: "Startup refresh completed", startupRefreshFailed: "Startup refresh failed",
    lastUpdateFinished: "Finished", unknownTime: "unknown time",
    degradedState: "Degraded", degradedReason: "Degraded reason",
    updateStatus: "Updates", currentVersion: "Current version", latestVersion: "Latest version",
    publishedAt: "Published", repository: "Repository", checkUpdates: "Check for updates",
    openRelease: "Open release", updateAvailableShort: "Update available", upToDate: "Up to date",
    updateCheckFailed: "Update check failed", updateUnknown: "Unknown", latestReleaseAvailable: "A newer release is available.",
    latestReleaseNotAvailable: "This instance already runs the latest published release.",
    openUpdatesTab: "Open updates",
    applyUpdate: "Update now", updateApplying: "Updating...", updateStarting: "Starting update...",
    updaterUnavailable: "Automatic update is unavailable", updateStagePreparing: "Preparing update",
    updateStagePulling: "Pulling images", updateStageRestarting: "Restarting services",
    updateStageCompleted: "Update completed", updateStageFailed: "Update failed",
    updateRollbackOk: "Rollback completed", updateRollbackFailed: "Rollback failed",
    sourceOptions: "Source options", sourceOptionsHint: "These toggles affect which route sources are included in generation.",
    reloadStarted: "Route reload started in background",
    listHintAsns: "Add ASNs here to include all announced IPv4 prefixes of those networks.",
    listHintCountries: "Add 2-letter country codes here to load IPv4 prefixes assigned to those countries from RIPE Stat RIR data.",
    listHintGoogleRanges: "Uses Google `goog.json`, subtracts Google Cloud prefixes from `cloud.json`, and adds the remaining IPv4 prefixes. In practice this is mainly the YouTube source.",
    lastGeneratedRoutes: "Routes from last generation",
    googleRangesSourceTitle: "Google service ranges source"
  },
  ru: {
    dashboard: "Панель", lists: "Списки", tools: "Инструменты", settings: "Настройки", loginTitle: "Вход",
    login: "Войти", logout: "Выйти", refresh: "Обновить", routes: "Активные маршруты", lastResult: "Статус генерации",
    nextUpdate: "До автообновления", duration: "Время генерации", actions: "Действия",
    dryRun: "Проверить изменения", checkSources: "Проверить источники", reload: "Обновить маршруты", operationLog: "Лог операции",
    save: "Сохранить", checkIp: "Проверить IP", checkTarget: "Проверить IP / домен", network: "Сеть", check: "Проверить", rawStatus: "Диагностика", saved: "Сохранено",
    failed: "Ошибка", never: "никогда", loadMetrics: "Показать метрики", loadRoutes: "Показать маршруты",
    commandOk: "Команда выполнена", commandFailed: "Команда завершилась с ошибкой", returnCode: "Код возврата",
    stdout: "Вывод", stderr: "Ошибки", matched: "Найден", notMatched: "Не найден",
    generatedRoutes: "Маршруты", sources: "Источники", rawDetails: "Детали",
    cache: "Кеш", generator: "Генератор", bird: "BIRD", mikrotik: "MikroTik",
    statusOk: "OK", statusWarn: "Внимание", statusFail: "Ошибка", lastGeneration: "Последняя генерация", birdUptime: "Аптайм BIRD",
    cacheHits: "Использовано из кеша", cachedCount: "Из кеша", freshDownloads: "Свежие загрузки", skippedSources: "Пропущено источников", cacheTtl: "Время жизни кеша",
    noCacheUsed: "Все источники загружены свежими", cacheUsed: "Источники отданы из кеша",
    total: "Всего", fresh: "Свежие", skipped: "Пропущено", failedCount: "Ошибки", base: "Из внешних источников",
    include: "Добавлено доменами и ASN", exclude: "Загружено префиксов исключения", invalid: "Отброшено как невалидное", excludeRules: "Срабатываний исключений",
    mode: "Режим запуска", normalRun: "Обычное обновление", updatedAt: "Обновлено",
    errors: "Ошибки генерации", noErrors: "Ошибок нет", dryRunMode: "Проверка без записи", checkSourcesMode: "Проверка источников",
    sourceDetails: "Детали источников", downloaded: "Загружено", resolvedRoutes: "Найдено маршрутов",
    routeMath: "Математика маршрутов", routeCandidates: "До фильтрации", afterExclusions: "После правил исключения",
    collapsedRemoved: "Склеено дублей и пересечений", finalRoutes: "Итоговые активные маршруты",
    addItem: "Добавить", rawEditor: "Текстовый редактор", remove: "Удалить", notSeen: "Статуса пока нет",
    comments: "Комментарии", emptyList: "Записей пока нет", itemPlaceholder: "Новая запись",
    logs: "Логи", containerLogs: "Логи контейнера", checkedAddresses: "Проверенные адреса",
    downloadRoutes: "Скачать routes.conf", restartRequired: "перезапуск", overridden: "изменено",
    updateSettings: "Обновление", securitySettings: "Безопасность генерации", birdSettings: "BIRD / BGP",
    applySettings: "Применить сейчас", applying: "Применяем...", unsavedChanges: "Есть несохраненные изменения",
    noChanges: "Изменений нет", backupSaved: "Бэкап", discardListChanges: "Отбросить несохраненные изменения списка?",
    discardSettingsChanges: "Отбросить несохраненные изменения настроек?", leavePageWarning: "Есть несохраненные изменения.",
    loading: "Загрузка...", networkSummary: "Сводка сети", dnsResolvers: "DNS-резолверы",
    customDnsResolvers: "Пользовательские DNS", dnsQueryTimeout: "Таймаут DNS", systemDnsResolvers: "Системный DNS",
    localAddresses: "Локальные IPv4", primaryAddress: "Основной IPv4", hostName: "Hostname", fqdn: "FQDN",
    externalNetwork: "Внешний IP", provider: "Провайдер", organization: "Организация", location: "Локация",
    timezone: "Часовой пояс", coordinates: "Координаты", proxy: "Прокси", hosting: "Хостинг", mobile: "Мобильная сеть",
    networkSettings: "Параметры BGP / админки", adminPort: "Порт админки", rawLookup: "Сырые данные", yes: "да", no: "нет"
    ,initializing: "Идет запуск", updateInProgress: "Идет обновление", stageRunning: "В процессе",
    startupGenerationBanner: "Сейчас идет первая генерация маршрутов. Админка уже доступна, но BIRD и BGP станут готовыми только после завершения стартовой подготовки.",
    refreshGenerationBanner: "Сейчас идет обновление маршрутов. Пока оно не завершится, панель может показывать данные предыдущего успешного запуска.",
    elapsed: "Прошло", startedAt: "Запущено", afterStartup: "после запуска", afterCurrentRun: "после текущего обновления",
    generatorBusy: "Собираем итоговый набор маршрутов", birdWaitingInitial: "BIRD запустится после завершения первой генерации",
    mikrotikWaitingInitial: "BGP-сессия появится после запуска BIRD", progress: "Прогресс",
    stageBootstrap: "Подготовка обновления", stageCollectingSources: "Сбор источников", stageBuildingRoutes: "Сборка маршрутов",
    stageWritingRoutes: "Запись routes.conf", stageWritingStatus: "Запись status и metrics", stageCompleted: "Завершено"
    ,currentSource: "Текущий источник", sourceUrl: "URL", sourceAsn: "ASN", sourceGoogle: "Google ranges",
    sourceIncludeDomain: "Include domain", sourceExcludeDomain: "Exclude domain", attempt: "Попытка",
    startupSnapshot: "Стартовый snapshot", snapshotAge: "Возраст snapshot", snapshotActive: "Запуск со старыми маршрутами",
    startupRefreshOk: "Стартовый refresh завершен", startupRefreshFailed: "Стартовый refresh завершился ошибкой",
    lastUpdateFinished: "Завершено", unknownTime: "время неизвестно",
    degradedState: "Деградация", degradedReason: "Причина деградации",
    updateStatus: "Обновления", currentVersion: "Текущая версия", latestVersion: "Последняя версия",
    publishedAt: "Опубликовано", repository: "Репозиторий", checkUpdates: "Проверить обновления",
    openRelease: "Открыть релиз", updateAvailableShort: "Есть обновление", upToDate: "Актуально",
    updateCheckFailed: "Не удалось проверить обновления", updateUnknown: "Неизвестно",
    latestReleaseAvailable: "Для этой установки доступен более новый релиз.",
    latestReleaseNotAvailable: "Эта установка уже работает на последнем опубликованном релизе.",
    openUpdatesTab: "Открыть обновления",
    applyUpdate: "Обновить сейчас", updateApplying: "Идет обновление...", updateStarting: "Запускаем обновление...",
    updaterUnavailable: "Автообновление недоступно", updateStagePreparing: "Подготавливаем обновление",
    updateStagePulling: "Скачиваем образы", updateStageRestarting: "Перезапускаем сервисы",
    updateStageCompleted: "Обновление завершено", updateStageFailed: "Обновление завершилось ошибкой",
    updateRollbackOk: "Откат выполнен", updateRollbackFailed: "Откат не удался",
    sourceOptions: "Параметры источников", sourceOptionsHint: "Эти переключатели влияют на то, какие источники попадут в генерацию маршрутов.",
    reloadStarted: "Перезагрузка маршрутов запущена в фоне",
    listHintAsns: "Добавляйте сюда ASN, чтобы включать все анонсируемые IPv4-префиксы этих сетей.",
    listHintCountries: "Добавляйте сюда двухбуквенные коды стран, чтобы загружать IPv4-префиксы этих стран из RIR-данных через RIPE Stat.",
    listHintGoogleRanges: "Берутся Google `goog.json`, из них вычитаются Google Cloud префиксы из `cloud.json`, а оставшиеся IPv4-префиксы добавляются в маршруты. На практике это в основном источник для YouTube.",
    lastGeneratedRoutes: "Получено с последней генерации",
    googleRangesSourceTitle: "Источник диапазонов сервисов Google"
  }
};

let lang = localStorage.getItem("lang") || ((navigator.language || "en").startsWith("ru") ? "ru" : "en");
let currentList = "urls";
let statusTimer = null;
let lastStatusPayload = null;
let selectedStage = "sources";
let loginCanvasStarted = false;
let settingsPayload = null;
let listSavedContent = "";
let listSavedPath = "";
let listDirty = false;
let settingsSavedValues = {};
let settingsDirty = false;
let checkIpPending = false;
let loginNetworkLabels = [];
let updateStatusPayload = null;
let updateStatusTimer = null;
let pendingReloadOperation = false;
let pendingReloadStartedAtUnix = 0;
const STATUS_POLL_INTERVAL_MS = 2000;
const UPDATE_STATUS_POLL_INTERVAL_MS = 15 * 60 * 1000;
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

function t(key) { return dict[lang][key] || dict.en[key] || key; }
function $(id) { return document.getElementById(id); }

function setStatusTone(element, tone = "") {
  element.classList.remove("status-ok", "status-warn", "status-fail");
  if (tone) {
    element.classList.add(`status-${tone}`);
  }
}

function listUnsavedLabel() {
  return t("unsavedChanges");
}

function settingsPendingLabel(count) {
  return lang === "ru"
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
  return Object.keys(values).filter(key => values[key] !== settingsSavedValues[key]).length;
}

function refreshListDirtyState(message = "", tone = "") {
  $("save-list-btn").disabled = !listDirty;
  if (message) {
    $("list-save-status").textContent = message;
    setStatusTone($("list-save-status"), tone);
    return;
  }
  $("list-save-status").textContent = listDirty ? listUnsavedLabel() : listSavedPath;
  setStatusTone($("list-save-status"), listDirty ? "warn" : "");
}

function refreshSettingsDirtyState(message = "", tone = "") {
  $("save-settings-btn").disabled = !settingsDirty;
  if (message) {
    $("settings-save-status").textContent = message;
    setStatusTone($("settings-save-status"), tone);
    return;
  }
  $("settings-save-status").textContent = settingsDirty
    ? settingsPendingLabel(changedSettingsCount())
    : (settingsPayload?.settings_file || "");
  setStatusTone($("settings-save-status"), settingsDirty ? "warn" : "");
}

function markListDirty(dirty) {
  listDirty = dirty;
  refreshListDirtyState();
}

function markSettingsDirty() {
  settingsDirty = changedSettingsCount() > 0;
  refreshSettingsDirtyState();
}

function hasUnsavedChanges() {
  return listDirty || settingsDirty;
}

function applyLang() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach(el => el.textContent = t(el.dataset.i18n));
  $("lang-ru").classList.toggle("active", lang === "ru");
  $("lang-en").classList.toggle("active", lang === "en");
  if (settingsPayload && !$("settings").classList.contains("hidden")) {
    const values = settingsDirty ? settingsFormValues() : null;
    renderSettings(settingsPayload);
    if (values) {
      applySettingsFormValues(values);
      markSettingsDirty();
    }
  }
  if (!$("lists").classList.contains("hidden")) {
    renderListTiles();
  }
  refreshListDirtyState();
  renderUpdateStatus(updateStatusPayload);
  renderIcons();
}

function renderIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: {"Content-Type": "application/json", ...(options.headers || {})},
    ...options
  });
  const type = response.headers.get("content-type") || "";
  const data = type.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) throw data;
  return data;
}

function showLogin() {
  $("app-shell").classList.add("login-mode");
  $("sidebar").classList.add("hidden");
  $("login-view").classList.remove("hidden");
  $("admin-view").classList.add("hidden");
  startLoginNetworkCanvas();
}

function showAdmin() {
  $("app-shell").classList.remove("login-mode");
  $("sidebar").classList.remove("hidden");
  $("login-view").classList.add("hidden");
  $("admin-view").classList.remove("hidden");
}

function formatCountdown(ts) {
  if (!ts) return "-";
  const seconds = Math.max(0, Math.floor(ts - Date.now() / 1000));
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

function formatDateTime(value) {
  if (!value) return t("never");
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(lang === "ru" ? "ru-RU" : "en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  }).format(date);
}

function formatDurationSeconds(value) {
  if (value == null || value === "") return "-";
  const seconds = Number(value);
  if (!Number.isFinite(seconds)) return String(value);
  const units = lang === "ru"
    ? {second: "с", minute: "мин", hour: "ч", day: "дн"}
    : {second: "s", minute: "m", hour: "h", day: "d"};
  if (seconds < 60) return `${Math.round(seconds * 10) / 10}${units.second}`;
  if (seconds >= 86400) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    return hours ? `${days} ${units.day} ${hours} ${units.hour}` : `${days} ${units.day}`;
  }
  if (seconds >= 3600) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return minutes ? `${hours} ${units.hour} ${minutes} ${units.minute}` : `${hours} ${units.hour}`;
  }
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes} ${units.minute} ${rest}${units.second}`;
}

function formatSecondsShort(value) {
  if (value == null || value === "") return "-";
  return formatDurationSeconds(value);
}

function formatBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes)) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${Math.round(size * 10) / 10} ${units[unit]}`;
}

function loginCanvasSubnets() {
  const fallback = ["192.168.77.111", "192.168.55.1", "172.21.0.2", "127.0.0.1"];
  const labels = [];
  const seen = new Set();
  for (const label of (loginNetworkLabels.length ? loginNetworkLabels : fallback).filter(Boolean)) {
    const raw = String(label).trim();
    const match = raw.match(/^(\d{1,3}\.\d{1,3}\.\d{1,3})\.\d{1,3}$/);
    const text = match ? `${match[1]}.0/24` : raw;
    if (seen.has(text)) {
      continue;
    }
    seen.add(text);
    labels.push({
      raw,
      text,
    });
    if (labels.length >= 4) {
      break;
    }
  }
  const layout = [
    {x: .2, y: .28, count: 5},
    {x: .78, y: .26, count: 5},
    {x: .72, y: .76, count: 4},
    {x: .26, y: .72, count: 4},
  ];
  return layout.map((item, index) => ({
    ...item,
    label: labels[index]?.text || labels[index]?.raw || "LAN"
  }));
}

function yesNo(value) {
  return value ? t("yes") : t("no");
}

function setVersion(version) {
  const value = version ? `v${version}` : "v-";
  $("version").textContent = value;
  $("login-footer-version").textContent = value;
  $("admin-footer-version").textContent = value;
}

function updateStatusLevel(data) {
  if (!data) return "warn";
  if (data.runtime?.active) return "warn";
  if (data.runtime?.success === false) return "fail";
  if (!data.ok) return "fail";
  return data.update_available ? "warn" : "ok";
}

function updateStageLabel(stage) {
  const map = {
    preparing: "updateStagePreparing",
    pulling: "updateStagePulling",
    restarting: "updateStageRestarting",
    completed: "updateStageCompleted",
    failed: "updateStageFailed",
  };
  return t(map[stage] || "updateUnknown");
}

function renderUpdateStatus(data) {
  updateStatusPayload = data;
  const level = updateStatusLevel(data);
  const runtime = data?.runtime || {};
  $("update-pill").textContent = !data
    ? t("loading")
    : runtime.active
    ? t("updateApplying")
    : runtime.success === false
    ? t("updateStageFailed")
    : !data.ok
    ? t("updateCheckFailed")
    : data.update_available
    ? t("updateAvailableShort")
    : t("upToDate");
  $("update-pill").className = `status-pill ${level}`;
  $("update-current-version").textContent = data?.current_version ? `v${data.current_version}` : t("updateUnknown");
  $("update-latest-version").textContent = data?.latest_tag || (data?.latest_version ? `v${data.latest_version}` : t("updateUnknown"));
  $("update-published-at").textContent = data?.published_at ? formatDateTime(data.published_at) : t("never");
  let summary = !data
    ? t("loading")
    : runtime.active
    ? `${updateStageLabel(runtime.stage)}: ${runtime.target_version ? `v${runtime.target_version}` : ""}`.trim()
    : runtime.success === false
    ? `${t("updateStageFailed")}: ${runtime.error || t("failed")}`
    : !data.ok
    ? `${t("updateCheckFailed")}: ${data.error || t("failed")}`
    : data.update_available
    ? t("latestReleaseAvailable")
    : t("latestReleaseNotAvailable");
  if (runtime.success === false && runtime.rollback) {
    summary += runtime.rollback.ok ? ` · ${t("updateRollbackOk")}` : ` · ${t("updateRollbackFailed")}`;
  }
  $("update-summary").textContent = summary;
  $("update-release-link").href = data?.repository_url || "https://github.com/LeonidOz/BGP-Antifilter";
  $("open-release-link").href = data?.release_url || data?.repository_url || "https://github.com/LeonidOz/BGP-Antifilter";
  $("open-release-link").classList.toggle("hidden", !data?.ok);
  $("apply-update-btn").classList.toggle("hidden", !(data?.apply_available || runtime.active));
  $("apply-update-btn").disabled = Boolean(runtime.active) || !data?.apply_available;
  $("apply-update-btn").querySelector("span").textContent = runtime.active
    ? t("updateApplying")
    : data?.latest_tag
    ? `${t("applyUpdate")} ${data.latest_tag}`
    : t("applyUpdate");
  $("check-updates-btn").disabled = Boolean(runtime.active);
  const noticeVisible = Boolean(runtime.active) || Boolean(data?.update_available);
  $("update-notice").classList.toggle("hidden", !noticeVisible);
  $("update-notice-pill").textContent = runtime.active
    ? t("updateApplying")
    : data?.latest_tag || t("updateAvailableShort");
  $("update-notice-summary").textContent = runtime.active
    ? summary
    : data?.latest_tag
    ? `${t("latestReleaseAvailable")} ${data.latest_tag}`
    : t("latestReleaseAvailable");
}

async function loadUpdateStatus(force = false) {
  const path = force ? "/api/update/status?force=1" : "/api/update/status";
  const data = await api(path);
  renderUpdateStatus(data);
}

async function applyUpdate() {
  const version = updateStatusPayload?.latest_version;
  if (!version) return;
  $("update-summary").textContent = t("updateStarting");
  $("apply-update-btn").disabled = true;
  try {
    await api("/api/update/apply", {
      method: "POST",
      body: JSON.stringify({version})
    });
    await loadUpdateStatus(true);
  } catch (err) {
    renderUpdateStatus({
      ...(updateStatusPayload || {}),
      ok: updateStatusPayload?.ok ?? false,
      runtime: {
        active: false,
        success: false,
        stage: "failed",
        error: typeof err === "string" ? err : (err.error || err.message || "request failed"),
      },
    });
  }
}

function sourceCacheFact(source) {
  if (source.status !== "cache" || source.cache_age_seconds == null) return "";
  return `${t("cache")}: ${formatDurationSeconds(source.cache_age_seconds)}`;
}

function parseBirdTime(value) {
  const match = String(value || "").match(/(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})/);
  if (!match) return null;
  const [, year, month, day, hour, minute, second] = match.map(Number);
  return Date.UTC(year, month - 1, day, hour, minute, second) / 1000;
}

function birdUptime(stdout) {
  const text = String(stdout || "");
  const current = text.match(/Current server time is ([^\n]+)/);
  const reboot = text.match(/Last reboot on ([^\n]+)/);
  const currentTime = parseBirdTime(current?.[1]);
  const rebootTime = parseBirdTime(reboot?.[1]);
  if (currentTime == null || rebootTime == null || currentTime < rebootTime) return "-";
  return formatDurationSeconds(currentTime - rebootTime);
}

function runtimeGenerationState(payload) {
  const runtime = payload?.runtime || {};
  if (!runtime.generation_active) return null;
  const startedAt = Number(runtime.generation_started_at_unix || 0) || null;
  return {
    active: true,
    kind: runtime.generation_kind || "manual",
    initial: (runtime.generation_kind || "") === "initial",
    message: runtime.generation_message || "",
    startedAt,
    elapsedSeconds: startedAt ? Math.max(0, Math.floor(Date.now() / 1000) - startedAt) : null,
    itemsDone: Number.isFinite(Number(runtime.generation_items_done)) ? Number(runtime.generation_items_done) : null,
    itemsTotal: Number.isFinite(Number(runtime.generation_items_total)) ? Number(runtime.generation_items_total) : null,
  };
}

function runtimeGenerationLabel(state) {
  return state?.initial ? t("initializing") : t("updateInProgress");
}

function runtimeStageLabel(stage) {
  const labels = {
    "bootstrap": t("stageBootstrap"),
    "collecting-sources": t("stageCollectingSources"),
    "building-routes": t("stageBuildingRoutes"),
    "writing-routes": t("stageWritingRoutes"),
    "writing-status": t("stageWritingStatus"),
    "completed": t("stageCompleted"),
  };
  return labels[stage] || stage || t("stageRunning");
}

function runtimeSourceKindLabel(kind) {
  const labels = {
    "url": t("sourceUrl"),
    "asn": t("sourceAsn"),
    "google": t("sourceGoogle"),
    "include-domain": t("sourceIncludeDomain"),
    "exclude-domain": t("sourceExcludeDomain"),
  };
  return labels[kind] || kind || "";
}

function runtimeSnapshotChip(runtime) {
  if (!runtime?.startup_snapshot_used) return "";
  const details = [];
  const age = runtime.startup_snapshot_age_seconds;
  const size = runtime.startup_snapshot_size_bytes;
  if (age != null) details.push(`${t("snapshotAge")}: ${formatSecondsShort(age)}`);
  if (Number.isFinite(Number(size)) && Number(size) > 0) details.push(formatBytes(size));
  const label = details.length ? `${t("snapshotActive")} · ${details.join(" · ")}` : t("snapshotActive");
  return `<span class="chip warn">${escapeHtml(label)}</span>`;
}

function runtimeStartupRefreshSummary(runtime) {
  if ((runtime?.last_update_reason || "") !== "startup") return "";
  const success = runtime?.last_update_success;
  if (success == null) return "";
  const label = success ? t("startupRefreshOk") : t("startupRefreshFailed");
  const finishedAt = runtime?.last_update_finished_at_unix
    ? formatDateTime(runtime.last_update_finished_at_unix * 1000)
    : t("unknownTime");
  return `${label} · ${t("lastUpdateFinished")}: ${finishedAt}`;
}

function runtimeDegradedSummary(runtime, status) {
  const degraded = Boolean(runtime?.degraded || status?.degraded);
  if (!degraded) return "";
  const reason = runtime?.degraded_reason || status?.degraded_reason || "";
  return reason ? `${t("degradedState")} · ${t("degradedReason")}: ${reason}` : t("degradedState");
}

function renderRuntimeBanner(payload) {
  const banner = $("runtime-banner");
  const runtimeState = runtimeGenerationState(payload);
  if (!runtimeState) {
    banner.classList.add("hidden");
    banner.innerHTML = "";
    return;
  }
  const message = runtimeState.initial ? t("startupGenerationBanner") : t("refreshGenerationBanner");
  const percent = Math.max(0, Math.min(100, Number(payload?.runtime?.generation_progress_percent || 0)));
  const stageTitle = runtimeStageLabel(payload?.runtime?.generation_stage || "");
  const stageMessage = payload?.runtime?.generation_stage_message || runtimeState.message || "";
  const currentKind = payload?.runtime?.generation_current_kind || "";
  const currentName = payload?.runtime?.generation_current_name || "";
  const currentIndex = Number(payload?.runtime?.generation_current_index || 0) || null;
  const currentAttempt = Number(payload?.runtime?.generation_current_attempt || 0) || null;
  const currentAttemptTotal = Number(payload?.runtime?.generation_current_attempt_total || 0) || null;
  const snapshotChip = runtimeSnapshotChip(payload?.runtime || {});
  const itemsLabel = runtimeState.itemsDone != null && runtimeState.itemsTotal != null && runtimeState.itemsTotal > 0
    ? `${runtimeState.itemsDone} / ${runtimeState.itemsTotal}`
    : "";
  const attemptLabel = currentAttempt && currentAttemptTotal ? `${t("attempt")} ${currentAttempt}/${currentAttemptTotal}` : "";
  const currentSourceLabel = currentName
    ? `${runtimeSourceKindLabel(currentKind)}${currentIndex ? ` ${currentIndex}/${runtimeState.itemsTotal || "?"}` : ""}: ${currentName}${attemptLabel ? ` · ${attemptLabel}` : ""}`
    : "";
  const meta = [
    runtimeState.startedAt ? `<span class="chip warn">${escapeHtml(t("startedAt"))}: ${escapeHtml(formatDateTime(runtimeState.startedAt * 1000))}</span>` : "",
    runtimeState.elapsedSeconds != null ? `<span class="chip warn">${escapeHtml(t("elapsed"))}: ${escapeHtml(formatSecondsShort(runtimeState.elapsedSeconds))}</span>` : "",
    itemsLabel ? `<span class="chip warn">${escapeHtml(t("sources"))}: ${escapeHtml(itemsLabel)}</span>` : "",
    snapshotChip,
  ].filter(Boolean).join("");
  banner.innerHTML = `
    <div class="runtime-banner-head">
      <div class="runtime-banner-title">
        <i data-lucide="loader-circle"></i>
        <span>${escapeHtml(runtimeGenerationLabel(runtimeState))}</span>
      </div>
      <span class="status-pill warn">${escapeHtml(t("stageRunning"))}</span>
    </div>
    <div class="runtime-banner-body">${escapeHtml(message)}</div>
    <div class="runtime-progress">
      <div class="runtime-progress-head">
        <span>${escapeHtml(stageTitle)}${stageMessage ? ` · ${escapeHtml(stageMessage)}` : ""}</span>
        <strong>${escapeHtml(t("progress"))}: ${percent}%</strong>
      </div>
      ${currentSourceLabel ? `<div class="runtime-progress-head"><span>${escapeHtml(t("currentSource"))}: ${escapeHtml(currentSourceLabel)}</span></div>` : ""}
      <div class="runtime-progress-track"><div class="runtime-progress-bar" style="width:${percent}%"></div></div>
    </div>
    ${meta ? `<div class="runtime-banner-meta">${meta}</div>` : ""}
  `;
  banner.classList.remove("hidden");
  renderIcons();
}

function startLoginNetworkCanvas() {
  if (loginCanvasStarted) return;
  const canvas = $("login-network-canvas");
  if (!canvas) return;
  loginCanvasStarted = true;

  const ctx = canvas.getContext("2d");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let width = 0;
  let height = 0;
  let dpr = 1;
  let frame = 0;
  let animationId = null;
  let nodes = [];
  let packets = [];
  const pointer = {x: 0, y: 0, active: false};
  const hubTarget = {x: 0, y: 0};

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = canvas.clientWidth;
    height = canvas.clientHeight;
    canvas.width = Math.max(1, Math.floor(width * dpr));
    canvas.height = Math.max(1, Math.floor(height * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    createTopology();
  }

  function createTopology() {
    const subnets = loginCanvasSubnets();
    const centerX = width * .5;
    const centerY = height * .5;
    pointer.x = pointer.x || centerX;
    pointer.y = pointer.y || centerY;
    hubTarget.x = centerX;
    hubTarget.y = centerY;
    nodes = [{x: centerX, y: centerY, baseX: centerX, baseY: centerY, r: 13, label: "", hub: true, pulse: Math.random() * 10}];
    for (const subnet of subnets) {
      const gatewayX = width * subnet.x;
      const gatewayY = height * subnet.y;
      nodes.push({x: gatewayX, y: gatewayY, baseX: gatewayX, baseY: gatewayY, r: 10, label: subnet.label, gateway: true, pulse: Math.random() * 10});
      for (let i = 0; i < subnet.count; i += 1) {
        const angle = (Math.PI * 2 * i) / subnet.count + .32;
        const radius = 54 + (i % 2) * 26;
        const nodeX = width * subnet.x + Math.cos(angle) * radius;
        const nodeY = height * subnet.y + Math.sin(angle) * radius;
        nodes.push({
          x: nodeX,
          y: nodeY,
          baseX: nodeX,
          baseY: nodeY,
          r: 4 + (i % 3),
          label: "",
          gateway: false,
          pulse: Math.random() * 10
        });
      }
    }
    packets = Array.from({length: Math.max(8, Math.floor(width / 120))}, (_, index) => ({
      from: 0,
      to: 1 + (index % (nodes.length - 1)),
      progress: Math.random(),
      speed: .0028 + Math.random() * .0032,
      color: index % 3 === 0 ? "#55d987" : index % 3 === 1 ? "#3dd6ff" : "#f3bd4d"
    }));
  }

  function setPointer(clientX, clientY, active = true) {
    const rect = canvas.getBoundingClientRect();
    pointer.x = clientX - rect.left;
    pointer.y = clientY - rect.top;
    pointer.active = active;
  }

  function releasePointer() {
    pointer.active = false;
  }

  function updateTopology() {
    const hub = nodes[0];
    const targetX = pointer.active ? pointer.x : width * .5;
    const targetY = pointer.active ? pointer.y : height * .5;
    const maxRadius = Math.min(width, height) * .22;
    const dx = targetX - width * .5;
    const dy = targetY - height * .5;
    const distance = Math.hypot(dx, dy) || 1;
    const scale = Math.min(distance, maxRadius) / distance;
    hubTarget.x = width * .5 + dx * scale;
    hubTarget.y = height * .5 + dy * scale;
    hub.x += (hubTarget.x - hub.x) * .075;
    hub.y += (hubTarget.y - hub.y) * .075;

    nodes.slice(1).forEach((node, index) => {
      const wave = Math.sin(frame * .018 + node.pulse) * (node.gateway ? 4 : 7);
      const pullX = (hub.x - width * .5) * (node.gateway ? -.035 : -.055);
      const pullY = (hub.y - height * .5) * (node.gateway ? -.035 : -.055);
      const angle = Math.atan2(node.baseY - hub.y, node.baseX - hub.x);
      node.x += (node.baseX + Math.cos(angle) * wave + pullX - node.x) * .045;
      node.y += (node.baseY + Math.sin(angle) * wave + pullY - node.y) * .045;
      if (pointer.active && index % 5 === 0) {
        const pdx = node.x - pointer.x;
        const pdy = node.y - pointer.y;
        const pd = Math.hypot(pdx, pdy) || 1;
        if (pd < 150) {
          node.x += (pdx / pd) * (150 - pd) * .012;
          node.y += (pdy / pd) * (150 - pd) * .012;
        }
      }
    });
  }

  function line(from, to, alpha = .25) {
    ctx.strokeStyle = `rgba(61, 214, 255, ${alpha})`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    const midX = (from.x + to.x) / 2;
    const midY = (from.y + to.y) / 2;
    ctx.quadraticCurveTo(midX, midY - 24, to.x, to.y);
    ctx.stroke();
  }

  function draw() {
    frame += 1;
    updateTopology();
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "rgba(7, 16, 23, .76)";
    ctx.fillRect(0, 0, width, height);

    ctx.strokeStyle = "rgba(61, 214, 255, .055)";
    ctx.lineWidth = 1;
    for (let x = (frame * .18) % 34; x < width; x += 34) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = (frame * .12) % 34; y < height; y += 34) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    const hub = nodes[0];
    nodes.slice(1).forEach((node, index) => {
      if (node.gateway || index % 3 === 0) line(hub, node, node.gateway ? .28 : .1);
    });
    for (let i = 1; i < nodes.length - 1; i += 1) {
      if (i % 4 === 0) line(nodes[i], nodes[i + 1], .1);
    }

    packets.forEach(packet => {
      const from = nodes[packet.from];
      const to = nodes[packet.to];
      packet.progress += packet.speed * (reduceMotion ? .35 : 1);
      if (packet.progress > 1) {
        packet.progress = 0;
        packet.to = 1 + Math.floor(Math.random() * (nodes.length - 1));
      }
      const x = from.x + (to.x - from.x) * packet.progress;
      const y = from.y + (to.y - from.y) * packet.progress - Math.sin(packet.progress * Math.PI) * 18;
      ctx.fillStyle = packet.color;
      ctx.shadowColor = packet.color;
      ctx.shadowBlur = 16;
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
    });

    nodes.forEach(node => {
      const pulse = .5 + Math.sin(frame * .035 + node.pulse) * .5;
      ctx.fillStyle = node.hub ? "#dffaff" : node.gateway ? "#55d987" : "#3dd6ff";
      ctx.shadowColor = node.gateway ? "#55d987" : "#3dd6ff";
      ctx.shadowBlur = node.hub ? 26 : 13;
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.r + pulse * (node.hub ? 3 : 1.4), 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
      if (node.label) {
        ctx.font = node.hub ? "700 13px Inter, Segoe UI, sans-serif" : "600 11px Inter, Segoe UI, sans-serif";
        ctx.fillStyle = node.hub ? "#e5f2ff" : "rgba(229, 242, 255, .68)";
        ctx.fillText(node.label, node.x + 15, node.y - 11);
      }
    });

    animationId = requestAnimationFrame(draw);
  }

  window.addEventListener("resize", resize);
  window.addEventListener("pointermove", event => setPointer(event.clientX, event.clientY));
  window.addEventListener("pointerleave", releasePointer);
  window.addEventListener("blur", releasePointer);
  resize();
  draw();
  document.addEventListener("visibilitychange", () => {
    if (document.hidden && animationId) {
      cancelAnimationFrame(animationId);
      animationId = null;
    } else if (!document.hidden && !animationId) {
      animationId = requestAnimationFrame(draw);
    }
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

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

function renderStoredReloadResult(payload) {
  const result = payload?.reload_result;
  if (!result || result.active || !result.started_at_unix) return "";
  if (pendingReloadStartedAtUnix && result.started_at_unix < pendingReloadStartedAtUnix) return "";
  return renderCommandResult("reload", result);
}

function renderCompletedReloadOperation(payload) {
  const runtime = payload?.runtime || {};
  const status = payload?.status || {};
  const finishedAt = Number(runtime.last_update_finished_at_unix || 0) || 0;
  const updatedAt = Number(status.updated_at_unix || 0) || 0;
  const completedAt = Math.max(finishedAt, updatedAt);
  if (!completedAt || completedAt < pendingReloadStartedAtUnix) return "";

  const success = runtime.last_update_success === true && !runtime.degraded && status.success !== false;
  const degraded = runtime.degraded || status.degraded;
  const pillClass = success ? "ok" : degraded ? "warn" : "fail";
  const title = success ? t("commandOk") : t("commandFailed");
  const runReason = runtime.last_update_reason || status.run_reason || "manual";
  const runMessage = status.run_message || runtime.last_update_message || "";
  const degradedReason = status.degraded_reason || runtime.degraded_reason || "";
  const sources = Array.isArray(status.sources) ? status.sources : [];
  const errors = Array.isArray(status.errors) ? status.errors : [];

  return `
    <div class="result-card">
      <div class="result-head">
        <span class="status-pill ${pillClass}">${escapeHtml(title)}</span>
        <span class="chip">${escapeHtml(runReason)}</span>
      </div>
      <div class="kv-grid">
        <div class="kv"><span>${t("lastUpdateFinished")}</span><strong>${escapeHtml(formatDateTime(finishedAt || updatedAt) || t("unknownTime"))}</strong></div>
        <div class="kv"><span>${t("duration")}</span><strong>${escapeHtml(formatSecondsShort(status.duration_seconds))}</strong></div>
        <div class="kv"><span>${t("sources")}</span><strong>${escapeHtml(`${sources.length}`)}</strong></div>
      </div>
      ${runMessage ? `<div class="text-lines"><div class="text-line">${escapeHtml(runMessage)}</div></div>` : ""}
      ${degradedReason ? `<div class="error-inline">${escapeHtml(degradedReason)}</div>` : ""}
      ${sources.length ? `<details open><summary>${t("sourceDetails")}</summary>${renderSourceDetails(sources)}</details>` : ""}
      ${errors.length ? `<details open><summary>${t("errors")}</summary>${renderDataTree(errors)}</details>` : ""}
    </div>`;
}

function renderActiveOperationLog(payload) {
  const runtime = payload?.runtime || {};
  const status = payload?.status || {};
  const runtimeState = runtimeGenerationState(payload);
  if (!runtimeState) return "";
  const stageTitle = runtimeStageLabel(runtime.generation_stage || "");
  const stageMessage = runtime.generation_stage_message || runtimeState.message || "";
  const currentKind = runtime.generation_current_kind || "";
  const currentName = runtime.generation_current_name || "";
  const currentIndex = Number(runtime.generation_current_index || 0) || null;
  const currentAttempt = Number(runtime.generation_current_attempt || 0) || null;
  const currentAttemptTotal = Number(runtime.generation_current_attempt_total || 0) || null;
  const itemsLabel = runtimeState.itemsDone != null && runtimeState.itemsTotal != null && runtimeState.itemsTotal > 0
    ? `${runtimeState.itemsDone} / ${runtimeState.itemsTotal}`
    : "";
  const sourceLabel = currentName
    ? `${runtimeSourceKindLabel(currentKind)}${currentIndex ? ` ${currentIndex}/${runtimeState.itemsTotal || "?"}` : ""}: ${currentName}${currentAttempt && currentAttemptTotal ? ` · ${t("attempt")} ${currentAttempt}/${currentAttemptTotal}` : ""}`
    : "";
  const sources = Array.isArray(status.sources) ? status.sources : [];
  const errors = Array.isArray(status.errors) ? status.errors : [];
  return `
    <div class="result-card">
      <div class="result-head">
        <span class="status-pill warn">${escapeHtml(t("applying"))}</span>
        <span class="chip">${escapeHtml(runtime.generation_kind || "reload")}</span>
      </div>
      <div class="kv-grid">
        <div class="kv"><span>${escapeHtml(t("stageRunning"))}</span><strong>${escapeHtml(stageTitle)}</strong></div>
        ${runtimeState.elapsedSeconds != null ? `<div class="kv"><span>${escapeHtml(t("elapsed"))}</span><strong>${escapeHtml(formatSecondsShort(runtimeState.elapsedSeconds))}</strong></div>` : ""}
        ${itemsLabel ? `<div class="kv"><span>${escapeHtml(t("sources"))}</span><strong>${escapeHtml(itemsLabel)}</strong></div>` : ""}
      </div>
      ${stageMessage ? `<div class="text-lines"><div class="text-line">${escapeHtml(stageMessage)}</div></div>` : ""}
      ${sourceLabel ? `<div class="timeline-summary"><span class="chip warn">${escapeHtml(t("currentSource"))}: ${escapeHtml(sourceLabel)}</span></div>` : ""}
      ${sources.length ? `<details open><summary>${t("sourceDetails")}</summary>${renderSourceDetails(sources)}</details>` : ""}
      ${errors.length ? `<details open><summary>${t("errors")}</summary>${renderDataTree(errors)}</details>` : ""}
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
  if (status === "cache" || status === "skipped" || status === "disabled" || message.includes("skipping")) return "warn";
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

function renderMetricsView(text) {
  const labels = {
    bgp_antifilter_routes_total: lang === "ru" ? "Активные маршруты" : "Active routes",
    bgp_antifilter_last_update_timestamp_seconds: lang === "ru" ? "Время последнего обновления" : "Last update time",
    bgp_antifilter_update_success: lang === "ru" ? "Последняя генерация успешна" : "Last update success",
    bgp_antifilter_update_duration_seconds: lang === "ru" ? "Время генерации" : "Update duration",
    bgp_antifilter_invalid_entries_total: lang === "ru" ? "Невалидные записи" : "Invalid entries",
    bgp_antifilter_exclude_rules_applied_total: lang === "ru" ? "Срабатывания исключений" : "Exclusion rule hits",
    bgp_antifilter_source_status_total: lang === "ru" ? "Источники по статусам" : "Sources by status",
    bgp_antifilter_source_cache_age_seconds: lang === "ru" ? "Возраст использованного кеша" : "Used cache age",
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
  const runtime = lastStatusPayload?.runtime || {};
  const status = lastStatusPayload?.status || {};
  const snapshotSummary = runtime?.startup_snapshot_used
    ? `${t("startupSnapshot")}: ${formatSecondsShort(runtime.startup_snapshot_age_seconds)}`
    : "";
  const runtimeSummary = runtimeStartupRefreshSummary(runtime);
  const degradedSummary = runtimeDegradedSummary(runtime, status);
  const extraSummary = [snapshotSummary, runtimeSummary, degradedSummary].filter(Boolean);
  return `
    <div class="result-card">
      <div class="result-head"><span class="status-pill ok">${rows.length} ${lang === "ru" ? "значимых метрик" : "non-zero metrics"}</span></div>
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
    return value === 1 ? (lang === "ru" ? "да" : "yes") : (lang === "ru" ? "нет" : "no");
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

function sourceCounts(sources = []) {
  return sources.reduce((acc, source) => {
    acc[source.status] = (acc[source.status] || 0) + 1;
    return acc;
  }, {});
}

function stageState(level, title, subtitle, rows, raw) {
  return {level, title, subtitle, rows, raw};
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

function rowLevel(key) {
  const normalized = String(key).toLowerCase();
  if (["fresh", "свежие", "ok"].includes(normalized)) return "ok";
  if (["skipped", "пропущено", "cache", "попадания в кеш", "invalid", "невалидные"].includes(normalized)) return "warn";
  if (["failed", "ошибки", "stderr"].includes(normalized)) return "fail";
  return "";
}

function buildStages(payload) {
  const status = payload?.status || {};
  const runtimeState = runtimeGenerationState(payload);
  const sources = status.sources || [];
  const counts = sourceCounts(sources);
  const routes = status.routes || {};
  const birdOk = payload?.bird?.ok;
  const bgpText = payload?.bgp?.stdout || "";
  const bgpOk = bgpText.includes("Established");
  const failed = counts.failed || 0;
  const skipped = counts.skipped || 0;
  const cached = counts.cache || 0;

  return {
    sources: stageState(
      failed ? "fail" : skipped || cached ? "warn" : "ok",
      t("sources"),
      `${sources.length} ${t("total").toLowerCase()} · ${counts.fresh || 0} ${t("fresh").toLowerCase()} · ${cached} ${t("cachedCount").toLowerCase()} · ${skipped} ${t("skipped").toLowerCase()} · ${failed} ${t("failedCount").toLowerCase()}`,
      [
        [t("fresh"), counts.fresh || 0],
        [t("cachedCount"), cached],
        [t("skipped"), skipped],
        [t("failedCount"), failed],
      ],
      sources
    ),
    cache: stageState(
      failed ? "fail" : "ok",
      t("cache"),
      cached ? `${cached} ${t("cacheUsed").toLowerCase()}` : t("noCacheUsed"),
      [
        [t("cacheHits"), cached],
        [t("freshDownloads"), counts.fresh || 0],
        [t("skippedSources"), skipped],
        [t("cacheTtl"), formatDurationSeconds(status.cache_max_age_seconds ?? 604800)],
      ],
      sources.filter(source => source.cache_file)
    ),
    generator: stageState(
      runtimeState ? "warn" : status.degraded ? "warn" : status.success === false ? "fail" : routes.invalid ? "warn" : "ok",
      t("generator"),
      runtimeState ? t("generatorBusy") : status.degraded ? (status.degraded_reason || t("degradedState")) : `${routes.final ?? 0} final routes`,
      runtimeState ? [
        [t("elapsed"), formatSecondsShort(runtimeState.elapsedSeconds)],
        [t("startedAt"), runtimeState.startedAt ? formatDateTime(runtimeState.startedAt * 1000) : "-"],
      ] : [],
      routes
    ),
    bird: stageState(
      birdOk ? "ok" : runtimeState?.initial ? "warn" : "fail",
      t("bird"),
      birdOk ? "birdc show status OK" : runtimeState?.initial ? t("birdWaitingInitial") : "birdc show status failed",
      [
        ["returncode", payload?.bird?.returncode ?? "-"],
        ["duration", formatSecondsShort(payload?.bird?.duration_seconds)],
      ],
      payload?.bird
    ),
    mikrotik: stageState(
      bgpOk ? "ok" : runtimeState?.initial ? "warn" : "fail",
      t("mikrotik"),
      bgpOk ? "BGP Established" : runtimeState?.initial ? t("mikrotikWaitingInitial") : "BGP not established",
      [
        ["protocol", "mikrotik"],
        ["returncode", payload?.bgp?.returncode ?? "-"],
      ],
      payload?.bgp
    ),
  };
}

function renderPipeline(payload) {
  if (!payload) return;
  const stages = buildStages(payload);
  document.querySelectorAll(".flow-node").forEach(node => {
    const stage = stages[node.dataset.stage];
    node.classList.remove("ok", "warn", "fail", "active");
    node.classList.add(stage.level);
    node.classList.toggle("active", node.dataset.stage === selectedStage);
    node.title = stage.subtitle;
  });
  renderStageDetails(stages[selectedStage] || stages.sources);
}

function renderStageDetails(stage) {
  const stageDetails = $("stage-details");
  $("stage-title").textContent = stage.title;
  $("stage-pill").textContent = stage.level === "ok" ? t("statusOk") : stage.level === "warn" ? t("statusWarn") : t("statusFail");
  $("stage-pill").className = `status-pill ${stage.level}`;
  const rowsClass = stage.rows.length >= 4 ? "kv-grid compact" : "kv-grid";
  const isRouteStats = stage.raw && typeof stage.raw === "object" && "final" in stage.raw && "base" in stage.raw;
  const details = isRouteStats
    ? renderRouteMath(stage.raw)
    : Array.isArray(stage.raw)
    ? `<details class="source-details-collapsed"><summary>${t("sourceDetails")}</summary>${renderSourceDetails(stage.raw)}</details>`
    : `<details><summary>${t("rawDetails")}</summary>${renderDataTree(stage.raw)}</details>`;
  replaceHtmlPreservingState(stageDetails, `
    <p>${escapeHtml(stage.subtitle)}</p>
    ${stage.rows.length ? `<div class="${rowsClass}">${stage.rows.map(([key, value]) => `
      <div class="kv ${rowLevel(key)}"><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>
    `).join("")}</div>` : ""}
    ${renderStageOutput(stage)}
    ${details}
  `);
}

async function loadStatus() {
  const data = await api("/api/status");
  lastStatusPayload = data;
  setVersion(data.version);
  const status = data.status || {};
  const runtime = data.runtime || {};
  const runtimeState = runtimeGenerationState(data);
  const routes = status.routes || {};
  $("routes-count").textContent = routes.final ?? data.routes_file_count ?? "-";
  const resultCard = $("last-result").closest(".metric-card");
  resultCard.classList.remove("ok", "fail", "warn");
  if (runtimeState) {
    $("last-result").textContent = runtimeGenerationLabel(runtimeState);
    resultCard.classList.add("warn");
  } else if (runtime.degraded || status.degraded) {
    $("last-result").textContent = t("statusWarn");
    resultCard.classList.add("warn");
  } else if (status.success === true) {
    $("last-result").textContent = "OK";
    resultCard.classList.add("ok");
  } else if (status.success === false) {
    $("last-result").textContent = t("failed");
    resultCard.classList.add("fail");
  } else {
    $("last-result").textContent = "-";
    resultCard.classList.add("warn");
  }
  $("duration").textContent = formatSecondsShort(runtimeState?.elapsedSeconds ?? status.duration_seconds);
  $("last-update").textContent = `${t("lastGeneration")}: ${formatDateTime(status.updated_at)}`;
  $("bird-uptime").textContent = `${t("birdUptime")}: ${birdUptime(data.bird?.stdout)}`;
  if (runtimeState?.initial) {
    $("next-update").dataset.next = "";
    $("next-update").dataset.label = t("afterStartup");
  } else if (runtimeState && !runtime.next_scheduled_update_unix) {
    $("next-update").dataset.next = "";
    $("next-update").dataset.label = t("afterCurrentRun");
  } else {
    $("next-update").dataset.next = runtime.next_scheduled_update_unix || "";
    $("next-update").dataset.label = "";
  }
  tickCountdown();
  renderRuntimeBanner(data);
  renderPipeline(data);
  if (runtimeState) {
    $("operation-log-details").open = true;
    replaceHtmlPreservingState($("operation-log"), renderActiveOperationLog(data));
  } else if (pendingReloadOperation) {
    const completedReload = renderCompletedReloadOperation(data);
    const storedReload = completedReload || renderStoredReloadResult(data);
    if (storedReload) {
      pendingReloadOperation = false;
      pendingReloadStartedAtUnix = 0;
      $("operation-log-details").open = true;
      replaceHtmlPreservingState($("operation-log"), storedReload);
    }
  }
  if (updateStatusPayload?.runtime?.active) {
    loadUpdateStatus().catch(() => {});
  }
  if (!$("lists").classList.contains("hidden")) {
    renderListTiles();
  }
}

function applyActionStatus(status) {
  if (!status || typeof status !== "object") return false;
  if (!lastStatusPayload) {
    lastStatusPayload = {version: $("version").textContent.replace(/^v/, ""), status: {}, runtime: {}};
  }
  const previousStatus = lastStatusPayload.status || {};
  lastStatusPayload.status = {
    ...previousStatus,
    sources: Array.isArray(status.sources) ? status.sources : previousStatus.sources,
    source_check_success: status.success,
    source_check_errors: status.errors || [],
    source_check_updated_at: status.updated_at,
  };
  renderPipeline(lastStatusPayload);
  if (!$("lists").classList.contains("hidden")) {
    renderListTiles();
  }
  return true;
}

function tickCountdown() {
  const label = $("next-update").dataset.label || "";
  if (label) {
    $("next-update").textContent = label;
    return;
  }
  $("next-update").textContent = formatCountdown(Number($("next-update").dataset.next || 0));
}

async function runAction(action) {
  const buttons = document.querySelectorAll("button");
  buttons.forEach(button => button.disabled = true);
  $("operation-log-details").open = true;
  $("operation-log").innerHTML = `<span class="chip">Running ${escapeHtml(action)}...</span>`;
  try {
    const result = await api(`/api/actions/${action}`, {method: "POST", body: "{}"});
    $("operation-log-details").open = true;
    if (action === "reload" && result.accepted) {
      pendingReloadOperation = true;
      pendingReloadStartedAtUnix = Math.floor(Date.now() / 1000);
      $("operation-log").innerHTML = renderAcceptedCommandResult(action, result);
      await loadStatus();
      return;
    }
    $("operation-log").innerHTML = renderCommandResult(action, result);
    if (action === "check-sources" && applyActionStatus(result.status)) {
      return;
    }
    await loadStatus();
  } catch (err) {
    $("operation-log-details").open = true;
    $("operation-log").innerHTML = renderErrorView(err);
  } finally {
    buttons.forEach(button => button.disabled = false);
  }
}

function switchView(view) {
  if (view !== "lists" && !$("lists").classList.contains("hidden") && listDirty && !window.confirm(t("discardListChanges"))) {
    return;
  }
  if (view !== "settings" && !$("settings").classList.contains("hidden") && settingsDirty && !window.confirm(t("discardSettingsChanges"))) {
    return;
  }
  document.querySelectorAll(".view").forEach(el => el.classList.add("hidden"));
  $(view).classList.remove("hidden");
  document.querySelectorAll(".nav-item").forEach(button => button.classList.toggle("active", button.dataset.view === view));
  $("view-title").textContent = t(view);
  if (view === "lists") {
    renderListTiles();
    if (!lastStatusPayload) {
      loadStatus().catch(() => {});
    }
  }
  if (view === "settings") {
    loadSettings().catch(err => {
      $("settings-form").innerHTML = renderErrorView(err);
    });
  }
}

async function loadToolTab(tabName) {
  if (tabName === "network") {
    $("network-view").innerHTML = renderNetworkView(await api("/api/tools/network"));
  } else if (tabName === "updates") {
    if (!updateStatusPayload) {
      await loadUpdateStatus();
    } else {
      renderUpdateStatus(updateStatusPayload);
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

function settingLabel(key) {
  return settingLabels[key]?.[lang] || settingLabels[key]?.en || key;
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
  settingsPayload = data;
  settingsSavedValues = Object.fromEntries((data.sections || []).flatMap(section =>
    (section.items || []).map(item => [item.key, String(item.value)])
  ));
  settingsDirty = false;
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
  if (!settingsDirty) {
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

async function applySettingsNow() {
  $("apply-settings-btn").disabled = true;
  $("save-settings-btn").disabled = true;
  $("settings-save-status").textContent = t("applying");
  setStatusTone($("settings-save-status"), "warn");
  try {
    if (!await saveSettings()) return;
    const result = await api("/api/actions/reload", {method: "POST", body: "{}"});
    await Promise.all([loadSettings(), loadStatus()]);
    $("settings-save-status").textContent = result.accepted ? t("reloadStarted") : t("commandOk");
    setStatusTone($("settings-save-status"), result.accepted ? "warn" : "ok");
  } catch (err) {
    $("settings-save-status").textContent = `${t("failed")}: ${typeof err === "string" ? err : (err.error || err.message || "request failed")}`;
    setStatusTone($("settings-save-status"), "fail");
  } finally {
    $("apply-settings-btn").disabled = false;
    $("save-settings-btn").disabled = !settingsDirty;
  }
}

async function loadList(name) {
  if (name !== currentList && listDirty && !window.confirm(t("discardListChanges"))) {
    return;
  }
  currentList = name;
  document.querySelectorAll("[data-list]").forEach(button => button.classList.toggle("active", button.dataset.list === name));
  $("list-title").textContent = listLabels[name];
  const special = isSpecialList(name);
  const showHintPanel = special || name === "asns";
  $("add-list-form").classList.toggle("hidden", special);
  $("list-source-settings").classList.toggle("hidden", !showHintPanel);
  $("list-tiles").classList.toggle("hidden", false);
  $("dry-after-save-btn").closest(".list-actions").classList.toggle("hidden", name === "google-ranges");
  $("list-editor").closest(".raw-list-editor").classList.toggle("hidden", special);
  if (name === "google-ranges") {
    listSavedContent = "";
    listSavedPath = settingsPayload?.settings_env_file || "";
    $("list-editor").value = "";
    $("add-list-input").value = "";
    markListDirty(false);
    renderListTiles();
    refreshListDirtyState(listSavedPath);
    return;
  }
  const data = await api(`/api/lists/${name}`);
  listSavedContent = data.content || "";
  listSavedPath = data.path || "";
  $("list-editor").value = listSavedContent;
  $("add-list-input").value = "";
  $("add-list-input").placeholder = `${t("itemPlaceholder")}: ${listLabels[name]}`;
  markListDirty(false);
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
    const result = await api(`/api/lists/${currentList}`, {
      method: "PUT",
      body: JSON.stringify({content})
    });
    listSavedContent = content;
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
  return lang === "ru" ? option.ru : option.en;
}

function isSpecialList(name) {
  return name === "google-ranges" || name === "countries";
}

function renderListHint(name) {
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
  const sources = lastStatusPayload?.status?.sources || [];
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
    return sources.find(source => source.kind === "url" && (source.url === value || source.name === value));
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
  const enabled = String(settingsPayload?.values?.INCLUDE_GOOGLE_RANGES || "0") === "1";
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

function renderListSourceStats(record) {
  if (!record) {
    return `<span class="chip warn">${t("notSeen")}</span>`;
  }
  const stats = [
    record.bytes != null ? `${t("downloaded")}: ${formatBytes(record.bytes)}` : "",
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
  if (currentList === "google-ranges") {
    $("list-tiles").innerHTML = "";
    renderGoogleRangesTab();
    renderIcons();
    return;
  }
  if (currentList === "countries") {
    $("list-tiles").innerHTML = "";
    renderCountriesTab();
    renderIcons();
    return;
  }
  const lines = parseListLines($("list-editor").value);
  const active = lines.filter(line => line.active);
  const comments = lines.filter(line => line.comment);
  $("list-tiles").innerHTML = active.length ? active.map(line => {
    const record = listSourceRecord(currentList, line.value);
    const level = record ? eventLevel(record) : "warn";
    return `
      <article class="list-card ${level}">
        <div class="list-card-head">
          <strong>${escapeHtml(line.value)}</strong>
          <button class="icon-button list-remove-btn" data-remove-index="${line.index}" title="${t("remove")}" aria-label="${t("remove")}">
            <i data-lucide="trash-2"></i>
          </button>
        </div>
        ${renderListSourceStats(record)}
      </article>`;
  }).join("") : `<div class="muted-box">${t("emptyList")}</div>`;
  if (comments.length) {
    $("list-tiles").insertAdjacentHTML("beforeend", `<div class="list-comments muted">${t("comments")}: ${comments.length}</div>`);
  }
  renderIcons();
}

async function addListItem(value) {
  const item = String(value || "").trim();
  if (!item) return;
  const lines = $("list-editor").value.split(/\r?\n/).filter((line, index, all) => index < all.length - 1 || line.trim());
  if (lines.some(line => line.trim() === item)) {
    $("list-save-status").textContent = `${t("saved")}: ${item}`;
    return;
  }
  lines.push(item);
  $("list-editor").value = `${lines.join("\n")}\n`;
  await saveList();
  $("add-list-input").value = "";
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

async function saveListSourceSetting(key, value) {
  try {
    $("list-save-status").textContent = "...";
    setStatusTone($("list-save-status"));
    const result = await api("/api/settings", {
      method: "PUT",
      body: JSON.stringify({values: {[key]: value}})
    });
    renderSettings(result);
    renderIcons();
    await loadStatus();
    if (currentList === "google-ranges") {
      renderListTiles();
    }
    refreshListDirtyState(`${t("saved")}: ${settingLabel(key)}`, "ok");
  } catch (err) {
    if (currentList === "google-ranges") {
      renderListTiles();
    }
    refreshListDirtyState(`${t("failed")}: ${typeof err === "string" ? err : (err.error || err.message || "request failed")}`, "fail");
  }
}

async function init() {
  applyLang();
  const session = await api("/api/session");
  loginNetworkLabels = session.login_network?.labels || [];
  setVersion(session.version);
  if (session.authenticated) {
    showAdmin();
    setupLists();
    await Promise.all([loadStatus(), loadList(currentList), loadUpdateStatus(), loadSettings()]);
    statusTimer = setInterval(() => { loadStatus().catch(() => {}); }, STATUS_POLL_INTERVAL_MS);
    updateStatusTimer = setInterval(() => { loadUpdateStatus().catch(() => {}); }, UPDATE_STATUS_POLL_INTERVAL_MS);
    setInterval(tickCountdown, 1000);
  } else {
    showLogin();
  }
}

$("login-form").addEventListener("submit", async event => {
  event.preventDefault();
  try {
    await api("/api/login", {method: "POST", body: JSON.stringify({password: $("password").value})});
    $("login-error").textContent = "";
    await init();
  } catch {
    $("login-error").textContent = t("failed");
  }
});

$("logout-btn").addEventListener("click", async () => {
  if (hasUnsavedChanges() && !window.confirm(t(listDirty ? "discardListChanges" : "discardSettingsChanges"))) {
    return;
  }
  await api("/api/logout", {method: "POST", body: "{}"});
  if (statusTimer) clearInterval(statusTimer);
  if (updateStatusTimer) clearInterval(updateStatusTimer);
  showLogin();
});

$("refresh-btn").addEventListener("click", () => loadStatus());
$("check-updates-btn").addEventListener("click", () => {
  $("update-summary").textContent = t("loading");
  loadUpdateStatus(true).catch(err => {
    renderUpdateStatus({
      ok: false,
      current_version: $("version").textContent.replace(/^v/, "") || "",
      latest_version: "",
      latest_tag: "",
      repository_url: "https://github.com/LeonidOz/BGP-Antifilter",
      release_url: "https://github.com/LeonidOz/BGP-Antifilter",
      published_at: "",
      update_available: false,
      error: typeof err === "string" ? err : (err.error || err.message || "request failed"),
    });
  });
});
$("apply-update-btn").addEventListener("click", () => {
  applyUpdate().catch(() => {});
});
$("open-updates-tab-btn").addEventListener("click", () => {
  switchView("tools");
  switchToolTab("updates");
});
document.querySelectorAll("[data-action]").forEach(button => {
  button.addEventListener("click", () => runAction(button.dataset.action));
});
document.querySelectorAll(".nav-item").forEach(button => {
  button.addEventListener("click", () => switchView(button.dataset.view));
});
document.querySelectorAll(".flow-node").forEach(button => {
  button.addEventListener("click", () => {
    selectedStage = button.dataset.stage;
    renderPipeline(lastStatusPayload);
  });
});
$("lang-ru").addEventListener("click", () => { lang = "ru"; localStorage.setItem("lang", lang); applyLang(); });
$("lang-en").addEventListener("click", () => { lang = "en"; localStorage.setItem("lang", lang); applyLang(); });
$("save-list-btn").addEventListener("click", saveList);
$("save-settings-btn").addEventListener("click", saveSettings);
$("apply-settings-btn").addEventListener("click", applySettingsNow);
$("add-list-form").addEventListener("submit", event => {
  event.preventDefault();
  addListItem($("add-list-input").value);
});
$("list-tiles").addEventListener("click", event => {
  const button = event.target.closest("[data-remove-index]");
  if (button) {
    removeListItem(Number(button.dataset.removeIndex));
  }
});
$("list-source-settings").addEventListener("change", event => {
  const countryCheckbox = event.target.closest("[data-country-code]");
  if (countryCheckbox && currentList === "countries") {
    toggleCountry(countryCheckbox.dataset.countryCode, countryCheckbox.checked);
    return;
  }
  if (event.target.id === "list-include-google-ranges") {
    saveListSourceSetting("INCLUDE_GOOGLE_RANGES", event.target.checked ? "1" : "0");
  }
});
$("list-editor").addEventListener("keydown", event => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
    event.preventDefault();
    saveList();
  }
});
$("list-editor").addEventListener("input", () => {
  markListDirty($("list-editor").value !== listSavedContent);
  renderListTiles();
});
$("settings-form").addEventListener("input", () => {
  markSettingsDirty();
});
$("settings-form").addEventListener("change", () => {
  markSettingsDirty();
});
$("check-ip-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = $("check-ip-form");
  const input = $("check-ip-input");
  const button = $("check-ip-submit");
  if (checkIpPending) return;
  checkIpPending = true;
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
    checkIpPending = false;
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
window.addEventListener("beforeunload", event => {
  if (!hasUnsavedChanges()) return;
  event.preventDefault();
  event.returnValue = t("leavePageWarning");
});

init().catch(() => showLogin());
