# BGP Antifilter

BGP Antifilter - контейнеризированная конфигурация BIRD 2 для публикации списков заблокированных IP-адресов и подсетей в MikroTik по BGP.

Проект скачивает списки маршрутов из открытых источников, дополняет их IP-адресами вручную заданных доменов, исключает маршруты для доменов из списка исключений и генерирует `blackhole`-маршруты для BIRD.

## Что входит в проект

- `Dockerfile` - образ на базе Debian с BIRD 2, curl и Python.
- `docker-compose.yml` - запуск BIRD в `host` network mode.
- `bird.conf.template` - шаблон BIRD-конфигурации с параметрами из окружения.
- `.env.example` - пример локальных настроек AS, IP-адресов и интервала обновления.
- `entrypoint.sh` - запуск BIRD, рендеринг конфига и периодическое обновление маршрутов.
- `generate-routes.py` - генератор и валидатор итогового файла маршрутов.
- `lists.txt` - URL-адреса исходных списков IP и подсетей.
- `include-domains.txt` - домены, IP-адреса которых нужно добавить в маршруты.
- `exclude-domains.txt` - домены, IP-адреса которых нужно исключить из маршрутов.
- `generated/` - генерируемый кеш маршрутов, не хранится в репозитории.

## Как это работает

1. Контейнер рендерит `/etc/bird/bird.conf` из `bird.conf.template`.
2. BIRD запускается с полученной конфигурацией.
3. `entrypoint.sh` скачивает списки из `lists.txt`.
4. `generate-routes.py` извлекает и валидирует IPv4/CIDR-маршруты.
5. Домены из `include-domains.txt` резолвятся в IPv4 и добавляются как `/32`.
6. Домены из `exclude-domains.txt` резолвятся в IPv4 и вычитаются из итогового набора маршрутов.
7. Итоговый файл `generated/routes.conf` подключается в BIRD как статические `blackhole`-маршруты.
8. BIRD экспортирует маршруты в MikroTik через BGP.

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
```

Где:

- `MY_AS` - AS контейнера с BIRD.
- `MT_AS` - AS MikroTik.
- `MT_IP` - IP-адрес MikroTik.
- `BIRD_IP` - IP-адрес хоста или интерфейса, с которого BIRD устанавливает BGP-сессию.
- `ROUTER_ID` - router id BIRD, обычно совпадает с `BIRD_IP`.
- `BGP_COMMUNITY` - community, которая добавляется к экспортируемым маршрутам.
- `UPDATE_INTERVAL` - интервал обновления списков в секундах.

Если `.env` не создан, используются значения по умолчанию из `docker-compose.yml`.

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

Домены, которые нужно принудительно добавить в маршруты, указываются в `include-domains.txt`.

Домены, которые нужно исключить из маршрутов, указываются в `exclude-domains.txt`. Если исключенный IP попадает внутрь более крупной подсети, генератор разобьет подсеть на меньшие маршруты без этого IP.

Пустые строки и строки с `#` игнорируются.

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
