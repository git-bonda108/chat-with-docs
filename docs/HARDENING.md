# Hardening

Production-readiness posture and a staged ladder, grounded in what the code actually is: a single-file Streamlit demo with no auth, no persistence, and one external dependency (the OpenAI API).

## Current posture

| Area | State |
|---|---|
| Authentication | None. Anyone who can reach the Streamlit port can upload files and spend API credit. |
| Secrets handling | Correct for a demo: `OPENAI_API_KEY` read from the environment via python-dotenv, fail-fast if missing, no key in the repository. There is no `.gitignore`, so an accidentally created `.env` is one `git add .` away from being committed. |
| Error handling | Startup key check and two upload guards (unsupported extension, empty corpus). No handling around any OpenAI call — network errors, rate limits, and context-window overflows surface as raw exceptions in the UI. |
| Observability | None — no logging, no request IDs, no token/cost accounting. |
| Dependencies | `requirements.txt` is unpinned and includes many packages the app never imports (pandasai and its extras, pinecone, serpapi, semantic-router, langgraph, whisper, ffmpeg-python, SQLAlchemy, seaborn, scikit-learn). Larger install surface, larger CVE surface, and unpinned versions make installs non-reproducible — the legacy `langchain.*` import paths in `rag-doc.py` are the most likely breakage. |
| Data handling | Uploaded content is sent to the OpenAI API (embeddings + prompts). Temp files are deleted after loading; nothing is persisted locally. |

## Ladder to production

### Stage 1 — Identity and keys
- Add a `.gitignore` covering `.env`, `.venv/`, `__pycache__/`.
- Trim `requirements.txt` to the imports the app actually uses and pin versions.
- Put the app behind authentication before any non-local deployment (reverse-proxy auth or Streamlit's supported auth options); scope the OpenAI key to a project with a spend limit.

### Stage 2 — Robustness and monitoring
- Wrap OpenAI calls (embeddings, summary, chat) with timeout, bounded retry, and user-readable error messages.
- Enforce upload limits (file size, page count) and check corpus size before the one-shot summary to avoid context-window failures.
- Add structured logging per pipeline stage and record token usage per request (both API responses expose usage data).

### Stage 3 — Deployment
- Containerize (python slim base, non-root user); run Streamlit behind TLS.
- Move pipeline state into `st.session_state` (see ARCHITECTURE.md) so per-interaction cost is predictable before exposing the app to more than one user.
- Health endpoint / container healthcheck; pin the base image.

### Stage 4 — Compliance and data governance
- Document that uploaded documents transit to the OpenAI API, and gate deployment on whether that is acceptable for the intended document classes; use an enterprise/zero-retention API arrangement where required.
- Retention statement: the app stores nothing at rest today — keep it that way or add explicit, documented retention if persistence (e.g. a saved FAISS index) is introduced.

## Secrets removed from HEAD

None — no credentials were found in the repository at HEAD.
