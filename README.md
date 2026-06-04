# BGP Antifilter

BGP Antifilter — контейнеризированная конфигурация BIRD для публикации списков заблокированных IP-адресов и подсетей в MikroTik по BGP.

Проект скачивает списки маршрутов из открытых источников, дополняет их IP-адресами вручную заданных доменов, исключает маршруты для доменов из списка исключений и генерирует `blackhole`-маршруты для BIRD.

## Что входит в проект

- `Dockerfile` — образ на базе Debian с BIRD 2, curl и Python.
- `docker-compose.yml` — запуск BIRD в `host` network mode.
- `bird.conf` — BGP-сессия с MikroTik и экспорт статических маршрутов.
- `entrypoint.sh` — периодическое обновление списков и перезагрузка конфигурации BIRD.
- `lists.txt` — URL-адреса исходных списков IP и подсетей.
- `include-domains.txt` — домены, IP-адреса которых нужно добавить в маршруты.
- `exclude-domains.txt` — домены, IP-адреса которых нужно исключить из маршрутов.
- `generated/` — генерируемый кеш маршрутов, не хранится в репозитории.

## Как это работает

1. Контейнер запускает BIRD с конфигурацией из `bird.conf`.
2. `entrypoint.sh` скачивает списки из `lists.txt`.
3. Найденные IP-адреса нормализуются в CIDR-формат.
4. Домены из `include-domains.txt` резолвятся в IPv4 и добавляются как `/32`.
5. Домены из `exclude-domains.txt` резолвятся в IPv4 и удаляют пересекающиеся маршруты.
6. Итоговый файл `generated/routes.conf` подключается в BIRD как статические `blackhole`-маршруты.
7. BIRD экспортирует маршруты в MikroTik через BGP.

## Настройка

Перед запуском проверьте параметры в `bird.conf`:

```bird
define MY_AS = 64500;
define MT_AS = 65455;
define MT_IP = 192.168.55.1;
define BIRD_IP = 192.168.55.5;
```

Где:

- `MY_AS` — AS контейнера с BIRD.
- `MT_AS` — AS MikroTik.
- `MT_IP` — IP-адрес MikroTik.
- `BIRD_IP` — IP-адрес хоста или интерфейса, с которого BIRD устанавливает BGP-сессию.

При необходимости измените интервал обновления в `docker-compose.yml`:

```yaml
UPDATE_INTERVAL: "1800"
```

Значение задается в секундах.

## Запуск

```bash
docker compose up -d --build
```

Посмотреть логи:

```bash
docker compose logs -f bird
```

Остановить контейнер:

```bash
docker compose down
```

## Управление списками

Добавьте новые источники IP-адресов и подсетей в `lists.txt`, по одному URL на строку.

Домены, которые нужно принудительно добавить в маршруты, указываются в `include-domains.txt`.

Домены, которые нужно исключить из маршрутов, указываются в `exclude-domains.txt`.

Пустые строки и строки с `#` игнорируются.

## Публикация на GitHub

После проверки можно добавить удаленный репозиторий и отправить проект:

```bash
git remote add origin git@github.com:USER/REPOSITORY.git
git branch -M main
git add .
git commit -m "Initial commit"
git push -u origin main
```
