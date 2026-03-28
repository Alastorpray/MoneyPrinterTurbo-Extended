import os
import sys
import json
from uuid import uuid4

import streamlit as st
from loguru import logger

# Add project root to path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from app.config import config
from app.services import series, voice
from app.services import task as tm
from app.models.schema import VideoParams, VideoAspect, VideoConcatMode
from app.utils import utils

# Load translations
i18n_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "i18n")
locales = utils.load_locales(i18n_dir)

if "ui_language" not in st.session_state:
    st.session_state["ui_language"] = config.ui.get("language", utils.get_system_locale())


def tr(key):
    loc = locales.get(st.session_state["ui_language"], {})
    return loc.get("Translation", {}).get(key, key)


st.set_page_config(
    page_title="Content Series",
    page_icon="🎬",
    layout="wide",
)

st.title("Content Series")
st.caption("Create episodic video series from any topic — generate videos directly")

# Initialize session state
if "series_data" not in st.session_state:
    st.session_state["series_data"] = None
if "series_folder" not in st.session_state:
    st.session_state["series_folder"] = None

# --- Tabs ---
tab_new, tab_load = st.tabs(["New Series", "Load Series"])

# ===================== NEW SERIES TAB =====================
with tab_new:
    st.subheader("Create New Series")

    col1, col2 = st.columns([3, 1])

    with col1:
        topic = st.text_input(
            "Topic",
            placeholder="e.g., La historia de los Atlantes, El origen del universo, Misterios de Egipto...",
            help="Enter a topic, title, or even a URL. The AI will research and create a series plan.",
        )

    with col2:
        num_episodes = st.number_input(
            "Number of Episodes",
            min_value=2,
            max_value=50,
            value=10,
            step=1,
        )

    language = st.selectbox(
        "Series Language",
        options=["es", "en", "pt", "fr", "de", "it", "ja", "ko"],
        format_func=lambda x: {
            "es": "Español", "en": "English", "pt": "Português",
            "fr": "Français", "de": "Deutsch", "it": "Italiano",
            "ja": "日本語", "ko": "한국어"
        }.get(x, x),
        index=0,
        key="series_language",
    )

    if st.button("Research & Plan Series", type="primary", disabled=not topic):
        with st.spinner("AI is researching the topic and planning episodes..."):
            result = series.research_topic(topic, num_episodes, language)

            if result and result.get("episodes"):
                result["created"] = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
                result["language"] = language
                for ep in result["episodes"]:
                    if "script" not in ep:
                        ep["script"] = ""
                    if "video_generated" not in ep:
                        ep["video_generated"] = False

                st.session_state["series_data"] = result
                st.session_state["series_folder"] = None
                st.success(f"Series planned: **{result['title']}** — {len(result['episodes'])} episodes")
            else:
                st.error("Failed to generate series plan. Check your LLM configuration.")

# ===================== LOAD SERIES TAB =====================
with tab_load:
    st.subheader("Load Existing Series")

    all_series = series.get_all_series()

    if not all_series:
        st.info("No saved series found. Create a new one first.")
    else:
        for s in all_series:
            total = len(s.get("episodes", []))
            generated = sum(1 for ep in s.get("episodes", []) if ep.get("script"))
            if total == 0:
                total = s.get("_total", 0)
                generated = s.get("_generated", 0)

            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"**{s.get('title', 'Untitled')}** — {generated}/{total} episodes generated")
            with col2:
                if st.button("Load", key=f"load_{s['folder']}"):
                    loaded = series.load_series(s["folder"])
                    if loaded:
                        st.session_state["series_data"] = loaded
                        st.session_state["series_folder"] = s["folder"]
                        st.rerun()

    st.write("---")
    st.write("**Or upload a series .json file:**")
    uploaded = st.file_uploader("Upload series.json", type=["json"])
    if uploaded:
        try:
            data = json.load(uploaded)
            if "title" in data and "episodes" in data:
                st.session_state["series_data"] = data
                st.session_state["series_folder"] = None
                st.success(f"Loaded: **{data['title']}**")
                st.rerun()
            else:
                st.error("Invalid series file format")
        except Exception as e:
            st.error(f"Failed to load file: {e}")

# ===================== SERIES EDITOR =====================
st.write("---")

data = st.session_state.get("series_data")

