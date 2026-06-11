# BGP Antifilter
![Python](https://img.shields.io/badge/python-3.x-blue)
![Debian](https://img.shields.io/badge/debian-bookworm-a81d33)
![BIRD](https://img.shields.io/badge/BIRD-2.x-green)
![RouterOS](https://img.shields.io/badge/RouterOS-7-blue)
![IPv4](https://img.shields.io/badge/IP-IPv4-blueviolet)

[English](README.en.md) | Русский

BGP Antifilter - контейнеризированная конфигурация BIRD 2 для публикации списков заблокированных IP-адресов и подсетей в MikroTik по BGP.

Проект скачивает списки маршрутов из открытых источников, дополняет их IP-адресами вручную заданных доменов, исключает маршруты для доменов из списка исключений и генерирует `blackhole`-маршруты для BIRD.

![Экран входа BGP Antifilter](docs/assets/admin-login.png)

<p align="center">
  <img src="docs/assets/admin-dashboard.png" alt="Панель BGP Antifilter" width="48%">
  <img src="docs/assets/admin-login.png" alt="Вход в BGP Antifilter" width="48%">
</p>

## Что входит в проект

- `deploy/` - канонические runtime-файлы: `Dockerfile`, `docker-compose.yml`, shell-скрипты и `bird.conf.template`.
- `scripts/` - Python entrypoint-обертки для контейнера и ручных проверок.
- `bgp_antifilter/` - основная логика генерации маршрутов, админки и служебных команд.
- `admin-ui/` - статические файлы веб-админки.
- `default-lists/` - дефолтные списки источников, ASN и include/exclude-доменов, которые копируются при первом старте.
- `.env.example` - пример локальных настроек AS, IP-адресов и интервала обновления.
- `generated/config/lists.txt` - рабочий список исходных IP и подсетей пользователя.
- `generated/config/include-asns.txt` - рабочий список ASN пользователя.
- `generated/config/include-domains.txt` - рабочий список include-доменов пользователя.
- `generated/config/exclude-domains.txt` - рабочий список exclude-доменов пользователя.
- `generated/` - генерируемый кеш маршрутов, не хранится в репозитории.

## Как это работает

1. Контейнер рендерит `/etc/bird/bird.conf` из `deploy/bird.conf.template`.
2. BIRD запускается с полученной конфигурацией.
3. `deploy/entrypoint.sh` при первом старте копирует дефолты из `default-lists/` в `generated/config/`, затем использует рабочий `generated/config/lists.txt`.
4. ASN из `generated/config/include-asns.txt` загружаются из RouteViews API как анонсированные IPv4-префиксы.
5. Если `INCLUDE_GOOGLE_RANGES=1`, загружаются Google `goog.json` и `cloud.json`; Cloud-префиксы вычитаются из общего списка Google.
6. `scripts/generate-routes.py` извлекает и валидирует IPv4/CIDR-маршруты.
7. Домены из `generated/config/include-domains.txt` резолвятся в IPv4 и добавляются как `/32`.
8. Домены из `generated/config/exclude-domains.txt` резолвятся в IPv4 и вычитаются из итогового набора маршрутов.
9. Итоговый файл `generated/routes.conf` подключается в BIRD как статические `blackhole`-маршруты.
10. BIRD экспортирует маршруты в MikroTik через BGP.

## Настройка

Скопируйте пример окружения и измените параметры под свою сеть:

```bash
cp .env.example .env
```

Если вы обновляетесь с предыдущей структуры репозитория, перенесите свои кастомные списки в `generated/config/`: `lists.txt`, `include-asns.txt`, `include-domains.txt`, `exclude-domains.txt`.

Основные параметры:

```dotenv
BGP_ANTIFILTER_VERSION=0.2.3
MY_AS=64500
MT_AS=65455
MT_IP=192.168.55.1
BIRD_IP=192.168.55.5
ROUTER_ID=192.168.55.5
BGP_COMMUNITY=65432,500
UPDATE_INTERVAL=1800
CACHE_MAX_AGE=604800
INCLUDE_GOOGLE_RANGES=1
REQUIRE_ALL_URL_SOURCES=0
MIN_PREFIX_LENGTH=8
ALLOW_BROAD_ROUTES=0
UPDATE_LOCK_DIR=/etc/bird/generated/update.lock
HEALTHCHECK_REQUIRE_BGP=1
BGP_PROTOCOL=mikrotik
ADMIN_ENABLED=0
ADMIN_PORT=8080
ADMIN_PASSWORD=
```

Где:

- `MY_AS` - AS контейнера с BIRD.
- `BGP_ANTIFILTER_VERSION` - тег локального Docker-образа, по умолчанию `0.2.3`.
- `MT_AS` - AS MikroTik.
- `MT_IP` - IP-адрес MikroTik.
- `BIRD_IP` - IP-адрес хоста или интерфейса, с которого BIRD устанавливает BGP-сессию.
- `ROUTER_ID` - router id BIRD, обычно совпадает с `BIRD_IP`.
- `BGP_COMMUNITY` - community, которая добавляется к экспортируемым маршрутам.
- `UPDATE_INTERVAL` - интервал обновления списков в секундах.
- `CACHE_MAX_AGE` - максимальный возраст кеша источника в секундах, по умолчанию 7 дней.
- `INCLUDE_GOOGLE_RANGES` - `1` добавляет default Google service ranges из `goog.json` за вычетом Google Cloud из `cloud.json`; `0` отключает этот источник.
- `REQUIRE_ALL_URL_SOURCES` - `1` делает каждый URL из `generated/config/lists.txt` обязательным; `0` по умолчанию разрешает пропустить недоступный URL-источник, если итоговая таблица все равно собирается из остальных данных.
- `MIN_PREFIX_LENGTH` - минимальная длина IPv4-префикса, разрешенная из внешних источников, по умолчанию `8`.
- `ALLOW_BROAD_ROUTES` - `1` отключает защиту от слишком широких IPv4-маршрутов; по умолчанию `0`.
- `UPDATE_LOCK_DIR` - lock-директория, предотвращающая параллельные обновления.
- `HEALTHCHECK_REQUIRE_BGP` - `1` требует установленную BGP-сессию в Docker healthcheck; `0` проверяет только BIRD и маршруты.
- `BGP_PROTOCOL` - имя BGP-протокола в BIRD для healthcheck, по умолчанию `mikrotik`.
- `ADMIN_ENABLED` - `1` включает веб-админку, по умолчанию `0`.
- `ADMIN_PORT` - порт веб-админки, по умолчанию `8080`.
- `ADMIN_PASSWORD` - пароль входа в веб-админку; обязателен при `ADMIN_ENABLED=1`.

Если `.env` не создан, используются значения по умолчанию из compose-конфига.

## Веб-админка

Админка выключена по умолчанию. Для включения задайте пароль и порт:

```dotenv
ADMIN_ENABLED=1
ADMIN_PORT=8080
ADMIN_PASSWORD=change-me
```

После перезапуска контейнера интерфейс будет доступен на указанном порту хоста. В админке есть RU/EN-переключатель, dashboard с таймером до следующего автообновления, статусом BIRD/BGP, количеством маршрутов и источниками, запуск `dry-run`, `check-sources`, `reload`, проверка IP или домена, просмотр метрик, маршрутов и логов контейнера, скачивание `routes.conf`, редактор четырех списков и страница настроек.

При `ADMIN_ENABLED=1` отдельный сервис `admin` поднимается всегда. Это убирает конкуренцию за stdout/stderr у контейнера BIRD и делает поведение одинаковым на Linux и Docker Desktop для Windows/macOS. Сервис `admin` публикует порт через обычный `ports:`, а с BIRD общается через общий `/run/bird` socket и общие файлы `generated/`.

Рабочие файлы `generated/config/lists.txt`, `generated/config/include-asns.txt`, `generated/config/include-domains.txt` и `generated/config/exclude-domains.txt` хранятся вне git и редактируются админкой без конфликтов с `git pull`. Если файла еще нет, контейнер создает его из дефолта из `default-lists/`. Перед сохранением создается backup в `generated/list-backups`.

При старте контейнер проверяет значения окружения до запуска BIRD:

- `MY_AS` и `MT_AS` должны быть целыми AS-номерами.
- `MT_IP`, `BIRD_IP` и `ROUTER_ID` должны быть корректными IPv4-адресами.
- `BGP_COMMUNITY` должен быть указан в формате `AS,VALUE`, например `65432,500`.
- `UPDATE_INTERVAL` должен быть положительным числом секунд.
- `CACHE_MAX_AGE` должен быть положительным числом секунд.

## Запуск

Из корня репозитория можно использовать короткие команды `docker compose ...`: root-level `docker-compose.yml` оставлен как удобная точка входа и автоматически подхватывает `.env`.

```bash
docker compose up -d --build
```

Посмотреть логи:

```bash
docker compose logs -f bird admin
```

Проверить состояние контейнера:

```bash
docker compose ps
```

Остановить контейнер:

```bash
docker compose down
```

## Управление списками

Добавьте новые источники IP-адресов и подсетей в `generated/config/lists.txt`, по одному URL на строку.

Источники могут быть обычным текстом или JSON. Генератор извлекает IPv4/CIDR из содержимого источника, поэтому URL вида `format=json&data=cidr4` тоже поддерживаются. Например:

```text
https://iplist.opencck.org/?format=json&data=cidr4&site=claude.ai&site=chatgpt.com&site=copilot&site=deepseek.com&site=grok.com
```

Если таких списков несколько, добавьте каждый URL отдельной строкой в `generated/config/lists.txt`.

ASN, чьи анонсированные IPv4-префиксы нужно принудительно добавить в маршруты, указываются в `generated/config/include-asns.txt`. Например, `AS32934` добавляет маршруты Meta для Facebook, Instagram, WhatsApp и Messenger.

Для YouTube включен отдельный источник Google ranges: при `INCLUDE_GOOGLE_RANGES=1` контейнер берет `https://www.gstatic.com/ipranges/goog.json`, вычитает `https://www.gstatic.com/ipranges/cloud.json` и добавляет оставшиеся IPv4-префиксы. Домены YouTube в `generated/config/include-domains.txt` остаются как дополнительный точечный источник.

Домены, которые нужно принудительно добавить в маршруты, указываются в `generated/config/include-domains.txt`. Эти домены обрабатываются как best-effort: если домен временно не резолвится и кеша для него нет, он помечается как `skipped`, но обновление маршрутов продолжается.

Домены, которые нужно исключить из маршрутов, указываются в `generated/config/exclude-domains.txt`. Эти домены считаются строгими: если исключение не удалось зарезолвить и свежего кеша нет, новый `routes.conf` не применяется. Если исключенный IP попадает внутрь более крупной подсети, генератор разобьет подсеть на меньшие маршруты без этого IP.

Перед записью итогового файла генератор удаляет точные дубли, убирает маршруты, уже покрытые более крупными подсетями, и схлопывает соседние сети там, где это не возвращает исключенные адреса.

Если URL-источник из `generated/config/lists.txt` временно недоступен, по умолчанию генератор помечает его как `failed`, но продолжает сборку из остальных источников и применяет результат, если итоговый набор маршрутов не пустой. Для строгого режима можно включить `REQUIRE_ALL_URL_SOURCES=1`; тогда отсутствие любого URL без свежего кеша останавливает обновление.

Пустые строки и строки с `#` игнорируются.

## Проверка и откат

Перед применением нового `generated/routes.conf` контейнер оставляет копию предыдущего файла. У каждого сетевого источника есть отдельный кеш в `generated/cache`: URL из `generated/config/lists.txt`, префиксы ASN, Google ranges и DNS-результаты доменов include/exclude. Если источник временно недоступен, генератор использует его последний кеш и продолжает обновление остальных источников.

Кеш используется только пока он моложе `CACHE_MAX_AGE`; по умолчанию это 604800 секунд, то есть 7 дней. Если у недоступного источника еще нет свежего кеша, обновление итогового файла не применяется и старый `routes.conf` остается на месте. Если `birdc configure` не принимает обновленную конфигурацию, `deploy/entrypoint.sh` восстанавливает старый файл маршрутов и повторно просит BIRD применить рабочий вариант.

При старте контейнер сначала пытается подготовить маршруты, а уже потом запускает BIRD. Это уменьшает шанс короткого анонса пустой таблицы после рестарта.

После каждой попытки обновления пишутся диагностические файлы:

- `generated/status.json` - итог обновления, количество маршрутов, состояние каждого источника (`fresh`, `cache`, `skipped`, `failed`, `disabled`) и ошибки.
- `generated/metrics.prom` - метрики в Prometheus text format: количество маршрутов, успех обновления, время последней попытки и сводка по состояниям источников.

Логи обновления пишутся в структурированном JSON-формате. У каждой записи есть `ts`, `level`, `message` и дополнительные поля этапа, источника или результата. Это упрощает фильтрацию в `docker compose logs`, Loki, Vector и других сборщиках логов.

Обновления маршрутов защищены lock-директорией `generated/update.lock`. Если ручной `/reload-routes.sh` запущен во время периодического обновления, второй запуск завершится с ошибкой и не будет параллельно писать `routes.conf`, `status.json` или `metrics.prom`.

По умолчанию генератор отказывается применять слишком широкие IPv4-маршруты короче `/8`, например `0.0.0.0/0`. Это защита от ошибочного внешнего источника. Порог можно изменить через `MIN_PREFIX_LENGTH`; полностью отключить проверку можно только явно: `ALLOW_BROAD_ROUTES=1`.

Docker healthcheck проверяет `birdc show status`, непустой `generated/routes.conf`, ненулевое количество маршрутов в `status.json` и, если `HEALTHCHECK_REQUIRE_BGP=1`, состояние BGP-протокола `BGP_PROTOCOL`.

Проверить состояние BIRD внутри контейнера:

```bash
docker compose exec bird birdc show status
```

Посмотреть количество опубликованных статических маршрутов:

```bash
docker compose exec bird birdc show route protocol static_antifilter count
```

Проверить, есть ли IP в сгенерированной базе, и увидеть источники из кеша:

```bash
docker compose exec bird /check-ip.py 1.2.3.4
```

Команда проверяет попадание IP в `generated/routes.conf`, затем ищет совпадения в кешах источников из `generated/status.json`. Если IP найден в финальной базе, команда завершится с кодом `0`; если нет - с кодом `1`.

Для скриптов можно получить машинно-читаемый вывод:

```bash
docker compose exec bird /check-ip.py 1.2.3.4 --json
```

Принудительно обновить маршруты без перезапуска BIRD:

```bash
docker compose exec bird /reload-routes.sh
```

Эта команда запускает обновление источников внутри работающего контейнера. Старые маршруты остаются активными, пока новый `routes.conf` не будет сгенерирован и принят командой `birdc configure`. Если генерация или применение не удались, старый файл маршрутов восстанавливается.

Во время ручного обновления и в `docker compose logs -f bird admin` выводится прогресс по этапам: загрузка URL/ASN/Google ranges, резолв include/exclude-доменов, парсинг, сборка итоговой таблицы, запись status/metrics.

Проверить обновление без записи `routes.conf`, `status.json` и `metrics.prom`:

```bash
docker compose exec bird /update-routes.py --dry-run
```

Dry-run скачивает и валидирует источники, собирает итоговую таблицу в памяти и печатает JSON-сводку. Кеши источников при этом могут обновиться, но активные маршруты и диагностические файлы не меняются.

Проверить только доступность источников без парсинга маршрутов и записи диагностических файлов:

```bash
docker compose exec bird /update-routes.py --check-sources
```

Локально проверить генератор маршрутов можно без Docker:

```bash
python -m unittest discover -s tests
```

Если установлен `make`, доступны короткие команды:

```bash
make test
make up
make logs
make reload
make dry-run
make check-sources
make check-ip IP=1.2.3.4
```

## Эксплуатационный чеклист

- Перед изменением `generated/config/lists.txt`, `generated/config/include-asns.txt`, `generated/config/include-domains.txt` или `generated/config/exclude-domains.txt` запустите dry-run.
- После ручного reload проверьте `generated/status.json`: `success` должен быть `true`, а `routes.final` больше нуля.
- На MikroTik принимайте только маршруты с ожидаемой BGP community и отклоняйте остальные.
- Для exclude-доменов держите свежий кеш: если DNS временно недоступен и кеша нет, обновление намеренно не применяется.
- Следите за `bgp_antifilter_update_success`, `bgp_antifilter_routes_total` и возрастом кеша источников в `metrics.prom`.
- Не включайте `ALLOW_BROAD_ROUTES=1`, если точно не понимаете, какой источник принес широкий префикс.


## Пример настройки MikroTik

Минимальный пример для RouterOS 7:

```routeros
/routing bgp template
add name=antifilter-template as=65455 routing-table=main

/routing bgp connection
add name=antifilter-bird \
    template=antifilter-template \
    remote.address=192.168.55.5 \
    remote.as=64500 \
    local.address=192.168.55.1 \
    multihop=yes \
    input.filter=antifilter-in

/routing filter rule
add chain=antifilter-in rule="if (bgp-communities includes 65432:500) { accept } else { reject }"
```

Параметры AS и IP-адресов должны совпадать со значениями в `.env`.
