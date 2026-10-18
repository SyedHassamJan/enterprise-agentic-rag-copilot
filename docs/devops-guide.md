# DevOps guide: Docker, CI and CD, step by step

This guide takes the project from "runs on my laptop" to:

```text
 git push ──► CI: lint ─┬─► tests (Py 3.11, 3.12) ─┬─► Docker build + smoke test   (every push / PR)
                        └──────────────────────────┘
 git tag v1.1.0 ──► CD: build image ──► push to GHCR ──► deploy hook ──► live app       (every release)
 manual button ──► Evaluation: 72 questions against real APIs ──► quality gate ≥ 90%   (on demand)
```

Every file mentioned already exists in the repo. The steps show you how to **run, understand and verify** each one.

---

## Part 0: Concepts in two minutes

| Term | Meaning here |
|---|---|
| **Image** | A packaged, read-only snapshot of the app: Python, dependencies and code. Built from the `Dockerfile`. |
| **Container** | A running instance of an image. You can start many containers from one image. |
| **Volume** | Storage that outlives a container. The audit log and uploads live on one. |
| **Registry** | A store for images. We use GitHub Container Registry (GHCR): `ghcr.io/<you>/<repo>`. |
| **CI** (Continuous Integration) | Every push is automatically linted, tested and built, so broken code is caught before merging. |
| **CD** (Continuous Delivery/Deployment) | Every release is automatically packaged and shipped. |
| **Workflow** | A YAML file in `.github/workflows/` that GitHub Actions runs on events (push, tag, button). |
| **Job / step** | A workflow contains jobs (each runs on a fresh virtual machine), and jobs contain steps (commands). |
| **Secret** | An encrypted variable such as an API key, stored in GitHub and never in the code. |

---

## Part 1: Prerequisites

1. **Git** (already installed) and a **GitHub account**.
2. **Docker Desktop** for Windows: https://www.docker.com/products/docker-desktop/
   - Install it, choose the **WSL 2** backend, then restart.
   - ⚠️ **Disk space.** Docker stores images on drive C: by default, and needs several GB. If C: is nearly full, open Docker Desktop → *Settings → Resources → Advanced → Disk image location* and choose a folder on D:.
   - Check that it works:
     ```powershell
     docker --version
     docker run --rm hello-world
     ```
     ✅ You should see "Hello from Docker!".
3. **Replace any API keys you've shared anywhere** (chat, screenshots) before they go into GitHub Secrets. Create new keys in the OpenAI, Pinecone and Tavily dashboards and delete the old ones.

---

## Part 2: Understand the Dockerfile

Open [`Dockerfile`](../Dockerfile). It has two **stages**:

```dockerfile
FROM python:3.12-slim AS builder         # stage 1: a throwaway build environment
RUN python -m venv /opt/venv              # dependencies go into an isolated virtualenv
COPY requirements.txt .                   # copy ONLY requirements first...
RUN pip install -r requirements.txt       # ...so this slow layer is cached until requirements change
```

```dockerfile
FROM python:3.12-slim AS runtime          # stage 2: the image we actually ship
COPY --from=builder /opt/venv /opt/venv   # take only the installed packages, no build leftovers
RUN useradd ... app                       # create an unprivileged user
COPY --chown=app:app app ./app            # copy code owned by that user
VOLUME ["/app/var"]                        # writable state (audit.db, uploads) lives here
USER app                                  # never run as root
HEALTHCHECK CMD ["python", "scripts/healthcheck.py"]   # Docker probes /api/health every 30 s
CMD ["sh", "-c", "exec uvicorn app.main:app --host \"$HOST\" --port \"$PORT\" ..."]
```

Why each choice matters, in interview language:

- **Multi-stage build:** the final image has no pip cache or build tools, so it's smaller, faster to pull, and exposes less to attackers.
- **Layer caching:** copying `requirements.txt` before the code means a code-only change rebuilds in seconds.
- **Non-root user:** if the app were compromised, the attacker wouldn't have root inside the container.
- **`exec`:** uvicorn becomes process 1 and receives `SIGTERM`, so `docker stop` shuts it down gracefully.
- **`$PORT`:** hosting platforms (Render, Railway, Cloud Run) set the port, and the image respects it.
- **The health check uses Python, not curl:** the slim image has no curl, and this way we don't add packages.

[`.dockerignore`](../.dockerignore) keeps `.env`, `venv`, `.git`, tests and evaluation files out of the image. **Secrets are never baked into images**; they're passed in at run time.

---

## Part 3: Build and run the container locally

From the project folder:

