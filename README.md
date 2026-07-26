# Rick

Walking-tour generation pipeline with a Supabase-backed local development
environment.

## Local development

Prerequisites:

- Docker Desktop
- Node.js and npm
- `uv`
- AWS SAM CLI 1.151 or newer

Install dependencies and create your local secrets file:

```bash
make install
```

Set `GOOGLE_API_KEY`, `GOOGLE_MAPS_API_KEY`, `LOGFIRE_TOKEN`, and
`MAPBOX_ACCESS_TOKEN` in `.env`, then start the local stack. They are used for
Gemini, Google Maps Places, Logfire tracing, and the checkpoint map shown to
the planning agent:

```bash
make up
```

Stop the stack without deleting locally generated tours:

```bash
make down
```

Other useful commands are `make status`, `make test`, `make build`, and
`make grant-credits EMAIL=user@example.com AMOUNT=5`. `make dev` is an alias
for `make up`.

`scripts/dev.py` supplies the local Supabase URL and publishable key to Vite.
For a standalone frontend build or deployment, set the two variables listed
in `frontend/.env.example` in the hosting environment.

This builds the Lambda image and starts local Supabase, the SAM Lambda emulator,
and the PWA together. The browser always sends commands through the Edge
Function, which uses the AWS SDK to invoke the same image and handler locally
and in production. Restart `make up` after changing Python code so the image is
rebuilt.

Local URLs:

- Supabase API: `http://127.0.0.1:54321`
- Supabase Studio: `http://127.0.0.1:54323`
- Local Lambda endpoint: `http://127.0.0.1:3001`
- PWA: `http://127.0.0.1:5173`

Local demo logins:

```text
demo@rick.local
password123

reviewer@rick.local
password123
```

Use the reviewer account to browse public tours and see reviews from a
different user's perspective. It intentionally has no generation credits.

The seed also creates three credits and one Edinburgh tour awaiting review.

You can install the local PWA from Chrome's address bar. Service workers and
installation are supported on `localhost`/`127.0.0.1`; HTTPS is required when
the app is deployed.

## Users and credits

Users can sign themselves up from the PWA. An administrator can also create a
user under **Authentication → Users** in Supabase Studio.

Grant credits to an existing user by email:

```bash
make grant-credits EMAIL=user@example.com AMOUNT=5
```

The command uses the local Supabase instance when it is running. In a deployed
environment, set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` before running
it. The service-role key is an admin secret and must never be exposed to the
PWA. One credit is deducted transactionally when a plan is approved.

## Database changes

The schema is owned by SQL files in `supabase/migrations/`; Python Pydantic
models validate records but never create tables.

Create and apply a migration locally:

```bash
npx supabase migration new describe_the_change
npm run supabase:reset
```

`supabase db reset` rebuilds the local database from every committed migration
and then loads `supabase/seed.sql`.

## Production deployment

Production deploys run locally from a clean `master` checkout using the values
in the git-ignored `.env` file:

```bash
make deploy
```

The command runs the test suite, applies pending Supabase migrations, builds
and deploys the Lambda image and SAM stack, deploys the Supabase Edge Function,
and publishes the frontend to Cloudflare Pages. Each component can also be
deployed independently:

```bash
make deploy-db
make deploy-worker
make deploy-edge
make deploy-frontend
```

The production defaults can be overridden as Make variables, for example
`make deploy AWS_REGION=eu-west-1 AWS_STACK_NAME=rick-production`.

## Command flow

The PWA invokes the authenticated `tour-commands` Supabase Edge Function. It
creates an idempotent tour job and returns `202`; the PWA then polls Supabase
for progress. Locally, the Edge Function invokes the Lambda image through SAM's
local AWS endpoint. The same private Lambda handler runs in production and
writes results directly to Supabase with the service-role key.

In production set `WORKER_INVOKER=aws`, `AWS_REGION`, and
`WORKER_FUNCTION_NAME` as Edge Function secrets, along with AWS credentials
that can only invoke that function. Supply the Google, Google Maps, and Mapbox
secrets to the Lambda stack, including `LogfireToken`. The Lambda has no
Function URL or API Gateway route.

## Tests

```bash
uv run python -m unittest discover -s tests -v
uv run ty check src tests
```
