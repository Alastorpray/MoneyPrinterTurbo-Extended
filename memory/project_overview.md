---
name: Project Overview
description: MoneyPrinterTurbo-Extended — automated video generation with AI text, TTS, subtitles, image generation, and semantic video matching
type: project
---

Enhanced fork of MoneyPrinterTurbo for automated short video generation.

**Stack:** Python, Streamlit (webui), FastAPI (api), TOML config.

**Key directories:**
- `app/services/` — core logic: LLM, TTS (voice), AI image gen, subtitle, video composition, semantic video matching, series, material sourcing
- `app/models/` — data schemas (VideoParams, MaterialInfo, etc.)
- `app/config/` — TOML-based config
- `webui/Main.py` — Streamlit UI
- `main.py` — entry point

**Features:** LLM-based script generation (Gemini, OpenAI, Ollama, LM Studio, etc.), multiple TTS providers (Edge, ElevenLabs, Chatterbox), AI image generation, Pexels/Pixabay video material sourcing, semantic video matching, subtitle generation, storyboard preview, content series support, smart transitions.

**Why:** Automated creation of short-form video content from text topics/keywords.
**How to apply:** Understand that changes touch a pipeline: topic → LLM script → TTS audio → visuals (AI or stock) → subtitle → video composition.
