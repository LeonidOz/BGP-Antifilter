.PHONY: test build up down logs ps reload dry-run check-ip

IP ?= 1.2.3.4

test:
	python -m unittest discover -s tests

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

