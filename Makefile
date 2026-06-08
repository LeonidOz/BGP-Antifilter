.PHONY: test shellcheck compose-config build up down logs ps reload dry-run check-ip

IP ?= 1.2.3.4

test:
	python -m unittest discover -s tests

shellcheck:
	shellcheck entrypoint.sh healthcheck.sh reload-routes.sh

compose-config:
	docker compose config

build:
	docker compose build

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

check-ip:
	docker compose exec bird /check-ip.py $(IP)
