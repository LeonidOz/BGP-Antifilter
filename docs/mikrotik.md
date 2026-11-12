# Подключение MikroTik

[Установка приложения](../README.md) | [English](mikrotik.en.md)

Выберите один способ: **BGP** автоматически передаёт обновлённые маршруты на роутер;
**Address List** позволяет вручную скачать и импортировать список для своих правил.

## BGP

В примере используются:

| Назначение | Значение |
| --- | --- |
| Linux-сервер с приложением | `192.168.55.5`, AS `64500` |
| MikroTik | `192.168.55.1`, AS `65455` |
| Метка маршрутов | `65432:500` — в `.env` записана как `65432,500` |
| Шлюз VPN | `10.10.10.1` — замените на свой |

VPN уже должен работать, а его шлюз — быть доступен с MikroTik.
Пример устанавливает маршруты в таблицу `main`.
Если используете отдельные таблицы, routing marks или VPN без IP-шлюза,
адаптируйте фильтр и таблицу под свою схему.

**Входящий фильтр должен указывать VPN-шлюз.**
По умолчанию приложение анонсирует свой адрес как следующий узел.
Linux-сервер с BIRD содержит маршруты `blackhole` и сам не пересылает этот трафик в VPN.

### 1. Создайте фильтры

На MikroTik замените `10.10.10.1` на IP-шлюз вашего VPN и выполните:

```routeros
/routing filter rule
add chain=antifilter-in rule="if (dst == 0.0.0.0/0) { reject }"
add chain=antifilter-in rule="if (bgp-communities includes 65432:500) { set gw 10.10.10.1; accept } else { reject }"
add chain=antifilter-out rule="reject"
```

Фильтр принимает только маршруты с нужной меткой, не принимает маршрут по умолчанию
и запрещает отправку маршрутов роутера в приложение.

### 2. Добавьте BGP-соединение

Для **RouterOS 7.20 и новее**:

```routeros
/routing bgp instance
add name=antifilter as=65455 router-id=192.168.55.1

/routing bgp connection
add name=antifilter-bird instance=antifilter \
    remote.address=192.168.55.5 remote.as=64500 \
    local.address=192.168.55.1 local.role=ebgp multihop=yes \
    input.filter=antifilter-in output.filter-chain=antifilter-out
```

Для **RouterOS 7 до 7.20** вместо предыдущего блока:

```routeros
/routing bgp connection
add name=antifilter-bird as=65455 router-id=192.168.55.1 routing-table=main \
    remote.address=192.168.55.5 remote.as=64500 \
    local.address=192.168.55.1 local.role=ebgp multihop=yes \
    input.filter=antifilter-in output.filter-chain=antifilter-out
```

Адреса, AS и community должны совпадать с настройками приложения.
Разрешите TCP 179 между этими двумя адресами, если firewall блокирует соединение.

### 3. Проверьте

```routeros
/routing bgp session print
/ip route print where bgp
```

У сессии ожидается флаг `E` (Established), у принятых маршрутов — шлюз вашего VPN.
Проверьте доступ к ресурсу из списка с устройства за роутером.
Если сессия есть, но трафик не проходит, проверьте шлюз, NAT, правила FastTrack
и допустимые адреса VPN-пира.

Примеры сверены с документацией MikroTik:
[BGP-соединения](https://manual.mikrotik.com/docs/user-guides/routing-and-networking-protocols/unicast/bgp/peering-sessions/),
[фильтры маршрутов](https://manual.mikrotik.com/docs/user-guides/routing-and-networking-protocols/route-selection-and-filtering/).
Применение на реальном RouterOS в рамках автоматических тестов проекта не проверяется.

## Address List вместо BGP

1. В настройках приложения задайте `HEALTHCHECK_REQUIRE_BGP=0` и примените настройки.
2. Откройте **Инструменты → Показать маршруты** в панели.
3. Укажите имя списка, например `bgp-antifilter`, и нажмите **Скачать Address List .rsc**.
4. Загрузите файл в **Files** на MikroTik и выполните:

```routeros
/import file-name=bgp-antifilter.rsc
```

Если ваша версия RouterOS поддерживает проверку импорта без применения, сначала выполните
`/import file-name=bgp-antifilter.rsc verbose=yes dry-run=yes`.

Файл содержит последний успешно применённый набор IPv4-подсетей.
Имя списка: 1–64 латинские буквы, цифры или символы `_.-`.
Во время обновления или при отсутствии рабочего набора скачивание недоступно.

Повторный импорт обновляет собственные записи и удаляет устаревшие.
Ручные записи сохраняются. Не используйте для своих записей зарезервированный
префикс комментария `bgp-antifilter:managed:`.
Импортируйте файл целиком и не запускайте одновременно два импорта в один список.
Большой список может импортироваться долго; при ошибке возможен частичный результат.

Скачивание и импорт выполняются вручную: обновления в приложении не обновляют Address List на роутере.
Настройте правила firewall/mangle и направление в VPN на MikroTik отдельно.
