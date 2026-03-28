"""
Content Series Service
Generates episodic video series from a topic, splitting into multiple short episodes.
"""
import json
import os
import re
from datetime import datetime
from typing import List, Optional

from loguru import logger

from app.config import config
from app.services.llm import _generate_response
from app.utils import utils


SERIES_DIR = os.path.join(utils.storage_dir("series", create=True))


def get_all_series() -> List[dict]:
    """List all saved series"""
    series_list = []
    if not os.path.exists(SERIES_DIR):
        return series_list

    for folder in sorted(os.listdir(SERIES_DIR)):
        md_path = os.path.join(SERIES_DIR, folder, "series.md")
        if os.path.isfile(md_path):
            meta = _parse_series_file(md_path)
            if meta:
                meta["folder"] = folder
                series_list.append(meta)
    return series_list


def load_series(folder: str) -> Optional[dict]:
    """Load a series from its folder"""
    md_path = os.path.join(SERIES_DIR, folder, "series.md")
    if not os.path.isfile(md_path):
        return None
    return _parse_series_file(md_path)


def research_topic(topic: str, num_episodes: int, language: str = "es") -> dict:
    """
    Use the LLM to research a topic and generate a full series plan.
    Returns a dict with title, summary, and list of episodes.
    """
    prompt = f"""
# Role: Content Series Planner

## Task:
Research the topic below and create a plan for a video series of {num_episodes} short episodes (each ~60 seconds when narrated).

## Topic: {topic}

## Requirements:
1. First, write a comprehensive summary of the topic (2-3 paragraphs covering the full story/subject).
2. Then split the content into exactly {num_episodes} episodes, each building on the previous one.
3. Each episode must have:
   - A catchy title
   - A brief description (1-2 sentences) of what this episode covers
4. The series must have narrative continuity — each episode connects to the next.
5. Respond in {language}.
6. Return ONLY valid JSON in this exact format, no markdown, no code blocks:

{{"title": "Series Title", "summary": "Full topic summary...", "episodes": [{{"part": 1, "title": "Episode Title", "description": "What this episode covers"}}, {{"part": 2, "title": "Episode Title", "description": "What this episode covers"}}]}}
""".strip()

    logger.info(f"Researching topic: {topic}, episodes: {num_episodes}")

    for attempt in range(3):
        try:
            response = _generate_response(prompt=prompt)
            if not response:
                logger.warning(f"Empty response, attempt {attempt + 1}")
                continue

            # Clean response - remove markdown code blocks if present
            response = response.strip()
            response = re.sub(r'^```json\s*', '', response)
            response = re.sub(r'^```\s*', '', response)
            response = re.sub(r'\s*```$', '', response)
            response = response.strip()

            data = json.loads(response)

            if "title" in data and "episodes" in data:
                logger.success(f"Series plan generated: {data['title']} ({len(data['episodes'])} episodes)")
                return data
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON (attempt {attempt + 1}): {e}")
        except Exception as e:
            logger.error(f"Failed to research topic (attempt {attempt + 1}): {e}")

    return {}