```powershell
# 1. Build the image (the first build takes a few minutes; later ones are cached)
docker build -t employee-support-copilot:local .

# 2. See it
docker images employee-support-copilot

# 3. Run it, passing secrets from .env at run time
docker run -d --name copilot -p 8080:8080 --env-file .env -v copilot-data:/app/var employee-support-copilot:local

# 4. Check it
docker ps                                   # STATUS should become "(healthy)" within ~30 s
curl.exe http://localhost:8080/api/health
curl.exe http://localhost:8080/api/ready    # {"status":"ready"} when the keys are set
docker exec copilot id                      # uid is NOT 0, so it isn't running as root
docker logs -f copilot                      # Ctrl+C to stop following

# 5. Clean up
docker rm -f copilot
```

✅ Checkpoint: open http://localhost:8080 and ask a question. It works exactly like `python run.py`.

---

## Part 4: Docker Compose

Typing long `docker run` commands gets old. [`docker-compose.yml`](../docker-compose.yml) records them once:

```powershell
docker compose up --build -d                            # build + start in the background
docker compose run --rm app python ingest_sample_kb.py  # one-off job in a temporary container
docker compose logs -f app
docker compose ps                                       # shows (healthy)
docker compose down                                     # stop; the named volume keeps your audit log
docker compose down -v                                  # stop AND delete the volume
```

Key ideas: `env_file` injects secrets at run time; the **named volume** `app-data` keeps `/app/var` between restarts; and `restart: unless-stopped` brings the app back after a crash or reboot.

---

## Part 5: Put the project on GitHub

1. Create an **empty** repository at https://github.com/new. Name it `enterprise-agentic-rag-copilot`, make it **Public**, and don't add a README, .gitignore or licence.
2. Push:
   ```powershell
   git remote add origin https://github.com/<your-username>/enterprise-agentic-rag-copilot.git
   git push -u origin main
   ```
3. Confirm `.env` is **not** on GitHub. It's listed in `.gitignore`.

✅ Checkpoint: open the **Actions** tab. The **CI** workflow starts automatically on that push.

---

## Part 6: Continuous Integration ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml))

```yaml
on:
  push: { branches: [main] }    # every push to main
  pull_request:                 # every PR
concurrency: ...                # a newer push cancels the older run
```

Three jobs:

| Job | What it proves | Key detail |
|---|---|---|
| **Lint (ruff)** | Code style and common bugs (unused imports, risky patterns) | `--output-format=github` puts errors inline on the PR diff |
| **Tests (Python 3.11, 3.12)** | 32 offline tests pass on two Python versions | A **matrix** runs the same job twice; pip cache speeds it up; JUnit results are uploaded as an artifact |
| **Docker build + smoke test** | The image builds, starts, becomes healthy, serves the UI, reports not-ready without keys, and runs as non-root | `needs: [lint, test]` means it only runs if they pass; `cache-from: type=gha` reuses layers between runs |

**Why does CI need no API keys?** The tests replace the LLM, Pinecone and Tavily with fakes ([`tests/test_agent_offline.py`](../tests/test_agent_offline.py)). CI stays free, fast and deterministic. The real-API check is a separate, manual workflow (Part 9).

Run the same checks locally before pushing:

```powershell
ruff check .
pytest -q
```

✅ Checkpoint: all three jobs are green. Add the badge to the top of the README:

```markdown
![CI](https://github.com/<your-username>/enterprise-agentic-rag-copilot/actions/workflows/ci.yml/badge.svg)
```

### Protect `main` (recommended)

*Settings → Branches* (or *Rules → Rulesets*) → add a rule for `main`:
- ✅ Require a pull request before merging.
- ✅ Require status checks to pass: select **Lint (ruff)**, **Tests (Python 3.11)**, **Tests (Python 3.12)** and **Docker build + smoke test**.

Now broken code can't reach `main`. This is the core promise of CI.

**Try it:** create a branch, add an unused import, open a PR, and watch the lint job fail and block the merge.

---

## Part 7: Continuous Delivery ([`.github/workflows/release.yml`](../.github/workflows/release.yml))

A release is triggered by a **version tag**:

```powershell
git tag v1.1.0
git push origin v1.1.0
```

The `publish` job then:

1. Logs in to **GHCR** with the built-in `GITHUB_TOKEN` (no setup needed; `permissions: packages: write` allows it).
2. Uses `docker/metadata-action` to compute tags: `1.1.0`, `1.1`, `sha-abc1234` and `latest`.
3. Builds and pushes `ghcr.io/<you>/<repo>:<tags>`.

✅ Checkpoint: your GitHub profile → **Packages** shows the image. To let anyone (or a hosting platform) pull it without credentials, open the package → *Package settings → Change visibility → Public*.

