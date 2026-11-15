# Подключение FRRouting

[Общая схема BGP](bgp.md) | [Установка приложения](../README.md) | [English](frr.en.md)

Пример проверяется интеграционным тестом с FRR 10.7.1 и BIRD 3.4.0. Тест проверяет приём и отзыв префиксов, community, отклонение default route, замену next hop и установку маршрута в Linux. Работу вашего VPN нужно проверить отдельно.

## Адреса примера

| Сторона | Адрес | AS |
| --- | --- | --- |
| BGP Antifilter / BIRD | `192.168.55.5` | `64500` |
| Маршрутизатор с FRR | `192.168.55.1` | `65455` |
| VPN-шлюз, доступный с FRR | `10.10.10.1` | — |

В приложении задайте `PEER_IP=192.168.55.1`, `PEER_AS=65455`, `BIRD_IP=192.168.55.5`, `MY_AS=64500`, `BGP_COMMUNITY=65432,500`. Адреса и AS замените на свои. TCP 179 должен проходить между BIRD и FRR.

## Настройка FRR

1. Установите FRRouting на маршрутизатор и включите `bgpd=yes` в `/etc/frr/daemons`. Для установки маршрутов в Linux должен работать zebra.
2. Откройте [готовую конфигурацию](examples/frr.conf). Замените адреса, AS, community и VPN-шлюз. Для существующего FRR объедините нужные блоки с вашей конфигурацией: полный файл является примером новой установки.
3. Примените настройки штатным способом вашей ОС. На Debian/Ubuntu после включения нового демона требуется `sudo systemctl restart frr`; это перезапустит и другие сессии FRR.

Ключевой входящий фильтр из примера:

```frr
ip prefix-list ANTIFILTER-V4 seq 5 deny 0.0.0.0/0
ip prefix-list ANTIFILTER-V4 seq 10 permit 0.0.0.0/0 ge 8 le 32
bgp community-list standard ANTIFILTER permit 65432:500
route-map ANTIFILTER-IN permit 10
 match ip address prefix-list ANTIFILTER-V4
 match community ANTIFILTER
 set ip next-hop 10.10.10.1
exit
route-map ANTIFILTER-IN deny 100
exit
```

Фильтр подключается к peer в направлении `in`; `ANTIFILTER-OUT` запрещает все исходящие анонсы. Полная конфигурация также задаёт remote AS, update-source, multihop и активацию IPv4. Если вам нужны разрешённые приложением префиксы короче /8, осознанно согласуйте prefix-list со своей политикой.

Шлюз `10.10.10.1` должен быть достижим через VPN-интерфейс в таблице Linux. Включите IPv4 forwarding на маршрутизаторе; проверьте firewall, маршруты/AllowedIPs VPN и NAT, если он нужен вашей схеме. Приложение не выполняет эти настройки на FRR-сервере.

## Проверка

```bash
sudo vtysh -c 'show bgp ipv4 unicast summary'
sudo vtysh -c 'show bgp ipv4 unicast community 65432:500'
sudo vtysh -c 'show ip route bgp'
ip route get <IP_из_списка>
```

У peer должны отображаться принятые префиксы, а не Idle/Active или `(Policy)`. Для выбранного префикса проверьте `show bgp ipv4 unicast <префикс>`: community должна быть `65432:500`, next hop — ваш VPN-шлюз. В системной таблице должен появиться тот же маршрут. Затем проверьте HTTPS с устройства за маршрутизатором.

Если префикс виден в BGP, но не установлен в Linux, проверьте zebra, достижимость VPN next hop и конкурирующие маршруты. Если есть `(Policy)`, проверьте привязку route-map в обоих направлениях. Экспорт `.rsc` для FRR не используется.

Официальная документация: [BGP и community](https://docs.frrouting.org/en/latest/bgp.html), [route-map и set ip next-hop](https://docs.frrouting.org/en/latest/routemap.html), [образы FRR](https://frrouting.org/release/).