def generate_episode_script(series_data: dict, episode_part: int, language: str = "es", paragraph_number: int = 8) -> str:
    """
    Generate a full narration script for a specific episode.
    """
    episode = None
    for ep in series_data.get("episodes", []):
        if ep["part"] == episode_part:
            episode = ep
            break

    if not episode:
        logger.error(f"Episode {episode_part} not found")
        return ""

    total_episodes = len(series_data.get("episodes", []))
    series_title = series_data.get("title", "")
    summary = series_data.get("summary", "")

    # Find next episode for the hook
    next_episode = None
    for ep in series_data.get("episodes", []):
        if ep["part"] == episode_part + 1:
            next_episode = ep
            break

    hook_instruction = ""
    if next_episode:
        hook_instruction = f"""
7. End with an engaging hook that teases the next episode: "{next_episode['title']}"
   Use something like "In the next episode we'll discover..." or "But that's not all... in part {episode_part + 1}..."
"""
    else:
        hook_instruction = """
7. This is the final episode. End with a powerful conclusion that wraps up the entire series.
"""

    prompt = f"""
# Role: Video Script Narrator

## Task:
Write a narration script for episode {episode_part} of {total_episodes} of the series "{series_title}".

## Series Context:
{summary}

## This Episode:
- Title: {episode['title']}
- Description: {episode['description']}

## Requirements:
1. Write a script that takes approximately 60 seconds to narrate (about 150-180 words).
2. The script MUST have EXACTLY {paragraph_number} paragraphs separated by blank lines. Each paragraph = 1 visual scene.
3. Start with a brief hook that grabs attention immediately.
4. If this is not episode 1, briefly reference what happened in the previous episode.
5. Cover the content described in the episode description.
6. Use a dramatic, engaging narrative tone.
7. Do NOT include any formatting, titles, markdown, or speaker indicators.
{hook_instruction}
9. Respond in {language}.
10. Return ONLY the raw narration text with exactly {paragraph_number} paragraphs separated by blank lines.
""".strip()

    logger.info(f"Generating script for episode {episode_part}: {episode['title']}")

    for attempt in range(3):
        try:
            response = _generate_response(prompt=prompt)
            if response:
                # Clean up
                script = response.strip()
                script = script.replace("*", "").replace("#", "")
                script = re.sub(r"\[.*?\]", "", script)
                script = re.sub(r"\(.*?\)", "", script)
                logger.success(f"Episode {episode_part} script generated ({len(script.split())} words)")
                return script
        except Exception as e:
            logger.error(f"Failed to generate episode script (attempt {attempt + 1}): {e}")

    return ""


def save_series(series_data: dict, folder: str = None) -> str:
    """
    Save series to a .md file. Returns the folder name.
    """
    if not folder:
        # Create folder from title
        title = series_data.get("title", "untitled")
        folder = re.sub(r'[^\w\s-]', '', title).strip().lower()
        folder = re.sub(r'[\s]+', '-', folder)
        folder = folder[:50]  # Limit length
        # Add timestamp to avoid collisions
        folder = f"{folder}-{datetime.now().strftime('%Y%m%d')}"

    series_path = os.path.join(SERIES_DIR, folder)
    os.makedirs(series_path, exist_ok=True)

    md_path = os.path.join(series_path, "series.md")

    total = len(series_data.get("episodes", []))
    generated = sum(1 for ep in series_data.get("episodes", []) if ep.get("script"))

    lines = []
    lines.append(f"# {series_data.get('title', 'Untitled Series')}")
    lines.append(f"")
    lines.append(f"**Estado:** {generated}/{total} generados")
    lines.append(f"**Creado:** {series_data.get('created', datetime.now().strftime('%Y-%m-%d'))}")
    lines.append(f"")
    lines.append(f"## Resumen")
    lines.append(f"")
    lines.append(series_data.get("summary", ""))
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    for ep in series_data.get("episodes", []):
        status = "✅" if ep.get("script") else "⏳"
        lines.append(f"### Parte {ep['part']}: {ep['title']} {status}")
        lines.append(f"")
        lines.append(f"**Descripción:** {ep['description']}")
        lines.append(f"")
        if ep.get("script"):
            lines.append(f"**Guion:**")
            lines.append(f"")
            lines.append(ep["script"])
            lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

    # Also save raw JSON for easy reloading
    json_path = os.path.join(series_path, "series.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(series_data, f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.success(f"Series saved to {series_path}")
    return folder


def _parse_series_file(md_path: str) -> Optional[dict]:
    """Parse a series from its JSON file (falling back to .md metadata)"""
    json_path = md_path.replace("series.md", "series.json")

    if os.path.isfile(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to parse series JSON: {e}")

    # Fallback: parse basic info from .md
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()

        title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else "Unknown"

        estado_match = re.search(r'\*\*Estado:\*\* (\d+)/(\d+)', content)
        generated = int(estado_match.group(1)) if estado_match else 0
        total = int(estado_match.group(2)) if estado_match else 0

        return {
            "title": title,
            "summary": "",
            "episodes": [],
            "_generated": generated,
            "_total": total,
        }
    except Exception as e:
        logger.warning(f"Failed to parse series md: {e}")
        return None
