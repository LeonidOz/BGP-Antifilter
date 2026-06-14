.PHONY: test smoke-test shellcheck compose-config build up down logs ps reload dry-run check-sources check-ip version release-version update

IP ?= 1.2.3.4
VERSION ?= $(shell cat VERSION)
COMPOSE := docker compose

test:
	python -m unittest discover -s tests

smoke-test:
	RUN_DOCKER_SMOKE=1 python -m unittest tests.test_smoke_docker -v

shellcheck:
	shellcheck deploy/entrypoint.sh deploy/healthcheck.sh deploy/reload-routes.sh

compose-config:
	$(COMPOSE) config

build:
	$(COMPOSE) build

version:
	@echo $(VERSION)

release-version:
	python scripts/release_version.py $(VERSION)

up:
	$(COMPOSE) up -d --build

update:
	@test -f .env || { echo ".env not found"; exit 1; }
	@git pull --ff-only
	@current="$$(cat VERSION)"; \
	tmp="$$(mktemp)"; \
	awk -v version="$$current" 'BEGIN { found = 0 } /^BGP_ANTIFILTER_VERSION=/ { print "BGP_ANTIFILTER_VERSION=" version; found = 1; next } { print } END { if (!found) print "BGP_ANTIFILTER_VERSION=" version }' .env > "$$tmp" && mv "$$tmp" .env; \
	echo "BGP_ANTIFILTER_VERSION=$$current"
	$(COMPOSE) up -d --build --remove-orphans

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f bird admin

ps:
	$(COMPOSE) ps

reload:
	$(COMPOSE) exec bird /reload-routes.sh

dry-run:
	$(COMPOSE) exec bird /update-routes.py --dry-run

check-sources:
	$(COMPOSE) exec bird /update-routes.py --check-sources

check-ip:
	$(COMPOSE) exec bird /check-ip.py $(IP)
