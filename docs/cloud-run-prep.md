# Cloud Run: preparation (nothing here has been run against Google Cloud)

Deployment is a later phase. This page holds what could be decided and verified locally, and the
runbook to follow when it is time. The commands are **unverified**: they have never been run.

## Verified locally (2026-11-22)

The production image was run the way Cloud Run runs it: `PORT=9000` (not 8080), `ADMIN_TOKEN`,
`PUBLIC_BASE_URL=https://sandbox.example.run.app`, `LATENCY_SCALE=1`, `DRIFT=0`, 512 MB and 1 CPU.

- All three `/health` endpoints answer; every served `openapi.yaml` has `servers[0].url` rewritten to `PUBLIC_BASE_URL + /<family>` and nothing else changed; the public specs do not mention `__admin`.
- `POST /<family>/__admin/reset` and `GET /<family>/__admin/state` answer 401 with no token and with a wrong token; 204 / 200 with `Authorization: Bearer <ADMIN_TOKEN>`.
- The token appears nowhere in the container log (one structured line per request: method, path, status, duration, family).
- `docker stop` ends the container with exit code 0 (SIGTERM handled; Uvicorn `timeout_graceful_shutdown=10`, which matches Cloud Run's 10 s stop window).
- `check_expectations.py --cloud --base-url http://localhost:8090` with `ADMIN_TOKEN` set: `ok`, `contract-fail` and `conform-fail` all as expected. `--cloud` skips the `local_only` entries and the whole-spec run, which include transport behavior and bodies over 32 MB.

Not verified: memory use of the large-body cases at 512 MB (they are `local_only` and were skipped), and anything that depends on Cloud Run's own front end (HTTP/2, body-size limits, header handling).

## Proposed settings

| Setting | Value | Why |
|---|---|---|
| `--max-instances` | 1 | state is in memory; `min-instances` stays 0 (state is lost on scale-to-zero, by design) |
| `--timeout` | 60s | the longest deliberate delay is 30 s (`MAX_SLEEP_SECONDS`, also `/timeout/hang`) |
| `--concurrency` | 40 | 20 slow-request slots exist (`MAX_CONCURRENT_SLOW`); the rest is headroom for ordinary requests |
| `--cpu` / `--memory` | 1 / 1Gi | 1Gi rather than 512Mi until the 32 MB `/large` cases are tried under a limit |
| `PORT` | set by Cloud Run | the app already reads it; do not set it yourself |
| `HOST` | `0.0.0.0` | already set in the image |
| `PUBLIC_BASE_URL` | the service URL | known only after the first deploy: deploy, read the URL, update the service |
| `ADMIN_TOKEN` | Secret Manager | `--set-secrets ADMIN_TOKEN=clearsignal-admin-token:latest`; never an env literal |
| `DRIFT`, `LATENCY_SCALE` | `0`, `1` | defaults; cases that need drift 1 start their own local server |

## Runbook (to be run later)

```
PROJECT=<project>  REGION=<region>  SERVICE=api-workbench-sandbox
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com cloudbuild.googleapis.com
gcloud artifacts repositories create sandbox --repository-format=docker --location=$REGION
printf '%s' "<new random token>" | gcloud secrets create clearsignal-admin-token --data-file=-
IMAGE=$REGION-docker.pkg.dev/$PROJECT/sandbox/$SERVICE:$(git rev-parse --short HEAD)
gcloud builds submit --tag $IMAGE .            # or: docker build / docker push
gcloud run deploy $SERVICE --image $IMAGE --region $REGION \
  --max-instances 1 --min-instances 0 --concurrency 40 --timeout 60 --cpu 1 --memory 1Gi \
  --set-secrets ADMIN_TOKEN=clearsignal-admin-token:latest \
  --set-env-vars LATENCY_SCALE=1,DRIFT=0 --allow-unauthenticated   # or private: see the open decisions
URL=$(gcloud run services describe $SERVICE --region $REGION --format 'value(status.url)')
gcloud run services update $SERVICE --region $REGION --update-env-vars PUBLIC_BASE_URL=$URL
```

Then verify against the service (replace the token with the secret's value):

```
curl $URL/ok/health
curl -s $URL/ok/openapi.yaml | head                       # servers[0].url is $URL/ok
curl -i -X POST $URL/ok/__admin/reset                     # 401
ADMIN_TOKEN=<secret> uv run python scripts/check_expectations.py --expectations expectations/ok.yaml --base-url $URL --cloud
# the same for contract-fail and conform-fail; timing entries need their own look (see below)
```

## Things to settle before running it

1. **Public or private.** Public (`--allow-unauthenticated`) is what a ClearSignal user without a Google identity needs; the open endpoints cost money when hammered (30 s delays, large bodies). Private needs an identity token, which `clrsig` does not send (only bearer auth from the spec/environment is applied; F-005).
2. **Project and region.**
3. **Budget alerts** before any public exposure (CLAUDE.md): a billing budget on the project with notifications at, say, 50/90/100 percent.
4. **The token.** The fixtures' fake credentials are documented; `ADMIN_TOKEN` is the only real secret and is not in the repo.
5. **Local-only entries.** Everything marked `local_only` (`/large` over 32 MB, connection cuts, timing that depends on a Linux container) must be tried on the deployed service one at a time. Until then they stay out of the cloud expectations and README must not claim them. Timing expectations compare against request timeouts; Cloud Run's network adds latency, so margins may need cloud-specific overrides (`expectations/*.yaml` already support `local_only` and `--cloud`; per-entry cloud overrides do not exist yet).
6. **The runner's `--base-url`** with `ADMIN_TOKEN` in the environment resets families on the deployed service; two people running it at once interfere (stores are shared and global in the MVP).

## Known gaps in the prep

- No cloud-specific expectation overrides yet (needs a real deployment to know which entries differ).
- No scripted deploy: the runbook is commands, not a script, until it has run once.
- Memory under limit with the largest bodies is unmeasured.
