"""
AI Image Generation Service
Generates images using Stable Horde (free) or Google Gemini API, and converts them to video clips.
"""
import base64
import os
import time
from typing import List, Optional, Tuple

import requests
from loguru import logger
from PIL import Image

from app.config import config
from app.services.llm import _generate_response
from app.utils import utils


def research_topic(subject: str, language: str = "", api_key: str = "") -> dict:
    """
    Use Gemini with Google Search grounding to research a topic AND its visual style in one call.
    Returns a dict with 'topic_research' and 'visual_style' keys.
    """
    if not api_key:
        api_key = config.app.get("gemini_api_key", "")
    if not api_key:
        logger.error("No Gemini API key for research")
        return {}

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.error("google-genai package not installed")
        return {}

    client = genai.Client(api_key=api_key)

    lang_instruction = f"Write the TOPIC RESEARCH section in {language}." if language else "Write the TOPIC RESEARCH section in the same language as the subject."

    search_prompt = f"""
Search the web for detailed, up-to-date information about: "{subject}"

Return your response in TWO clearly separated sections using these exact headers:

===TOPIC RESEARCH===
Write a comprehensive research summary (~300 words) covering:
- Key facts, plot, or description of the subject
- Important details, characters, people, or elements involved
- Context, background, and why it's relevant or interesting
- Recent news or developments if applicable
- Interesting angles or lesser-known facts
{lang_instruction}
Do NOT write a video script — just provide raw research material that a scriptwriter can use.

===VISUAL STYLE===
Write a visual style guide (~100 words, in English) for AI image generation covering:
- Color palette: specific colors and tones
- Lighting style: type and mood
- Set design / environments: key visual elements
- Camera style: typical framing, angles, lens choices
- Overall mood / atmosphere
- Art direction references: similar styles from film, photography, or art
- Costume / character look: typical clothing, appearance style
Do NOT include character names, logos, or trademarked elements — describe the visual essence only.
""".strip()

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=search_prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
        result = response.text.strip()
        result = result.replace("**", "").replace("*", "")

        # Parse the two sections
        topic_research = ""
        visual_style = ""

        if "===VISUAL STYLE===" in result:
            parts = result.split("===VISUAL STYLE===", 1)
            topic_research = parts[0]
            visual_style = parts[1].strip()
        elif "===TOPIC RESEARCH===" in result:
            topic_research = result
        else:
            topic_research = result

        # Clean up topic research header
        topic_research = topic_research.replace("===TOPIC RESEARCH===", "").strip()

        logger.success(f"Research complete for: {subject} (topic: {len(topic_research)} chars, style: {len(visual_style)} chars)")
        return {
            "topic_research": topic_research,
            "visual_style": visual_style,
        }
    except Exception as e:
        logger.error(f"Research failed: {e}")
        return {}


