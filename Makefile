COMPOSE_FILE=docker-compose.dev.yml

.PHONY: up down logs ps restart sh sh-%

up:
	docker compose -f $(COMPOSE_FILE) up --build

down:
	docker compose -f $(COMPOSE_FILE) down -v

logs-%:
	docker compose -f $(COMPOSE_FILE) logs -f $*

ps:
	docker compose -f $(COMPOSE_FILE) ps

restart-%:
	docker compose -f $(COMPOSE_FILE) restart $*

sh-%:
	docker compose -f $(COMPOSE_FILE) exec $* sh

test:
	bash tests/run_tests.sh
