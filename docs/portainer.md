# Portainer

Стек из `deploy/portainer-stack.yml` рассчитан на Docker Standalone под Linux.
Он запускает BIRD, scheduler и панель в одном контейнере `bgp-antifilter`
под управлением supervisord из готового образа. Репозиторий на Docker-хосте
не требуется.

1. Создайте стек и вставьте YAML.
2. В Environment variables задайте `BGP_ANTIFILTER_IMAGE`, `ADMIN_PASSWORD`,
   `MT_IP`, `BIRD_IP`, `ROUTER_ID`, `MY_AS` и `MT_AS`.
3. Разверните стек. Панель доступна по адресу `http://<Docker-хост>:8080`.
   Другой порт задаётся через `ADMIN_PORT`.

`BGP_ANTIFILTER_IMAGE` — опубликованный тег или digest образа. Для локальной
сборки можно выполнить `docker build -t bgp-antifilter:local -f deploy/Dockerfile .`
и указать `bgp-antifilter:local` на том же Docker-хосте.

Для этого стека нужен образ с одноконтейнерным runtime и поддержкой URL-списков
доменов: текущий `ghcr.io/leonidoz/bgp-antifilter:edge` после принятия PR #2
или последующий релиз. Старые образы до этих изменений несовместимы со стеком.

Конфигурация, списки, кеш и журналы хранятся в томе `bgp-antifilter-data`.
Чтобы использовать существующий именованный том, задайте `BGP_DATA_VOLUME`
и `BGP_DATA_EXTERNAL=true`. Старый bind mount `./generated` нужно перенести
в именованный том отдельно. Для второго стека выберите другое имя тома,
измените `container_name` и настройте отдельные порты и BGP-адреса.

Панель сохраняет списки и запускает обновление маршрутов через общий сокет BIRD.
Настройки, требующие перезапуска BIRD, применяются после пересоздания `bgp-antifilter`
в Portainer. Образ также обновляется через Portainer; встроенный updater
в этом стеке отключён.

При необходимости задайте `HTTP_PROXY`, `HTTPS_PROXY` и `NO_PROXY` в окружении
стека. Локальные адреса в `NO_PROXY` перечисляйте явно. По умолчанию генератор
использует системный DNS; указание `DNS_RESOLVERS` в панели включает отдельный
HTTP-клиент с прямыми запросами и обходит HTTP-прокси.

Контейнер использует сеть хоста. `BIRD_IP` должен принадлежать Linux-хосту.
Windows/Docker Desktop поддерживается только как dev-среда, не для реальной BGP-сессии.
Порт BGP и порт панели должны быть свободны.
Стек не требует `NET_ADMIN`, privileged-режима или доступа к Docker socket.
