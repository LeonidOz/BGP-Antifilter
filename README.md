# BGP Antifilter
![Python](https://img.shields.io/badge/python-3.x-blue)
![Debian](https://img.shields.io/badge/debian-bookworm-a81d33)
![BIRD](https://img.shields.io/badge/BIRD-2.x-green)
![RouterOS](https://img.shields.io/badge/RouterOS-7-blue)
![IPv4](https://img.shields.io/badge/IP-IPv4-blueviolet)

[English](README.en.md) | Русский

BGP Antifilter - контейнеризированная конфигурация BIRD 2 для публикации списков заблокированных IP-адресов и подсетей в MikroTik по BGP.

Проект скачивает списки маршрутов из открытых источников, дополняет их IP-адресами вручную заданных доменов, исключает маршруты для доменов из списка исключений и генерирует `blackhole`-маршруты для BIRD.

## Что входит в проект

- `Dockerfile` - образ на базе Debian с BIRD 2, curl и Python.
- `docker-compose.yml` - запуск BIRD в `host` network mode.
- `bird.conf.template` - шаблон BIRD-конфигурации с параметрами из окружения.
- `.env.example` - пример локальных настроек AS, IP-адресов и интервала обновления.
- `entrypoint.sh` - запуск BIRD, рендеринг конфига и периодическое обновление маршрутов.
- `generate-routes.py` - генератор и валидатор итогового файла маршрутов.
- `update-routes.py` - обновление источников, кеширование, статус и метрики.
- `healthcheck.sh` - проверка BIRD, наличия маршрутов и BGP-сессии.
- `lists.txt` - URL-адреса исходных списков IP и подсетей.
- `include-asns.txt` - ASN, анонсированные IPv4-префиксы которых нужно добавить в маршруты.
- `include-domains.txt` - домены, IP-адреса которых нужно добавить в маршруты.
- `exclude-domains.txt` - домены, IP-адреса которых нужно исключить из маршрутов.
- `generated/` - генерируемый кеш маршрутов, не хранится в репозитории.

## Как это работает

1. Контейнер рендерит `/etc/bird/bird.conf` из `bird.conf.template`.
2. BIRD запускается с полученной конфигурацией.
3. `entrypoint.sh` скачивает списки из `lists.txt`.
4. ASN из `include-asns.txt` загружаются из RouteViews API как анонсированные IPv4-префиксы.
5. Если `INCLUDE_GOOGLE_RANGES=1`, загружаются Google `goog.json` и `cloud.json`; Cloud-префиксы вычитаются из общего списка Google.
6. `generate-routes.py` извлекает и валидирует IPv4/CIDR-маршруты.
7. Домены из `include-domains.txt` резолвятся в IPv4 и добавляются как `/32`.
8. Домены из `exclude-domains.txt` резолвятся в IPv4 и вычитаются из итогового набора маршрутов.
9. Итоговый файл `generated/routes.conf` подключается в BIRD как статические `blackhole`-маршруты.
10. BIRD экспортирует маршруты в MikroTik через BGP.

## Настройка

Скопируйте пример окружения и измените параметры под свою сеть:

```bash
cp .env.example .env
```

Основные параметры:

```dotenv
MY_AS=64500
MT_AS=65455
MT_IP=192.168.55.1
BIRD_IP=192.168.55.5
ROUTER_ID=192.168.55.5
BGP_COMMUNITY=65432,500
UPDATE_INTERVAL=1800
CACHE_MAX_AGE=604800
INCLUDE_GOOGLE_RANGES=1
HEALTHCHECK_REQUIRE_BGP=1
BGP_PROTOCOL=mikrotik
```

Где:

- `MY_AS` - AS контейнера с BIRD.
- `MT_AS` - AS MikroTik.
- `MT_IP` - IP-адрес MikroTik.
- `BIRD_IP` - IP-адрес хоста или интерфейса, с которого BIRD устанавливает BGP-сессию.
- `ROUTER_ID` - router id BIRD, обычно совпадает с `BIRD_IP`.
- `BGP_COMMUNITY` - community, которая добавляется к экспортируемым маршрутам.
- `UPDATE_INTERVAL` - интервал обновления списков в секундах.
- `CACHE_MAX_AGE` - максимальный возраст кеша источника в секундах, по умолчанию 7 дней.
- `INCLUDE_GOOGLE_RANGES` - `1` добавляет default Google service ranges из `goog.json` за вычетом Google Cloud из `cloud.json`; `0` отключает этот источник.
- `HEALTHCHECK_REQUIRE_BGP` - `1` требует установленную BGP-сессию в Docker healthcheck; `0` проверяет только BIRD и маршруты.
- `BGP_PROTOCOL` - имя BGP-протокола в BIRD для healthcheck, по умолчанию `mikrotik`.

Если `.env` не создан, используются значения по умолчанию из `docker-compose.yml`.

При старте контейнер проверяет значения окружения до запуска BIRD:

- `MY_AS` и `MT_AS` должны быть целыми AS-номерами.
- `MT_IP`, `BIRD_IP` и `ROUTER_ID` должны быть корректными IPv4-адресами.
- `BGP_COMMUNITY` должен быть указан в формате `AS,VALUE`, например `65432,500`.
- `UPDATE_INTERVAL` должен быть положительным числом секунд.
- `CACHE_MAX_AGE` должен быть положительным числом секунд.

## Запуск

```bash
docker compose up -d --build
```

Посмотреть логи:

```bash
docker compose logs -f bird
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

Добавьте новые источники IP-адресов и подсетей в `lists.txt`, по одному URL на строку.

Источники могут быть обычным текстом или JSON. Генератор извлекает IPv4/CIDR из содержимого источника, поэтому URL вида `format=json&data=cidr4` тоже поддерживаются. Например:

```text
https://iplist.opencck.org/?format=json&data=cidr4&site=claude.ai&site=chatgpt.com&site=copilot&site=deepseek.com&site=grok.com
```

Если таких списков несколько, добавьте каждый URL отдельной строкой в `lists.txt`.

ASN, чьи анонсированные IPv4-префиксы нужно принудительно добавить в маршруты, указываются в `include-asns.txt`. Например, `AS32934` добавляет маршруты Meta для Facebook, Instagram, WhatsApp и Messenger.

Для YouTube включен отдельный источник Google ranges: при `INCLUDE_GOOGLE_RANGES=1` контейнер берет `https://www.gstatic.com/ipranges/goog.json`, вычитает `https://www.gstatic.com/ipranges/cloud.json` и добавляет оставшиеся IPv4-префиксы. Домены YouTube в `include-domains.txt` остаются как дополнительный точечный источник.

Домены, которые нужно принудительно добавить в маршруты, указываются в `include-domains.txt`. Эти домены обрабатываются как best-effort: если домен временно не резолвится и кеша для него нет, он помечается как `skipped`, но обновление маршрутов продолжается.

Домены, которые нужно исключить из маршрутов, указываются в `exclude-domains.txt`. Эти домены считаются строгими: если исключение не удалось зарезолвить и свежего кеша нет, новый `routes.conf` не применяется. Если исключенный IP попадает внутрь более крупной подсети, генератор разобьет подсеть на меньшие маршруты без этого IP.

Перед записью итогового файла генератор удаляет точные дубли, убирает маршруты, уже покрытые более крупными подсетями, и схлопывает соседние сети там, где это не возвращает исключенные адреса.

Пустые строки и строки с `#` игнорируются.

## Проверка и откат

Перед применением нового `generated/routes.conf` контейнер оставляет копию предыдущего файла. У каждого сетевого источника есть отдельный кеш в `generated/cache`: URL из `lists.txt`, префиксы ASN, Google ranges и DNS-результаты доменов include/exclude. Если источник временно недоступен, генератор использует его последний кеш и продолжает обновление остальных источников.

Кеш используется только пока он моложе `CACHE_MAX_AGE`; по умолчанию это 604800 секунд, то есть 7 дней. Если у недоступного источника еще нет свежего кеша, обновление итогового файла не применяется и старый `routes.conf` остается на месте. Если `birdc configure` не принимает обновленную конфигурацию, `entrypoint.sh` восстанавливает старый файл маршрутов и повторно просит BIRD применить рабочий вариант.

При старте контейнер сначала пытается подготовить маршруты, а уже потом запускает BIRD. Это уменьшает шанс короткого анонса пустой таблицы после рестарта.

После каждой попытки обновления пишутся диагностические файлы:

- `generated/status.json` - итог обновления, количество маршрутов, состояние каждого источника (`fresh`, `cache`, `skipped`, `failed`, `disabled`) и ошибки.
- `generated/metrics.prom` - метрики в Prometheus text format: количество маршрутов, успех обновления, время последней попытки и сводка по состояниям источников.

Docker healthcheck проверяет `birdc show status`, непустой `generated/routes.conf`, ненулевое количество маршрутов в `status.json` и, если `HEALTHCHECK_REQUIRE_BGP=1`, состояние BGP-протокола `BGP_PROTOCOL`.

Проверить состояние BIRD внутри контейнера:

```bash
docker compose exec bird birdc show status
```

Посмотреть количество опубликованных статических маршрутов:

```bash
docker compose exec bird birdc show route protocol static_antifilter count
```

Локально проверить генератор маршрутов можно без Docker:

```bash
python -m unittest discover -s tests
```

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