def generate_image_prompts(paragraphs: List[str], language: str = "en", visual_style: str = "", research_context: str = "") -> List[str]:
    """
    Use the LLM to generate one image prompt per paragraph of the video script.
    Each paragraph represents one visual scene.
    """
    num_paragraphs = len(paragraphs)

    style_section = ""
    if visual_style:
        style_section = f"""
## Visual Style & References (provided by user):
{visual_style}

IMPORTANT: Use the above description as the primary guide for the visual style, color palette, mood, and atmosphere of every prompt. All generated prompts MUST be consistent with this style.
"""

    research_section = ""
    if research_context:
        research_section = f"""
## Factual Research Context (use this for accurate visual details):
{research_context}

IMPORTANT: Use the above research to make image prompts accurate — include real locations, settings, architectural details, costumes, and atmosphere that match the actual subject. Do NOT copy trademarked elements, but capture the authentic visual essence.
"""

    # Build numbered paragraph list for the LLM
    paragraph_list = ""
    for i, p in enumerate(paragraphs):
        paragraph_list += f"\n### Paragraph {i + 1}:\n{p}\n"

    prompt = f"""
# Role: Expert Cinematic Visual Prompt Generator

## Task:
You are given a video script divided into {num_paragraphs} paragraphs. Each paragraph is one scene in the video.
Generate EXACTLY {num_paragraphs} image prompts — one per paragraph — that visually represent the content of that paragraph.

## Script Paragraphs:
{paragraph_list}
{style_section}{research_section}
## Prompt Generation Rules:
1. **One prompt per paragraph**: Prompt 1 illustrates Paragraph 1, Prompt 2 illustrates Paragraph 2, etc.
2. **Visual Style Consistency**: Identify the genre, tone, and visual aesthetic. Every prompt must reflect a consistent style.
3. **Detailed Scene Description**: Each prompt must describe a concrete, specific scene — not abstract concepts. Include:
   - **Subject**: Who/what is in the scene, their posture, expression, clothing
   - **Setting**: Specific environment details (architecture, furniture, nature)
   - **Lighting**: Type (fluorescent, natural, neon), direction, shadows, intensity
   - **Color palette**: Dominant colors and tones (cold/warm, desaturated/vivid)
   - **Camera**: Angle (low, high, eye-level), lens (wide, telephoto, macro), framing (symmetrical, rule of thirds)
   - **Mood/Atmosphere**: The emotional feeling the image should evoke
4. **Inspired, Not Copied**: If the script references known media, capture the *visual essence and atmosphere* without reproducing exact characters, logos, or trademarked elements. Use generic descriptions.
5. **Cinematic Quality**: Reference film photography styles when appropriate.
6. **Varied Composition**: Alternate between wide establishing shots, medium shots, and close-ups for visual rhythm.
7. **Prompts must be in English** (for best AI image generation results).
8. **Return ONLY a JSON array of {num_paragraphs} strings**, no markdown, no code blocks.

## Example output format:
["prompt for paragraph 1", "prompt for paragraph 2", ...]

Return exactly {num_paragraphs} prompts as a JSON array.
""".strip()

    import json
    import re

    for attempt in range(3):
        try:
            response = _generate_response(prompt=prompt)
            if not response:
                continue

            response = response.strip()
            response = re.sub(r'^```json\s*', '', response)
            response = re.sub(r'^```\s*', '', response)
            response = re.sub(r'\s*```$', '', response)

            prompts = json.loads(response)
            if isinstance(prompts, list) and len(prompts) > 0:
                # Enforce exact count: trim or pad to match paragraph count
                if len(prompts) > num_paragraphs:
                    prompts = prompts[:num_paragraphs]
                while len(prompts) < num_paragraphs:
                    prompts.append(prompts[-1])
                logger.success(f"Generated {len(prompts)} image prompts (1 per paragraph)")
                return prompts
        except Exception as e:
            logger.warning(f"Failed to generate image prompts (attempt {attempt + 1}): {e}")

    # Fallback: generic prompts based on each paragraph
    logger.warning("Using fallback generic prompts")
    return [f"Cinematic scene illustrating: {p[:100]}" for p in paragraphs]


# ===================== Stable Horde (Free, no API key required) =====================

def generate_image_horde(prompt: str, aspect_ratio: str = "9:16", output_path: str = None) -> Optional[str]:
    """
    Generate an image using Stable Horde API (free, crowdsourced GPU network).
    """
    # Determine dimensions from aspect ratio
    if aspect_ratio == "16:9":
        width, height = 1024, 576
    elif aspect_ratio == "1:1":
        width, height = 768, 768
    else:  # 9:16
        width, height = 576, 1024

    api_key = "0000000000"  # Anonymous key (free tier)

    try:
        logger.info(f"Requesting image from Stable Horde: {prompt[:80]}...")

        # Submit generation request
        payload = {
            "prompt": f"{prompt} ### cinematic, photorealistic, 8k, detailed",
            "params": {
                "width": width,
                "height": height,
                "steps": 25,
                "cfg_scale": 7.0,
                "sampler_name": "k_euler_a",
            },
            "nsfw": False,
            "models": ["SDXL 1.0"],
            "r2": True,
        }

        r = requests.post(
            "https://stablehorde.net/api/v2/generate/async",
            json=payload,
            headers={"apikey": api_key},
            timeout=30,
        )

        if r.status_code not in (200, 202):
            logger.error(f"Horde submit failed: {r.status_code} {r.text[:200]}")
            return None

        job_id = r.json().get("id")
        if not job_id:
            logger.error("No job ID returned from Horde")
            return None

        logger.info(f"Horde job submitted: {job_id}, waiting for completion...")

        # Poll for completion (max ~10 minutes)
        for _ in range(200):
            time.sleep(3)
            check = requests.get(
                f"https://stablehorde.net/api/v2/generate/check/{job_id}",
                timeout=15,
            )
            if check.status_code != 200:
                continue

            status = check.json()
            if status.get("done"):
                break

            queue_pos = status.get("queue_position", "?")
            wait_time = status.get("wait_time", "?")
            logger.info(f"Horde queue position: {queue_pos}, est. wait: {wait_time}s")
        else:
            logger.error("Horde generation timed out after 3 minutes")
            return None

        # Fetch result
        result = requests.get(
            f"https://stablehorde.net/api/v2/generate/status/{job_id}",
            timeout=30,
        )

        if result.status_code != 200:
            logger.error(f"Horde status failed: {result.status_code}")
            return None

        generations = result.json().get("generations", [])
        if not generations:
            logger.error("No generations returned from Horde")
            return None

        img_url = generations[0].get("img")
        if not img_url:
            logger.error("No image URL in Horde response")
            return None

        # Download the image
        if img_url.startswith("http"):
            img_response = requests.get(img_url, timeout=60)
            image_bytes = img_response.content
        else:
            # Base64 encoded
            image_bytes = base64.b64decode(img_url)

        if not output_path:
            output_dir = utils.storage_dir("ai_images", create=True)
            output_path = os.path.join(output_dir, f"img-{int(time.time())}.png")

        with open(output_path, "wb") as f:
            f.write(image_bytes)

        logger.success(f"Horde image saved: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Horde image generation failed: {e}")
        return None


