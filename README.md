# WhatsApp “Ask Anything” AI Bot (Twilio + FastAPI + OpenAI)

Production-ready starter for a WhatsApp AI assistant:

- Twilio WhatsApp inbound webhook (`/webhooks/twilio/whatsapp`)
- OpenAI Responses API for replies
- Short, WhatsApp-friendly responses (auto-truncate)
- Basic per-sender conversation memory (in-memory or Redis)
- Optional async replies (recommended)
- Optional RAG + media (image/audio)

## 1) Project structure

```
app/
  api/webhook.py           # Twilio webhook
  core/config.py           # env config
  integrations/            # OpenAI + Twilio + signature validator
  memory/                  # memory backends
  prompts/system.py        # system instructions
  services/assistant.py    # orchestration
  utils/text.py            # truncation helpers
```

## 2) Local run

1. Create `.env`:
   - `cp .env.example .env`
   - Fill in `OPENAI_API_KEY`, `TWILIO_*`
2. Install deps:
   - `python -m venv .venv && source .venv/bin/activate`
   - `pip install -r requirements.txt`
3. Run:
   - `uvicorn app.main:app --reload --port 8000`

Health check: `GET http://localhost:8000/healthz`

## 3) Connect Twilio WhatsApp

1. In Twilio Console, configure your WhatsApp sender webhook URL:
   - `https://<your-domain>/webhooks/twilio/whatsapp`
2. Use a tunnel (dev): `ngrok http 8000`
3. Ensure `TWILIO_VALIDATE_SIGNATURE=true` and `TWILIO_AUTH_TOKEN` is correct.

## 4) Async reply mode (recommended)

Twilio webhooks have practical time limits; LLM calls can sometimes be slow.
If `ASYNC_REPLY=true`, we ack immediately and send the reply via Twilio REST in the background.

## 5) Docker

1. `cp .env.example .env` and fill it.
2. `docker compose up --build`

## 6) Deployment notes

- Put the API behind HTTPS (Cloud Run, ECS/Fargate, Render, Fly, etc.).
- Set `ASYNC_REPLY=true` for better reliability.
- Use Redis (`MEMORY_BACKEND=redis`) for multi-instance deployments.
- Configure observability (structured logs, error tracking).

### Example: Google Cloud Run (Docker)

High-level steps:
1. Build & push image (Artifact Registry / Docker Hub)
2. Deploy a Cloud Run service from the image
3. Set env vars (`OPENAI_API_KEY`, `TWILIO_*`, `ASYNC_REPLY=true`, `MEMORY_BACKEND=redis`, etc.)
4. Configure Twilio webhook to `https://<cloud-run-url>/webhooks/twilio/whatsapp`

## Optional: RAG (custom docs)

1. Put `.txt`/`.md` docs in `data/docs/`
2. Install extras: `pip install -r requirements-optional.txt`
3. Build index: `python scripts/build_faiss_index.py`
4. Set `RAG_ENABLED=true`

## Optional: Media (audio/image)

1. Set `MEDIA_ENABLED=true`
2. Ensure Twilio media URLs are accessible (Twilio credentials required).