Pull it anywhere:

```powershell
docker pull ghcr.io/<your-username>/enterprise-agentic-rag-copilot:1.1.0
```

Image names on GHCR are lowercase, and the workflow lowercases them automatically.

**Semantic versioning:** `MAJOR.MINOR.PATCH`. Bump PATCH for fixes, MINOR for features, MAJOR for breaking changes. Also update `APP_VERSION` in `app/core/config.py` so `/api/health` reports it.

---

## Part 8: Deploy (Render, free tier)

1. https://render.com → **New → Web Service → Existing image** → `ghcr.io/<you>/<repo>:latest`.
2. **Environment:** add `OPENAI_API_KEY`, `PINECONE_API_KEY`, `TAVILY_API_KEY`, `ADMIN_API_KEY` and `APP_ENV=production`. Render sets `PORT` itself, and the image uses it.
3. **Health check path:** `/api/health`.
4. Deploy, then open the `https://<name>.onrender.com` URL.
5. Copy the service's **Deploy Hook** URL (*Settings → Deploy Hook*). In GitHub: *Settings → Secrets and variables → Actions → New repository secret* → name `DEPLOY_HOOK_URL`, value = the URL.

Now every `git push origin vX.Y.Z` **builds, publishes and redeploys**. The `deploy` job uses `environment: production`. Under *Settings → Environments → production* you can add **required reviewers**, which gives you a manual approval button before each deployment.

Free-tier notes:
- The service sleeps when idle, so the first request takes around 30 seconds.
- Without a paid persistent disk, `/app/var` (the audit log) resets on redeploy. That's fine for a demo.
- Set an **OpenAI monthly budget** before sharing a public link.
- The knowledge base lives in Pinecone, so no ingestion is needed on Render.

---

## Part 9: The LLM quality gate ([`.github/workflows/evaluation.yml`](../.github/workflows/evaluation.yml))

This runs the 72-question evaluation against the **real** APIs and fails if the pass rate drops below a threshold.

1. Add the repository secrets `OPENAI_API_KEY`, `PINECONE_API_KEY`, `TAVILY_API_KEY` and `ADMIN_API_KEY`.
2. **Actions → Evaluation → Run workflow**, and set the threshold (default 0.90).
3. The run summary shows the metrics table, and the full report is attached as an artifact.

How the gate works: `python -m eval.run_eval --min-pass-rate 0.90` exits with code **2** when quality is below the bar. Any non-zero exit code fails the job.

It's manual on purpose: each run costs about $0.25. Uncomment the `schedule:` block to run it weekly.

**Interview point:** unit tests prove the *code* works; the evaluation gate proves the *AI* still answers correctly after a prompt, model or data change.

---

## Part 10: Dependabot ([`.github/dependabot.yml`](../.github/dependabot.yml))

Every week, GitHub opens pull requests to update pip packages, GitHub Actions versions and the Docker base image. CI tests each one, so you merge only when everything is green.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `docker: command not found` | Start Docker Desktop and open a new terminal |
| The build fails with "no space left on device" | Free disk space, move the Docker disk image to D: (Part 1), and run `docker system prune` |
| The container is `unhealthy` | `docker logs <name>`. Usually the app crashed on startup; check the environment variables |
| `/api/ready` returns 503 in the container | Keys weren't passed: use `--env-file .env`, or set them in the platform |
| The CI Docker job fails at "Wait until healthy" | Read the "Container logs" step output at the bottom of the job |
| GHCR push is denied | The workflow needs `permissions: packages: write` (present). For forks, enable Actions write permissions in *Settings → Actions → General* |
| Render can't pull the image | Make the GHCR package public (Part 7), or add registry credentials in Render |
| The deploy job says "skipped" | The `DEPLOY_HOOK_URL` secret isn't set. That's expected until Part 8 |

---

## What to say about this in an interview

- "Every push runs lint, tests on two Python versions, and a **Docker build with a smoke test** that checks health, readiness and that the container isn't running as root. Merges to main are blocked unless all of that passes."
- "Tests replace the LLM and vector store with **fakes**, so CI is free and deterministic. A separate **LLM evaluation gate** runs the real system against 72 labelled questions and fails below 90%."
- "Releases are **tag-driven**: a semver tag builds a multi-stage, non-root image, pushes it to GHCR with version and commit-SHA tags, and triggers deployment through a deploy hook behind a protected environment with manual approval."
- "Secrets never enter the image or the repo; they come from GitHub Secrets or platform environment variables at run time. State lives on a volume, so the container itself is disposable."
- "Dependabot keeps dependencies, Actions and the base image current, with CI as the safety net."