# ===================== Google Gemini (requires billing) =====================

def generate_image_gemini(prompt: str, api_key: str, aspect_ratio: str = "9:16", output_path: str = None) -> Optional[str]:
    """
    Generate an image using Google Gemini API (requires paid plan for image generation).
    """
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.error("google-genai package not installed. Run: pip install google-genai")
        return None

    client = genai.Client(api_key=api_key)
    models = ["gemini-2.5-flash-image", "gemini-2.0-flash-exp"]

    for attempt in range(3):
        for model_name in models:
            try:
                logger.info(f"Generating image with Gemini (attempt {attempt + 1}, {model_name}): {prompt[:60]}...")

                response = client.models.generate_content(
                    model=model_name,
                    contents=f"Generate a photorealistic, cinematic image: {prompt}",
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                    ),
                )

                image_data = None
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.data:
                        image_data = part.inline_data.data
                        break

                if image_data:
                    if not output_path:
                        output_dir = utils.storage_dir("ai_images", create=True)
                        output_path = os.path.join(output_dir, f"img-{int(time.time())}-{attempt}.png")

                    if isinstance(image_data, str):
                        image_bytes = base64.b64decode(image_data)
                    else:
                        image_bytes = image_data

                    with open(output_path, "wb") as f:
                        f.write(image_bytes)

                    logger.success(f"Gemini image saved: {output_path}")
                    return output_path

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    logger.warning(f"Rate limited on {model_name}, waiting...")
                    time.sleep(10)
                elif "400" in error_str and ("not support" in error_str.lower() or "limit: 0" in error_str):
                    logger.warning(f"{model_name} doesn't support image gen or quota exhausted, trying next...")
                    break
                else:
                    logger.error(f"Gemini image gen failed ({model_name}): {e}")
                    time.sleep(3)

    return None


# ===================== Unified generate_image =====================

def generate_image(prompt: str, api_key: str = "", aspect_ratio: str = "9:16", output_path: str = None) -> Optional[str]:
    """
    Generate an image. Tries Gemini first (if API key with billing), falls back to Stable Horde (free).
    """
    # Try Gemini first if API key is available
    if api_key:
        result = generate_image_gemini(prompt, api_key, aspect_ratio, output_path)
        if result:
            return result
        logger.info("Gemini failed, falling back to Stable Horde...")

    # Fallback: Stable Horde (free)
    return generate_image_horde(prompt, aspect_ratio, output_path)


# ===================== Image to Video =====================

def image_to_video_clip(
    image_path: str,
    duration: float,
    output_path: str,
    resolution: Tuple[int, int] = (1080, 1920),
    zoom: bool = True,
) -> Optional[str]:
    """
    Convert a static image to a video clip with Ken Burns effect (slow zoom/pan).
    """
    try:
        from moviepy import ImageClip, vfx

        target_w, target_h = resolution

        clip = ImageClip(image_path, duration=duration)

        # Resize to fill the target resolution
        img_w, img_h = clip.size
        scale = max(target_w / img_w, target_h / img_h) * 1.2  # 20% extra for zoom
        clip = clip.resized(scale)

        # Center crop
        clip = clip.cropped(
            x_center=clip.size[0] / 2,
            y_center=clip.size[1] / 2,
            width=target_w,
            height=target_h,
        )

        if zoom:
            # Ken Burns: slow zoom in from 1.0 to 1.15 over the duration
            def zoom_effect(get_frame, t):
                import numpy as np
                from PIL import Image as PILImage

                frame = get_frame(t)
                h, w = frame.shape[:2]
                progress = t / duration
                zoom_factor = 1.0 + (0.15 * progress)

                new_h = int(h / zoom_factor)
                new_w = int(w / zoom_factor)
                y_start = (h - new_h) // 2
                x_start = (w - new_w) // 2

                cropped = frame[y_start:y_start + new_h, x_start:x_start + new_w]

                img = PILImage.fromarray(cropped)
                img = img.resize((w, h), PILImage.LANCZOS)
                return np.array(img)

            clip = clip.transform(zoom_effect)

        clip.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio=False,
            logger=None,
        )

        clip.close()
        logger.success(f"Image converted to video: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Failed to convert image to video: {e}")
        return None


