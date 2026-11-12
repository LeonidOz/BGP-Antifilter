# Запуск из исходников

[Установка готового приложения](../README.md) | [English](development.en.md)

Этот способ нужен для изменения кода или локальной проверки.
Для обычной установки используйте готовый Docker-образ из README.

## Linux

```bash
git clone https://github.com/LeonidOz/BGP-Antifilter.git
cd BGP-Antifilter
cp .env.example .env
```

В `.env` задайте адреса сервера и MikroTik. Для веб-панели добавьте
`ADMIN_ENABLED=1` и свой `ADMIN_PASSWORD`.
Оставьте `BGP_ANTIFILTER_VERSION` незаданной для локальной сборки.

```bash
docker compose up -d --build
docker compose logs -f --tail=50
```

Корневой `docker-compose.yml` собирает локальный образ `bgp-antifilter:dev`.
Установка из исходников хранит пользовательские списки, настройки и их резервные копии
в `config/`, а маршруты, кеш и runtime — в `generated/`.
При переходе со старой схемы конфигурация копируется автоматически при первом старте;
подробности — в [инструкции по миграции](usage.md#переход-к-раздельному-хранению).
В отличие от стека готового образа, она монтирует репозиторий и Docker socket.

## Windows и macOS

Для проверки генератора и панели через Docker Desktop используйте:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

Панель доступна на **http://localhost:8080**, если включена в `.env`.
Задайте `HEALTHCHECK_REQUIRE_BGP=0` для проверки без BGP.
Этот режим использует bridge-сеть; для рабочей BGP-сессии следуйте Linux-установке.

## Структура кода

| Путь | Назначение |
| --- | --- |
| `scripts/` | Точки входа CLI в Python-пакет и скрипт изменения версии |
| `bgp_antifilter/update_routes.py` | Аргументы CLI и последовательность обновления маршрутов |
| `bgp_antifilter/sources/` | Загрузка источников, кеш, DNS и обработка URL, ASN, стран и доменов |
| `bgp_antifilter/route_builder.py`, `route_output.py` | Сборка и проверка маршрутов; запись маршрутов, статуса и метрик |
| `bgp_antifilter/state_store.py`, `runtime_state.py` | Атомарные операции с JSON-состоянием и переходы состояния генерации |
| `bgp_antifilter/container_runtime.py` | Проверка окружения, шаблон BIRD, диагностика старта и healthcheck |
| `bgp_antifilter/config_migration.py`, `runtime_paths.py` | Миграция конфигурации и единые определения путей |
| `bgp_antifilter/admin/server.py` | HTTP-маршруты, проверка авторизации и сериализация ответов |
| `bgp_antifilter/admin/` | Сервисы настроек, списков, сессий, диагностики, статуса и действий; сборка приложения в `application.py` |
| `bgp_antifilter/updater_server.py` | Обновление образа приложения через Compose и откат |
| `admin-ui/app.js`, `admin-ui/modules/` | Инициализация веб-панели и ES-модули её разделов |
| `deploy/` | Образ, стек Portainer, запуск процессов, планировщик и shell-обёртки |
| `tests/`, `tests/js/` | Python- и JavaScript-тесты; Docker-сценарии включаются отдельно |

`bgp_antifilter/admin_server.py` сохраняет прежнюю точку входа HTTP-сервера.
Бизнес-логику админки меняйте в сервисах, а HTTP-коды и маршруты — в `admin/server.py`.
Общие правила чтения списков и сборки маршрутов находятся вне HTTP-слоя.

Для runtime JSON используйте операции `state_store`: они блокируют весь цикл чтения,
изменения и атомарной публикации файла. Файлы блокировки `*.lock` остаются на месте;
удалять их во время работы нельзя. Кеш источников и пользовательские списки имеют
свои форматы хранения и не являются runtime JSON.

Пути конфигурации задаются `CONFIG_DIR`, `SETTINGS_FILE`, `SETTINGS_ENV_FILE`,
`LIST_BACKUP_DIR` и отдельными переменными списков (`LISTS_FILE` и другими).
Явно заданные пути имеют приоритет, включая пути из прежних YAML.
В контейнере пакет доступен из любого рабочего каталога через `PYTHONPATH=/`.

Веб-панель загружает ES-модули прямо из `admin-ui/`, без сборщика и установки npm-пакетов.
Открывайте её через HTTP-сервер приложения, а не как `file://`.
При добавлении модуля сохраняйте явные импорты и отсутствие циклических зависимостей.

## Проверки

Для Python-проверок подойдёт Python 3.11 из Debian-образа; для JavaScript используйте
Node.js 22, как в CI. Из корня репозитория:

```bash
python -m unittest discover -s tests
node --test tests/js/admin-modules.test.mjs
docker compose --env-file .env.example config --quiet
shellcheck -x deploy/*.sh
```

На Windows вместо `python` можно использовать `py -3`.
ShellCheck и POSIX shell-проверки выполняйте в Linux или подходящем контейнере;
зависящие от платформы тесты помечаются как пропущенные.

Для проверки миграции на временных Docker volumes сначала соберите текущий образ:

```bash
docker compose --env-file .env.example build
RUN_DOCKER_CONFIG_MIGRATION=1 CONFIG_MIGRATION_IMAGE=bgp-antifilter:dev python -m unittest tests.test_config_volume -v
```

Эквивалент запуска теста в PowerShell:

```powershell
$env:RUN_DOCKER_CONFIG_MIGRATION = '1'
$env:CONFIG_MIGRATION_IMAGE = 'bgp-antifilter:dev'
py -3 -m unittest tests.test_config_volume -v
Remove-Item Env:RUN_DOCKER_CONFIG_MIGRATION
Remove-Item Env:CONFIG_MIGRATION_IMAGE
```

Тест проверяет старые пути, миграцию списков и настроек, сохранение правок после
пересоздания контейнера, восстановление маршрутов с пустым томом данных и запуск
служебных скриптов из другого каталога. Он создаёт временные тома и удаляет их после проверки.
Для дополнительной проверки отката задайте `CONFIG_ROLLBACK_IMAGE` — локально доступный
предыдущий образ с поддержкой переменных путей. Запускайте тест с образом текущего кода.

Полный smoke-тест контейнера выполняется на Linux с доступным Docker Engine и Compose:

```bash
RUN_DOCKER_SMOKE=1 python -m unittest tests.test_smoke_docker -v
```

Этот набор отдельно проверяет Compose, HTTP-панель и готовый стек Portainer.
Он не заменяет проверку реальной BGP-сессии с MikroTik.
Команды с переменными перед именем программы используют синтаксис Linux shell.
CI выполняет Python- и JavaScript-тесты, проверку Compose, сборку, миграцию volumes,
Docker smoke-тесты и ShellCheck; см. [workflow](../.github/workflows/ci.yml).
Порядок выпуска релиза описан в [AGENTS.md](../AGENTS.md).
