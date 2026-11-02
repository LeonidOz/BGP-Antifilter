# Portainer

Стек из `deploy/portainer-stack.yml` рассчитан на Docker Standalone под Linux.
Он запускает BIRD и панель из одного готового образа. Репозиторий на Docker-хосте
не требуется.

1. Создайте стек и вставьте YAML.
2. В Environment variables задайте `BGP_ANTIFILTER_IMAGE`, `ADMIN_PASSWORD`,
   `MT_IP`, `BIRD_IP`, `ROUTER_ID`, `MY_AS` и `MT_AS`.
3. Разверните стек. Панель доступна по адресу `http://<Docker-хост>:8080`.
   Другой порт задаётся через `ADMIN_PORT`.

`BGP_ANTIFILTER_IMAGE` — опубликованный тег или digest образа. Для локальной
сборки можно выполнить `docker build -t bgp-antifilter:local -f deploy/Dockerfile .`
и указать `bgp-antifilter:local` на том же Docker-хосте.

Конфигурация, списки, кеш и журналы хранятся в томе `bgp-antifilter-data`.
Чтобы использовать существующий именованный том, задайте `BGP_DATA_VOLUME`
и `BGP_DATA_EXTERNAL=true`. Старый bind mount `./generated` нужно перенести
в именованный том отдельно. Для второго стека выберите другое имя тома.

Панель сохраняет списки и запускает обновление маршрутов через общий сокет BIRD.
Настройки, требующие перезапуска BIRD, применяются после пересоздания `bird`
в Portainer. Образ также обновляется через Portainer; встроенный updater
в этом стеке отключён.

При необходимости задайте `HTTP_PROXY`, `HTTPS_PROXY` и `NO_PROXY` в окружении
стека. Локальные адреса в `NO_PROXY` перечисляйте явно. По умолчанию генератор
использует системный DNS; указание `DNS_RESOLVERS` в панели включает отдельный
HTTP-клиент с прямыми запросами и обходит HTTP-прокси.

Оба контейнера используют сеть хоста. Порт BGP и порт панели должны быть свободны.
Стек не требует `NET_ADMIN`, privileged-режима или доступа к Docker socket.
