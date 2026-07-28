AWS_REGION ?= eu-west-2
AWS_STACK_NAME ?= rick-production
ECR_REPOSITORY ?= rick-worker
EDGE_FUNCTION ?= tour-commands
DEPLOY_BRANCH ?= master

.PHONY: install up dev down status build test grant-credits \
	deploy deploy-check deploy-db deploy-worker deploy-edge deploy-frontend

install: .env
	npm install
	npm --prefix frontend install
	uv sync

.env:
	cp .env.example .env

up:
	npm run dev

dev: down
	$(MAKE) up

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

deploy: deploy-check
	$(MAKE) test
	$(MAKE) deploy-db
	$(MAKE) deploy-worker
	$(MAKE) deploy-edge
	$(MAKE) deploy-frontend
	@echo "Production deployment complete."

deploy-check:
	@test -f .env || (echo ".env is required" && exit 1)
	@command -v aws >/dev/null || (echo "aws CLI is required" && exit 1)
	@command -v docker >/dev/null || (echo "Docker is required" && exit 1)
	@command -v sam >/dev/null || (echo "AWS SAM CLI is required" && exit 1)
	@branch="$$(git branch --show-current)"; \
		test "$$branch" = "$(DEPLOY_BRANCH)" || \
		(echo "Deploy from $(DEPLOY_BRANCH), not $$branch" && exit 1)
	@git diff --quiet && git diff --cached --quiet || \
		(echo "Commit tracked changes before deploying" && exit 1)

deploy-db:
	@echo "Deploying Supabase migrations..."
	@set -a; . ./.env; set +a; \
		test -n "$$SUPABASE_PROJECT_REF" || (echo "SUPABASE_PROJECT_REF is required in .env" && exit 1); \
		npx supabase link --project-ref "$$SUPABASE_PROJECT_REF"; \
		npx supabase db push

deploy-worker:
	@echo "Building and deploying the AWS worker..."
	@set -a; . ./.env; set +a; \
		for name in SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY GOOGLE_API_KEY GOOGLE_MAPS_API_KEY LOGFIRE_TOKEN MAPBOX_ACCESS_TOKEN; do \
			eval "value=\$$$${name}"; \
			test -n "$$value" || (echo "$$name is required in .env" && exit 1); \
		done; \
		AWS_ACCOUNT_ID="$$(aws sts get-caller-identity --query Account --output text)"; \
		ECR_URI="$$AWS_ACCOUNT_ID.dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPOSITORY)"; \
		IMAGE_URI="$$ECR_URI:$$(git rev-parse --short=12 HEAD)"; \
		aws ecr get-login-password --region "$(AWS_REGION)" | \
			docker login --username AWS --password-stdin "$$AWS_ACCOUNT_ID.dkr.ecr.$(AWS_REGION).amazonaws.com"; \
		docker buildx build \
			--platform linux/arm64 \
			--provenance=false \
			--sbom=false \
			--file infra/aws/Dockerfile \
			--output "type=image,name=$$IMAGE_URI,push=true,oci-mediatypes=false" \
			.; \
		sam deploy \
			--template-file infra/aws/template.yaml \
			--stack-name "$(AWS_STACK_NAME)" \
			--region "$(AWS_REGION)" \
			--resolve-s3 \
			--capabilities CAPABILITY_IAM \
			--image-repositories "WorkerFunction=$$ECR_URI" \
			--no-confirm-changeset \
			--no-fail-on-empty-changeset \
			--parameter-overrides \
				WorkerImageUri="$$IMAGE_URI" \
				SupabaseUrl="$$SUPABASE_URL" \
				SupabaseServiceRoleKey="$$SUPABASE_SERVICE_ROLE_KEY" \
				GoogleApiKey="$$GOOGLE_API_KEY" \
				GoogleMapsApiKey="$$GOOGLE_MAPS_API_KEY" \
				LogfireToken="$$LOGFIRE_TOKEN" \
				MapboxAccessToken="$$MAPBOX_ACCESS_TOKEN"

deploy-edge:
	@echo "Deploying the Supabase Edge Function..."
	@set -a; . ./.env; set +a; \
		test -n "$$SUPABASE_PROJECT_REF" || (echo "SUPABASE_PROJECT_REF is required in .env" && exit 1); \
		npx supabase functions deploy "$(EDGE_FUNCTION)" --project-ref "$$SUPABASE_PROJECT_REF"

deploy-frontend:
	@echo "Building and deploying Cloudflare Pages..."
	@set -a; . ./.env; set +a; \
		VITE_SUPABASE_URL="$${VITE_SUPABASE_URL:-$$SUPABASE_URL}"; \
		export VITE_SUPABASE_URL; \
		for name in VITE_SUPABASE_URL VITE_SUPABASE_ANON_KEY CLOUDFLARE_ACCOUNT_ID CLOUDFLARE_API_TOKEN CLOUDFLARE_PAGES_PROJECT; do \
			eval "value=\$$$${name}"; \
			test -n "$$value" || (echo "$$name is required in .env" && exit 1); \
		done; \
		npm --prefix frontend ci; \
		npm --prefix frontend run build; \
		npx --yes wrangler@4 pages deploy frontend/dist \
			--project-name "$$CLOUDFLARE_PAGES_PROJECT" \
			--branch "$(DEPLOY_BRANCH)"

grant-credits:
	@test -n "$(EMAIL)" || (echo "EMAIL is required" && exit 1)
	@test -n "$(AMOUNT)" || (echo "AMOUNT is required" && exit 1)
	npm run credits:grant -- "$(EMAIL)" "$(AMOUNT)"
