# M7 AI Workflow Modernization

This milestone closes the remaining AI workflow gaps that were still open after the runtime, orchestration, and frontend modernization work.

## Delivered

- summary and translation workers now use a shared typed Ollama client with health checks and structured JSON parsing
- summarization jobs accept an optional `content_profile` so users can steer output toward generic media, meetings, podcasts, lectures, or interviews
- summaries now persist structured AI metadata and named variants alongside the rendered markdown
- summary generation now produces chapters, highlights, keywords, action items, named entities, open questions, and risks
- the summary workspace now exposes profile-aware generation controls and renders the structured enrichment sections directly
- translation controls remain profileable through style guides and glossary terms, with subtitle QA metrics stored on translated transcripts

## Main Files

- `backend/app/ai/ollama_client.py`
- `backend/app/summarization/summarizer.py`
- `backend/app/summarization/worker.py`
- `backend/app/translation/ollama_client.py`
- `backend/app/api/app.py`
- `backend/app/persistence/models.py`
- `frontend/src/components/VideoSummary.tsx`
- `frontend/src/components/VideoSummary.test.tsx`

## Remaining Work After M7

The next roadmap milestone is M8, which focuses on hardening, cleanup, metrics, backups, and release preparation.
