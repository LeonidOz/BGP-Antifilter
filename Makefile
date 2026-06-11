.PHONY: test shellcheck compose-config build up down logs ps reload dry-run check-sources check-ip version

IP ?= 1.2.3.4
VERSION ?= $(shell cat VERSION)
COMPOSE := docker compose

test:
	python -m unittest discover -s tests

shellcheck:
	shellcheck deploy/entrypoint.sh deploy/healthcheck.sh deploy/reload-routes.sh

compose-config:
	$(COMPOSE) config

build:
	$(COMPOSE) build

version:
	@echo $(VERSION)

up:
	$(COMPOSE) up -d --build

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
