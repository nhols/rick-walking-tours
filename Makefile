.PHONY: install up dev down status build test grant-credits

install: .env
	npm install
	npm --prefix frontend install
	uv sync

.env:
	cp .env.example .env

up:
	npm run dev

dev: up

down:
	npm run supabase:stop

status:
	npm run supabase:status

build:
	npm --prefix frontend run build

test:
	uv run python -m unittest discover -s tests -v
	uv run ty check src tests scripts/grant_credits.py
	npm --prefix frontend run build

grant-credits:
	@test -n "$(EMAIL)" || (echo "EMAIL is required" && exit 1)
	@test -n "$(AMOUNT)" || (echo "AMOUNT is required" && exit 1)
	npm run credits:grant -- "$(EMAIL)" "$(AMOUNT)"
