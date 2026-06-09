.PHONY: test shellcheck compose-config build up down logs ps reload dry-run check-sources check-ip version

IP ?= 1.2.3.4
VERSION ?= $(shell cat VERSION)

test:
	python -m unittest discover -s tests

shellcheck:
	shellcheck entrypoint.sh healthcheck.sh reload-routes.sh

compose-config:
	docker compose config

build:
	docker compose build

version:
	@echo $(VERSION)

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f bird

ps:
	docker compose ps

reload:
	docker compose exec bird /reload-routes.sh

dry-run:
	docker compose exec bird /update-routes.py --dry-run

check-sources:
	docker compose exec bird /update-routes.py --check-sources

check-ip:
	docker compose exec bird /check-ip.py $(IP)