# ===================== Full Pipeline =====================

def generate_ai_video_materials(
    paragraphs: List[str],
    api_key: str = "",
    clip_durations: List[float] = None,
    aspect_ratio: str = "9:16",
    resolution: Tuple[int, int] = (1080, 1920),
    predefined_prompts: List[str] = None,
    audio_duration: float = 0,
) -> List[dict]:
    """
    Full pipeline: generate image prompts (1 per paragraph), create images, convert to video clips.
    Each clip duration matches its paragraph's audio duration.
    Uses Gemini if API key has billing, otherwise falls back to Stable Horde (free).
    """
    num_clips = len(paragraphs)
    logger.info(f"Starting AI image generation pipeline: {num_clips} clips (1 per paragraph)")
    if api_key:
        logger.info("Gemini API key provided — will try Gemini first, Stable Horde as fallback")
    else:
        logger.info("No Gemini API key — using Stable Horde (free, may be slower)")

    # Step 1: Use predefined prompts or generate from paragraphs
    if predefined_prompts and len(predefined_prompts) >= num_clips:
        prompts = predefined_prompts[:num_clips]
        logger.info(f"Using {len(prompts)} predefined image prompts")
    else:
        prompts = generate_image_prompts(paragraphs)

    # Ensure we have enough prompts
    while len(prompts) < num_clips:
        prompts.append(prompts[-1] if prompts else "A cinematic establishing shot")

    # Log all prompts for visibility
    logger.info(f"=== AI Image Prompts ({num_clips} — 1 per paragraph) ===")
    for i, p in enumerate(prompts[:num_clips]):
        dur_str = f" [{clip_durations[i]:.1f}s]" if clip_durations and i < len(clip_durations) else ""
        logger.info(f"  Paragraph {i + 1}{dur_str}: {p}")
    logger.info("=== End Prompts ===")

    # Use provided durations or calculate proportional ones
    if not clip_durations and audio_duration > 0:
        # Calculate proportional durations based on word count per paragraph
        total_words = sum(len(p.split()) for p in paragraphs)
        clip_durations = []
        for p in paragraphs:
            word_count = len(p.split())
            dur = max(2.0, (word_count / total_words) * audio_duration) if total_words > 0 else audio_duration / num_clips
            clip_durations.append(round(dur, 2))
        # Adjust to match audio_duration exactly
        diff = audio_duration - sum(clip_durations)
        clip_durations[-1] = round(clip_durations[-1] + diff, 2)

    if not clip_durations:
        clip_durations = [5.0] * num_clips

    logger.info(f"Clip durations (total={sum(clip_durations):.1f}s): {clip_durations}")

    materials = []
    output_dir = utils.storage_dir("ai_images", create=True)

    for i, img_prompt in enumerate(prompts[:num_clips]):
        this_duration = clip_durations[i] if i < len(clip_durations) else 5.0
        logger.info(f"Generating clip {i + 1}/{num_clips} ({this_duration:.1f}s) — Prompt: {img_prompt[:80]}...")

        # Step 2: Generate image
        img_path = os.path.join(output_dir, f"ai-img-{int(time.time())}-{i}.png")
        result = generate_image(img_prompt, api_key, aspect_ratio, img_path)

        if not result:
            logger.warning(f"Skipping clip {i + 1}: image generation failed")
            continue

        # Step 3: Convert to video clip with paragraph-matched duration
        clip_path = os.path.join(output_dir, f"ai-clip-{int(time.time())}-{i}.mp4")
        video_path = image_to_video_clip(
            result, this_duration, clip_path, resolution, zoom=True
        )

        if video_path:
            materials.append({
                "provider": "ai_generated",
                "url": video_path,
                "image_path": result,
                "duration": this_duration,
                "prompt": img_prompt,
                "paragraph": paragraphs[i][:100],
            })

        # Rate limiting
        if i < num_clips - 1:
            time.sleep(2)

    logger.success(f"AI generation complete: {len(materials)}/{num_clips} clips created")
    return materials