if data:
    total = len(data.get("episodes", []))
    generated = sum(1 for ep in data.get("episodes", []) if ep.get("script"))
    videos_done = sum(1 for ep in data.get("episodes", []) if ep.get("video_generated"))

    st.header(f"{data.get('title', 'Untitled')}")

    col_prog1, col_prog2 = st.columns(2)
    with col_prog1:
        st.progress(generated / total if total > 0 else 0, text=f"Scripts: {generated}/{total}")
    with col_prog2:
        st.progress(videos_done / total if total > 0 else 0, text=f"Videos: {videos_done}/{total}")

    # Summary
    with st.expander("Series Summary", expanded=False):
        st.write(data.get("summary", "No summary available"))

    # Save / Download
    col_save, col_download = st.columns(2)
    with col_save:
        if st.button("Save Series"):
            folder = series.save_series(data, st.session_state.get("series_folder"))
            st.session_state["series_folder"] = folder
            st.success(f"Saved to `storage/series/{folder}/`")
    with col_download:
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        st.download_button(
            "Download .json",
            data=json_str,
            file_name=f"{data.get('title', 'series').replace(' ', '_')}.json",
            mime="application/json",
        )

    st.write("---")

    # ===================== VIDEO SETTINGS (shared for all episodes) =====================
    with st.expander("Video Generation Settings", expanded=False):
        st.caption("These settings apply to all videos generated from this series. They use your main page configuration by default.")

        series_video_sources = [
            ("Pexels", "pexels"),
            ("Pixabay", "pixabay"),
            ("AI Generated (Google Imagen)", "ai_generated"),
        ]
        saved_src = config.app.get("video_source", "pexels")
        src_values = [v[1] for v in series_video_sources]
        src_index = src_values.index(saved_src) if saved_src in src_values else 0

        series_video_source_sel = st.selectbox(
            "Video Source",
            options=series_video_sources,
            format_func=lambda x: x[0],
            index=src_index,
            key="series_video_source",
        )
        config.app["video_source"] = series_video_source_sel[1]

        if series_video_source_sel[1] == "ai_generated" and not config.app.get("gemini_api_key", ""):
            st.warning("Google AI API Key is required. Set it in the main page Basic Settings.")

        vc1, vc2, vc3, vc4 = st.columns(4)
        with vc1:
            video_aspect = st.selectbox(
                tr("Video Ratio"),
                options=[
                    (tr("Portrait"), VideoAspect.portrait.value),
                    (tr("Landscape"), VideoAspect.landscape.value),
                ],
                format_func=lambda x: x[0],
                index=0,
                key="series_aspect",
            )
        with vc2:
            series_paragraph_number = st.number_input(
                "Paragraphs (scenes)",
                min_value=1, max_value=20, value=8, step=1,
                help="Each paragraph = 1 visual scene/image",
                key="series_paragraph_number",
            )
        with vc3:
            video_clip_duration = st.slider("Clip Duration (s)", 2, 10, 3, key="series_clip_dur",
                help="Only used for non-AI sources. AI Generated uses per-paragraph duration.")
        with vc4:
            video_concat_mode = st.selectbox(
                tr("Video Concat Mode"),
                options=[
                    (tr("Sequential"), VideoConcatMode.sequential.value),
                    (tr("Random"), VideoConcatMode.random.value),
                    ("Semantic", VideoConcatMode.semantic.value),
                ],
                format_func=lambda x: x[0],
                index=0,
                key="series_concat",
            )

    st.write("---")

    # ===================== BATCH SCRIPT GENERATION =====================
    st.subheader("Episodes")

    pending_scripts = [ep for ep in data.get("episodes", []) if not ep.get("script")]
    if pending_scripts:
        col_batch1, col_batch2 = st.columns([3, 1])
        with col_batch1:
            if len(pending_scripts) > 1:
                batch_count = st.slider(
                    "Generate scripts in batch",
                    min_value=1,
                    max_value=len(pending_scripts),
                    value=min(5, len(pending_scripts)),
                )
            else:
                batch_count = 1
                st.write("1 episode pending")
        with col_batch2:
            if st.button(f"Generate {batch_count} Scripts", type="primary"):
                progress_bar = st.progress(0)
                series_lang = data.get("language", "es")
                for i, ep in enumerate(pending_scripts[:batch_count]):
                    progress_bar.progress(
                        i / batch_count,
                        text=f"Generating Part {ep['part']}: {ep['title']}..."
                    )
                    script = series.generate_episode_script(
                        data, ep["part"], language=series_lang,
                        paragraph_number=series_paragraph_number,
                    )
                    if script:
                        ep["script"] = script

                progress_bar.progress(1.0, text="Done!")
                folder = series.save_series(data, st.session_state.get("series_folder"))
                st.session_state["series_folder"] = folder
                st.rerun()

    # ===================== EPISODE LIST =====================
    for ep in data.get("episodes", []):
        has_script = bool(ep.get("script"))
        has_video = bool(ep.get("video_generated"))

        if has_video:
            status = "🎬"
        elif has_script:
            status = "✅"
        else:
            status = "⏳"

        with st.expander(f"Part {ep['part']}: {ep['title']} {status}", expanded=False):
            st.write(f"**Description:** {ep['description']}")

            if has_script:
                # Editable script
                edited_script = st.text_area(
                    "Script",
                    value=ep["script"],
                    height=200,
                    key=f"script_{ep['part']}",
                )
                # Save edits
                if edited_script != ep["script"]:
                    ep["script"] = edited_script

                if has_video and ep.get("video_path"):
                    st.video(ep["video_path"])
                    st.success(f"Video generated: {ep['video_path']}")

                # Generate Video button
                if st.button(
                    f"{'Regenerate' if has_video else 'Generate'} Video — Part {ep['part']}",
                    key=f"gen_video_{ep['part']}",
                    type="primary",
                ):
                    with st.spinner(f"Generating video for Part {ep['part']}..."):
                        try:
                            task_id = str(uuid4())

                            _src = config.app.get("video_source", "pexels")
                            _para_num = series_paragraph_number
                            params = VideoParams(
                                video_subject=f"{data.get('title', '')} — Part {ep['part']}: {ep['title']}",
                                video_script=edited_script,
                                video_aspect=video_aspect[1],
                                video_concat_mode=video_concat_mode[1],
                                video_clip_duration=video_clip_duration,
                                video_count=1,
                                video_source=_src,
                                voice_name=config.ui.get("voice_name", ""),
                                voice_volume=1.0,
                                voice_rate=1.0,
                                bgm_type=config.ui.get("bgm_type", "random"),
                                bgm_volume=0.2,
                                subtitle_enabled=True,
                                subtitle_position="bottom",
                                font_name=config.ui.get("font_name", "STHeitiMedium.ttc"),
                                text_fore_color=config.ui.get("text_fore_color", "#FFFFFF"),
                                font_size=config.ui.get("font_size", 60),
                                stroke_color="#000000",
                                stroke_width=1.5,
                                enable_word_highlighting=config.ui.get("enable_word_highlighting", False),
                                word_highlight_color=config.ui.get("highlight_color", "#ff0000"),
                                n_threads=2,
                                paragraph_number=_para_num,
                                ai_image_count=_para_num if _src == "ai_generated" else None,
                            )

                            log_container = st.empty()
                            log_records = []

                            def log_received(msg):
                                with log_container:
                                    log_records.append(str(msg))
                                    if len(log_records) > 20:
                                        log_records.pop(0)
                                    st.code("\n".join(log_records))

                            handler_id = logger.add(log_received)

                            result = tm.start(task_id=task_id, params=params)

                            logger.remove(handler_id)

                            if result and "videos" in result:
                                video_files = result.get("videos", [])
                                if video_files:
                                    ep["video_generated"] = True
                                    ep["video_path"] = video_files[0]
                                    st.video(video_files[0])
                                    st.success(f"Video generated for Part {ep['part']}!")

                                    # Open the folder containing the video
                                    import subprocess
                                    import platform
                                    video_dir = os.path.dirname(video_files[0])
                                    if platform.system() == "Darwin":
                                        subprocess.Popen(["open", video_dir])
                                    elif platform.system() == "Windows":
                                        os.startfile(video_dir)
                                    else:
                                        subprocess.Popen(["xdg-open", video_dir])

                                    # Auto-save
                                    folder = series.save_series(data, st.session_state.get("series_folder"))
                                    st.session_state["series_folder"] = folder
                                else:
                                    st.error("Video generation completed but no files were produced")
                            else:
                                st.error("Video generation failed")
                        except Exception as e:
                            st.error(f"Error generating video: {str(e)}")
                            logger.error(f"Series video generation error: {str(e)}")

            else:
                if st.button(f"Generate Script", key=f"gen_script_{ep['part']}"):
                    with st.spinner(f"Generating script for Part {ep['part']}..."):
                        series_lang = data.get("language", "es")
                        script = series.generate_episode_script(
                            data, ep["part"], language=series_lang,
                            paragraph_number=series_paragraph_number,
                        )
                        if script:
                            ep["script"] = script
                            folder = series.save_series(data, st.session_state.get("series_folder"))
                            st.session_state["series_folder"] = folder
                            st.rerun()
                        else:
                            st.error("Failed to generate script")

else:
    st.info("Create a new series or load an existing one to get started.")
