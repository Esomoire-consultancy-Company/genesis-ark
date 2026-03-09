.PHONY: up down status lint docs help

COMPOSE_FILE := docker-compose.yml

## up: Start all Genesis Ark platform services
up:
	docker compose -f $(COMPOSE_FILE) up -d

## down: Stop all Genesis Ark platform services
down:
	docker compose -f $(COMPOSE_FILE) down

## status: Show running service status
status:
	docker compose -f $(COMPOSE_FILE) ps

## lint: Validate docker-compose and YAML configs
lint:
	docker compose -f $(COMPOSE_FILE) config --quiet && echo "docker-compose.yml is valid"

## docs: Render documentation locally (requires Python)
docs:
	@echo "Open docs/index.md for platform documentation"

## help: List available make targets
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## //'
