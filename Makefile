# This is the Makefile for the project.
# It is used to run the application in a development environment.
# run `make help` to see the available commands.

COMPOSE_FILE=docker-compose.dev.yml
REPO ?= mongo
DC = docker compose -f $(COMPOSE_FILE)
INFRA_COMPOSE_FILE=docker-compose.infra.yml
DC_INFRA = docker compose -f $(INFRA_COMPOSE_FILE)

# Compute environment to pass into docker compose based on REPO selection
ifeq ($(REPO),mongo)
  ifdef MONGO_URL
    COMPOSE_ENV=REPO_BACKEND=mongo MONGO_URL=$(MONGO_URL)
  else
    COMPOSE_ENV=REPO_BACKEND=mongo MONGO_URL=mongodb://mongo:27017
  endif
else ifeq ($(REPO),memory)
  COMPOSE_ENV=REPO_BACKEND=memory
else
  $(error Invalid REPO '$(REPO)'. Use 'mongo' or 'memory')
endif

.PHONY: help up up-mongo up-memory down logs ps restart sh sh-% test infra-up infra-down

help:
	@echo "Available targets:" && \
	awk -F: '/^[a-zA-Z0-9_.-]+:([^=]|$$)/ && $$1 !~ /%/ {print "  -", $$1}' $(firstword $(MAKEFILE_LIST)) | sort -u && \
	echo "\nSpecial Usage:" && \
	echo "  make up [REPO=mongo|memory]" && \
	echo "\nInfra:" && \
	echo "  make infra-up     # start Mongo and infra" && \
	echo "  make infra-down   # stop infra" && \
	echo "\nCurrent defaults:" && \
	echo "  COMPOSE_FILE=$(COMPOSE_FILE)" && \
	echo "  REPO=$(REPO)"

up:
	$(DC_INFRA) up -d
	$(COMPOSE_ENV) $(DC) up --build

# Convenience shortcuts
up-mongo:
	$(MAKE) up REPO=mongo

up-memory:
	$(MAKE) up REPO=memory

down:
	$(DC) down -v

infra-up:
	$(DC_INFRA) up -d

infra-down:
	$(DC_INFRA) down

logs-%:
	$(DC) logs -f $*

ps:
	$(DC) ps

restart-%:
	$(DC) restart $*

sh-%:
	$(DC) exec $* sh

test:
	bash tests/run_all.sh
