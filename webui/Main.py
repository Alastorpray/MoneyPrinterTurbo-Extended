import os
import platform
import sys
from uuid import uuid4
import streamlit as st
from loguru import logger


# Add the root directory of the project to the system path to allow importing modules from the project
root_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)
    print("******** sys.path ********")
    print(sys.path)
    print("")

from app.config import config
from app.models.schema import (
    MaterialInfo,
    VideoAspect,
    VideoConcatMode,
    VideoParams,
    VideoTransitionMode,
)
from app.services import llm, voice, ai_images
from app.services import task as tm
from app.utils import utils

st.set_page_config(
    page_title="MoneyPrinterTurbo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={
        "Report a bug": "https://github.com/harry0703/MoneyPrinterTurbo/issues",
        "About": "# MoneyPrinterTurbo\nSimply provide a topic or keyword for a video, and it will "
        "automatically generate the video copy, video materials, video subtitles, "
        "and video background music before synthesizing a high-definition short "
        "video.\n\nhttps://github.com/harry0703/MoneyPrinterTurbo",
    },
)


streamlit_style = """
<style>
/* ── Global ── */
h1 { padding-top: 0 !important; }

/* ── Accent palette ── */
:root {
    --accent: #6C5CE7;
    --accent-light: #a29bfe;
    --accent-bg: rgba(108, 92, 231, 0.08);
    --card-border: rgba(108, 92, 231, 0.25);
    --card-radius: 12px;
    --success: #00b894;
    --warn: #fdcb6e;
    --danger: #e17055;
    --text-muted: #888;
}

/* ── Bordered containers (Steps) ── */
div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid var(--card-border) !important;
    border-radius: var(--card-radius) !important;
    padding: 0.25rem 0.5rem !important;
    background: var(--accent-bg) !important;
}

/* ── Step headers ── */
div[data-testid="stVerticalBlockBorderWrapper"] h3 {
    color: var(--accent) !important;
    font-weight: 700 !important;
    letter-spacing: -0.3px;
    font-size: 1.15rem !important;
    border-bottom: 2px solid var(--accent-light);
    padding-bottom: 6px;
    margin-bottom: 12px !important;
}

/* ── Section labels (bold **text**) ── */
div[data-testid="stVerticalBlockBorderWrapper"] strong {
    color: var(--accent-light) !important;
    font-size: 0.95rem;
}

/* ── Primary buttons ── */
button[kind="primary"], button[data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, var(--accent), var(--accent-light)) !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
}
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 15px rgba(108, 92, 231, 0.35) !important;
}

/* ── Secondary buttons ── */
button[kind="secondary"], button[data-testid="stBaseButton-secondary"] {
    border-radius: 8px !important;
    border: 1px solid var(--card-border) !important;
    transition: background 0.15s ease !important;
}
button[kind="secondary"]:hover, button[data-testid="stBaseButton-secondary"]:hover {
    background: var(--accent-bg) !important;
}

/* ── Inputs & selects ── */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-testid="stSelectbox"] > div > div {
    border-radius: 8px !important;
    border-color: var(--card-border) !important;
    transition: border-color 0.2s ease !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(108, 92, 231, 0.15) !important;
}

/* ── Expanders ── */
details[data-testid="stExpander"] {
    border: 1px solid var(--card-border) !important;
    border-radius: 8px !important;
    background: transparent !important;
}
details[data-testid="stExpander"] summary {
    font-weight: 600 !important;
    font-size: 0.9rem !important;
}

/* ── Progress bars ── */
div[data-testid="stProgress"] > div > div > div {
    background: linear-gradient(90deg, var(--accent), var(--accent-light)) !important;
    border-radius: 4px !important;
}

/* ── Sidebar polish ── */
section[data-testid="stSidebar"] {
    border-right: 1px solid var(--card-border) !important;
}

/* ── Toast / alerts ── */
div[data-testid="stAlert"] {
    border-radius: 8px !important;
}

/* ── Script text area bigger ── */
div[data-testid="stTextArea"] textarea {
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace !important;
    font-size: 0.85rem !important;
    line-height: 1.55 !important;
}

/* ── Storyboard images ── */
div[data-testid="stImage"] img {
    border-radius: 8px !important;
    border: 1px solid var(--card-border);
}

/* ── Reduce top padding ── */
.block-container { padding-top: 1.5rem !important; }

/* ── Label styling ── */
label[data-testid="stWidgetLabel"] p {
    font-weight: 500 !important;
    font-size: 0.85rem !important;
}
</style>
"""
st.markdown(streamlit_style, unsafe_allow_html=True)

# 定义资源目录
font_dir = os.path.join(root_dir, "resource", "fonts")
song_dir = os.path.join(root_dir, "resource", "songs")
i18n_dir = os.path.join(root_dir, "webui", "i18n")
config_file = os.path.join(root_dir, "webui", ".streamlit", "webui.toml")
system_locale = utils.get_system_locale()


if "video_subject" not in st.session_state:
    st.session_state["video_subject"] = ""
if "video_script" not in st.session_state:
    st.session_state["video_script"] = ""
if "video_terms" not in st.session_state:
    st.session_state["video_terms"] = ""
if "ui_language" not in st.session_state:
    st.session_state["ui_language"] = config.ui.get("language", system_locale)
if "ai_image_prompts" not in st.session_state:
    st.session_state["ai_image_prompts"] = []
if "topic_research" not in st.session_state:
    st.session_state["topic_research"] = ""
if "storyboard" not in st.session_state:
    st.session_state["storyboard"] = []

# 加载语言文件
locales = utils.load_locales(i18n_dir)

# 创建一个顶部栏，包含标题和语言选择
title_col, lang_col = st.columns([3, 1])

with title_col:
    st.title(f"MoneyPrinterTurbo v{config.project_version}")

with lang_col:
    display_languages = []
    selected_index = 0
    for i, code in enumerate(locales.keys()):
        display_languages.append(f"{code} - {locales[code].get('Language')}")
        if code == st.session_state.get("ui_language", ""):
            selected_index = i

    selected_language = st.selectbox(
        "Language / 语言",
        options=display_languages,
        index=selected_index,
        key="top_language_selector",
        label_visibility="collapsed",
    )
    if selected_language:
        code = selected_language.split(" - ")[0].strip()
        st.session_state["ui_language"] = code
        config.ui["language"] = code

support_locales = [
    "zh-CN",
    "zh-HK",
    "zh-TW",
    "de-DE",
    "en-US",
    "es-ES",
    "es-MX",
    "fr-FR",
    "pt-BR",
    "pt-PT",
    "it-IT",
    "ja-JP",
    "ko-KR",
    "vi-VN",
    "th-TH",
]


def get_all_fonts():
    fonts = []
    for root, dirs, files in os.walk(font_dir):
        for file in files:
            if file.endswith(".ttf") or file.endswith(".ttc"):
                fonts.append(file)
    fonts.sort()
    return fonts


def get_all_songs():
    songs = []
    for root, dirs, files in os.walk(song_dir):
        for file in files:
            if file.endswith(".mp3"):
                songs.append(file)
    return songs


def open_task_folder(task_id):
    try:
        sys = platform.system()
        path = os.path.join(root_dir, "storage", "tasks", task_id)
        if os.path.exists(path):
            if sys == "Windows":
                os.system(f"start {path}")
            if sys == "Darwin":
                os.system(f"open {path}")
    except Exception as e:
        logger.error(e)


def scroll_to_bottom():
    js = """
    <script>
        console.log("scroll_to_bottom");
        function scroll(dummy_var_to_force_repeat_execution){
            var sections = parent.document.querySelectorAll('section.main');
            console.log(sections);
            for(let index = 0; index<sections.length; index++) {
                sections[index].scrollTop = sections[index].scrollHeight;
            }
        }
        scroll(1);
    </script>
    """
    st.components.v1.html(js, height=0, width=0)


def init_log():
    logger.remove()
    _lvl = "DEBUG"

    def format_record(record):
        # 获取日志记录中的文件全路径
        file_path = record["file"].path
        # 将绝对路径转换为相对于项目根目录的路径
        relative_path = os.path.relpath(file_path, root_dir)
        # 更新记录中的文件路径
        record["file"].path = f"./{relative_path}"
        # 返回修改后的格式字符串
        # 您可以根据需要调整这里的格式
        record["message"] = record["message"].replace(root_dir, ".")

        _format = (
            "<green>{time:%Y-%m-%d %H:%M:%S}</> | "
            + "<level>{level}</> | "
            + '"{file.path}:{line}":<blue> {function}</> '
            + "- <level>{message}</>"
            + "\n"
        )
        return _format

    logger.add(
        sys.stdout,
        level=_lvl,
        format=format_record,
        colorize=True,
    )


init_log()

locales = utils.load_locales(i18n_dir)


def tr(key):
    loc = locales.get(st.session_state["ui_language"], {})
    return loc.get("Translation", {}).get(key, key)


# Toggle to show/hide basic settings (always visible so user can toggle back)
hide_config = st.checkbox(
    tr("Hide Basic Settings"), value=config.app.get("hide_config", False)
)
config.app["hide_config"] = hide_config

if not hide_config:
    with st.expander(tr("Basic Settings"), expanded=False):
        config_panels = st.columns(3)
        left_config_panel = config_panels[0]
        middle_config_panel = config_panels[1]
        right_config_panel = config_panels[2]

        # 左侧面板 - 日志设置
        with left_config_panel:

            # 是否禁用日志显示
            hide_log = st.checkbox(
                tr("Hide Log"), value=config.ui.get("hide_log", False)
            )
            config.ui["hide_log"] = hide_log

        # 中间面板 - LLM 设置

        with middle_config_panel:
            st.write(tr("LLM Settings"))
            llm_providers = [
                "OpenAI",
                "Moonshot",
                "Azure",
                "Qwen",
                "DeepSeek",
                "Gemini",
                "Ollama",
                "LMStudio",
                "G4f",
                "OneAPI",
                "Cloudflare",
                "ERNIE",
                "Pollinations",
            ]
            saved_llm_provider = config.app.get("llm_provider", "OpenAI").lower()
            saved_llm_provider_index = 0
            for i, provider in enumerate(llm_providers):
                if provider.lower() == saved_llm_provider:
                    saved_llm_provider_index = i
                    break

            llm_provider = st.selectbox(
                tr("LLM Provider"),
                options=llm_providers,
                index=saved_llm_provider_index,
            )
            llm_helper = st.container()
            llm_provider = llm_provider.lower()
            config.app["llm_provider"] = llm_provider

            llm_api_key = config.app.get(f"{llm_provider}_api_key", "")
            llm_secret_key = config.app.get(
                f"{llm_provider}_secret_key", ""
            )  # only for baidu ernie
            llm_base_url = config.app.get(f"{llm_provider}_base_url", "")
            llm_model_name = config.app.get(f"{llm_provider}_model_name", "")
            llm_account_id = config.app.get(f"{llm_provider}_account_id", "")

            tips = ""
            if llm_provider == "ollama":
                if not llm_model_name:
                    llm_model_name = "qwen:7b"
                if not llm_base_url:
                    llm_base_url = "http://localhost:11434/v1"
                if not llm_api_key:
                    llm_api_key = "not-needed"

                with llm_helper:
                    st.success("**Ollama runs locally — no API key needed!**")
                    tips = """
                            ##### Ollama Configuration
                            - **API Key**: Not required (runs locally, leave as-is)
                            - **Base Url**: Default `http://localhost:11434/v1`
                                - If Ollama is on a different machine, use that machine's IP address
                                - For Docker deployments, use `http://host.docker.internal:11434/v1`
                            - **Model Name**: Run `ollama list` to see available models
                            """

            if llm_provider == "lmstudio":
                if not llm_base_url:
                    llm_base_url = "http://localhost:1234/v1"
                if not llm_api_key:
                    llm_api_key = "lm-studio"

                # Auto-detect models from LM Studio
                lmstudio_models = []
                try:
                    import requests as _requests
                    _lms_resp = _requests.get(f"{llm_base_url.rstrip('/').replace('/v1','')}/v1/models", timeout=3)
                    if _lms_resp.status_code == 200:
                        _lms_data = _lms_resp.json().get("data", [])
                        lmstudio_models = [
                            m["id"] for m in _lms_data
                            if "embed" not in m["id"].lower()
                        ]
                except Exception:
                    pass

                with llm_helper:
                    if lmstudio_models:
                        st.success(f"**LM Studio connected — {len(lmstudio_models)} model(s) detected!**")
                    else:
                        st.warning("**LM Studio not detected.** Make sure it's running with the server started.")
                    tips = """
                            ##### LM Studio Configuration
                            - **API Key**: Not required (runs locally, leave as-is)
                            - **Base Url**: Default `http://localhost:1234/v1`
                            - Select a model from the dropdown below (auto-detected from LM Studio)
                            """

                if lmstudio_models:
                    # Show detected models in a selectbox
                    saved_model = config.app.get("lmstudio_model_name", "")
                    model_index = 0
                    if saved_model in lmstudio_models:
                        model_index = lmstudio_models.index(saved_model)

                    selected_lms_model = st.selectbox(
                        "LM Studio Model (auto-detected)",
                        options=lmstudio_models,
                        index=model_index,
                        key="lmstudio_model_select",
                    )
                    llm_model_name = selected_lms_model
                    config.app["lmstudio_model_name"] = selected_lms_model

            if llm_provider == "openai":
                if not llm_model_name:
                    llm_model_name = "gpt-3.5-turbo"
                with llm_helper:
                    tips = """
                            ##### OpenAI 配置说明
                            > 需要VPN开启全局流量模式
                            - **API Key**: [点击到官网申请](https://platform.openai.com/api-keys)
                            - **Base Url**: 可以留空
                            - **Model Name**: 填写**有权限**的模型，[点击查看模型列表](https://platform.openai.com/settings/organization/limits)
                            """

            if llm_provider == "moonshot":
                if not llm_model_name:
                    llm_model_name = "moonshot-v1-8k"
                with llm_helper:
                    tips = """
                            ##### Moonshot 配置说明
                            - **API Key**: [点击到官网申请](https://platform.moonshot.cn/console/api-keys)
                            - **Base Url**: 固定为 https://api.moonshot.cn/v1
                            - **Model Name**: 比如 moonshot-v1-8k，[点击查看模型列表](https://platform.moonshot.cn/docs/intro#%E6%A8%A1%E5%9E%8B%E5%88%97%E8%A1%A8)
                            """
            if llm_provider == "oneapi":
                if not llm_model_name:
                    llm_model_name = (
                        "claude-3-5-sonnet-20240620"  # 默认模型，可以根据需要调整
                    )
                with llm_helper:
                    tips = """
                        ##### OneAPI 配置说明
                        - **API Key**: 填写您的 OneAPI 密钥
                        - **Base Url**: 填写 OneAPI 的基础 URL
                        - **Model Name**: 填写您要使用的模型名称，例如 claude-3-5-sonnet-20240620
                        """

            if llm_provider == "qwen":
                if not llm_model_name:
                    llm_model_name = "qwen-max"
                with llm_helper:
                    tips = """
                            ##### 通义千问Qwen 配置说明
                            - **API Key**: [点击到官网申请](https://dashscope.console.aliyun.com/apiKey)
                            - **Base Url**: 留空
                            - **Model Name**: 比如 qwen-max，[点击查看模型列表](https://help.aliyun.com/zh/dashscope/developer-reference/model-introduction#3ef6d0bcf91wy)
                            """

            if llm_provider == "g4f":
                if not llm_model_name:
                    llm_model_name = "gpt-3.5-turbo"
                with llm_helper:
                    tips = """
                            ##### gpt4free 配置说明
                            > [GitHub开源项目](https://github.com/xtekky/gpt4free)，可以免费使用GPT模型，但是**稳定性较差**
                            - **API Key**: 随便填写，比如 123
                            - **Base Url**: 留空
                            - **Model Name**: 比如 gpt-3.5-turbo，[点击查看模型列表](https://github.com/xtekky/gpt4free/blob/main/g4f/models.py#L308)
                            """
            if llm_provider == "azure":
                with llm_helper:
                    tips = """
                            ##### Azure 配置说明
                            > [点击查看如何部署模型](https://learn.microsoft.com/zh-cn/azure/ai-services/openai/how-to/create-resource)
                            - **API Key**: [点击到Azure后台创建](https://portal.azure.com/#view/Microsoft_Azure_ProjectOxford/CognitiveServicesHub/~/OpenAI)
                            - **Base Url**: 留空
                            - **Model Name**: 填写你实际的部署名
                            """

            if llm_provider == "gemini":
                if not llm_model_name:
                    llm_model_name = "gemini-2.5-flash"

                with llm_helper:
                    tips = """
                            ##### Gemini Configuration
                            - **API Key**: [Get it here](https://aistudio.google.com/apikey)
                            - **Base Url**: Leave empty
                            - **Model**: Select from dropdown
                            """

            if llm_provider == "deepseek":
                if not llm_model_name:
                    llm_model_name = "deepseek-chat"
                if not llm_base_url:
                    llm_base_url = "https://api.deepseek.com"
                with llm_helper:
                    tips = """
                            ##### DeepSeek 配置说明
                            - **API Key**: [点击到官网申请](https://platform.deepseek.com/api_keys)
                            - **Base Url**: 固定为 https://api.deepseek.com
                            - **Model Name**: 固定为 deepseek-chat
                            """

            if llm_provider == "ernie":
                with llm_helper:
                    tips = """
                            ##### 百度文心一言 配置说明
                            - **API Key**: [点击到官网申请](https://console.bce.baidu.com/qianfan/ais/console/applicationConsole/application)
                            - **Secret Key**: [点击到官网申请](https://console.bce.baidu.com/qianfan/ais/console/applicationConsole/application)
                            - **Base Url**: 填写 **请求地址** [点击查看文档](https://cloud.baidu.com/doc/WENXINWORKSHOP/s/jlil56u11#%E8%AF%B7%E6%B1%82%E8%AF%B4%E6%98%8E)
                            """

            if llm_provider == "pollinations":
                if not llm_model_name:
                    llm_model_name = "default"
                with llm_helper:
                    tips = """
                            ##### Pollinations AI Configuration
                            - **API Key**: Optional - Leave empty for public access
                            - **Base Url**: Default is https://text.pollinations.ai/openai
                            - **Model Name**: Use 'openai-fast' or specify a model name
                            """

            if tips and config.ui["language"] == "zh":
                if llm_provider != "ollama":
                    st.warning(
                        "中国用户建议使用 **DeepSeek** 或 **Moonshot** 作为大模型提供商\n- 国内可直接访问，不需要VPN \n- 注册就送额度，基本够用"
                    )
                st.info(tips)
            elif tips:
                st.info(tips)

            # Hide API Key for local providers
            if llm_provider not in ["ollama", "lmstudio"]:
                st_llm_api_key = st.text_input(
                    tr("API Key"), value=llm_api_key, type="password"
                )
            else:
                st_llm_api_key = llm_api_key

            st_llm_base_url = st.text_input(tr("Base Url"), value=llm_base_url)

            # Model Name selection
            st_llm_model_name = ""
            if llm_provider == "lmstudio":
                st_llm_model_name = llm_model_name
            elif llm_provider == "gemini":
                gemini_models = [
                    ("Gemini 2.0 Flash Lite (fastest, cheapest)", "gemini-2.0-flash-lite"),
                    ("Gemini 2.5 Flash Lite", "gemini-2.5-flash-lite"),
                    ("Gemini 2.5 Flash (recommended)", "gemini-2.5-flash"),
                    ("Gemini 2.0 Flash", "gemini-2.0-flash"),
                    ("Gemini 2.5 Pro (most capable)", "gemini-2.5-pro"),
                ]
                gemini_model_ids = [m[1] for m in gemini_models]
                try:
                    gemini_default_idx = gemini_model_ids.index(llm_model_name)
                except ValueError:
                    gemini_default_idx = 2  # default to gemini-2.5-flash
                selected_gemini = st.selectbox(
                    tr("Model Name"),
                    options=range(len(gemini_models)),
                    format_func=lambda x: gemini_models[x][0],
                    index=gemini_default_idx,
                    key="gemini_model_select",
                )
                st_llm_model_name = gemini_models[selected_gemini][1]
                config.app[f"{llm_provider}_model_name"] = st_llm_model_name
            elif llm_provider != "ernie":
                st_llm_model_name = st.text_input(
                    tr("Model Name"),
                    value=llm_model_name,
                    key=f"{llm_provider}_model_name_input",
                )
                if st_llm_model_name:
                    config.app[f"{llm_provider}_model_name"] = st_llm_model_name
            else:
                st_llm_model_name = None

            if st_llm_api_key:
                config.app[f"{llm_provider}_api_key"] = st_llm_api_key
            if st_llm_base_url:
                config.app[f"{llm_provider}_base_url"] = st_llm_base_url
            if st_llm_model_name:
                config.app[f"{llm_provider}_model_name"] = st_llm_model_name
            if llm_provider == "ernie":
                st_llm_secret_key = st.text_input(
                    tr("Secret Key"), value=llm_secret_key, type="password"
                )
                config.app[f"{llm_provider}_secret_key"] = st_llm_secret_key

            if llm_provider == "cloudflare":
                st_llm_account_id = st.text_input(
                    tr("Account ID"), value=llm_account_id
                )
                if st_llm_account_id:
                    config.app[f"{llm_provider}_account_id"] = st_llm_account_id

        # 右侧面板 - API 密钥设置
        with right_config_panel:

            def get_keys_from_config(cfg_key):
                api_keys = config.app.get(cfg_key, [])
                if isinstance(api_keys, str):
                    api_keys = [api_keys]
                api_key = ", ".join(api_keys)
                return api_key

            def save_keys_to_config(cfg_key, value):
                value = value.replace(" ", "")
                if value:
                    config.app[cfg_key] = value.split(",")

            st.write(tr("Video Source Settings"))

            pexels_api_key = get_keys_from_config("pexels_api_keys")
            pexels_api_key = st.text_input(
                tr("Pexels API Key"),
                value=pexels_api_key,
                type="password",
                help="Get your free API key at https://www.pexels.com/api/ — required for Pexels video source",
            )
            if pexels_api_key:
                st.caption("Pexels API Key configured")
            else:
                st.warning("Pexels API Key is required to download stock videos")
            save_keys_to_config("pexels_api_keys", pexels_api_key)

            pixabay_api_key = get_keys_from_config("pixabay_api_keys")
            pixabay_api_key = st.text_input(
                tr("Pixabay API Key"),
                value=pixabay_api_key,
                type="password",
                help="Get your free API key at https://pixabay.com/api/docs/ — required for Pixabay video source",
            )
            save_keys_to_config("pixabay_api_keys", pixabay_api_key)

            st.write("**AI Image Generation (Google AI Studio)**")
            google_ai_api_key = config.app.get("gemini_api_key", "")
            google_ai_api_key = st.text_input(
                "Google AI / Gemini API Key",
                value=google_ai_api_key,
                type="password",
                help="Get your API key at https://aistudio.google.com/apikey — used for both Gemini LLM and AI Generated images",
            )
            if google_ai_api_key:
                st.caption("Google AI API Key configured")
            else:
                st.caption("Required only if you use Gemini LLM or 'AI Generated' video source")
            config.app["gemini_api_key"] = google_ai_api_key

llm_provider = config.app.get("llm_provider", "").lower()

params = VideoParams(video_subject="")
uploaded_files = []

# =====================================================================
# STEP 1: SCRIPT
# =====================================================================
with st.container(border=True):
    st.subheader("Step 1: Script")

    # ── Topic input ──
    params.video_subject = st.text_input(
        tr("Video Subject"),
        value=st.session_state["video_subject"],
        key="video_subject_input",
        placeholder="Enter a topic, title, or URL...",
    ).strip()

    # ── Config row: Language | Duration | Paragraphs ──
    cfg_col1, cfg_col2, cfg_col3 = st.columns(3)

    with cfg_col1:
        video_languages = [(tr("Auto Detect"), "")]
        for code in support_locales:
            video_languages.append((code, code))
        selected_index = st.selectbox(
            tr("Script Language"),
            index=0,
            options=range(len(video_languages)),
            format_func=lambda x: video_languages[x][0],
        )
        params.video_language = video_languages[selected_index][1]

    with cfg_col2:
        _wps_map = {
            "es": 1.5, "fr": 1.8, "pt": 1.7, "de": 1.6, "it": 1.7,
            "ja": 1.2, "ko": 1.3, "zh": 1.2, "vi": 1.5, "th": 1.4,
        }
        wps = 2.5
        if params.video_language:
            for prefix, rate in _wps_map.items():
                if params.video_language.lower().startswith(prefix):
                    wps = rate
                    break
        video_duration_options = [
            (f"~30s (~{int(30 * wps)}w)", 30),
            (f"~1min (~{int(60 * wps)}w)", 60),
            (f"~1.5min (~{int(90 * wps)}w)", 90),
            (f"~2min (~{int(120 * wps)}w)", 120),
            (f"~3min (~{int(180 * wps)}w)", 180),
            (f"~5min (~{int(300 * wps)}w)", 300),
        ]
        selected_duration = st.selectbox(
            "Duration",
            options=range(len(video_duration_options)),
            format_func=lambda x: video_duration_options[x][0],
            index=1,
            key="video_duration_select",
        )
        target_duration = video_duration_options[selected_duration][1]

    with cfg_col3:
        paragraph_number = st.number_input(
            "Paragraphs (scenes)",
            min_value=1, max_value=20,
            value=config.app.get("paragraph_number", 8),
            step=1,
            help="Each paragraph = 1 visual scene. For AI Generated, each gets its own image.",
            key="paragraph_number_input",
        )
        config.app["paragraph_number"] = paragraph_number

    # ── Action buttons ──
    google_ai_key = config.app.get("gemini_api_key", "")
    btn_cols = [None, None, None]
    if google_ai_key:
        btn_cols = st.columns(3)
    else:
        btn_cols = [None] + list(st.columns(2))

    if google_ai_key:
        with btn_cols[0]:
            if st.button("Research Topic", key="research_topic", use_container_width=True):
                if not params.video_subject:
                    st.error(tr("Please Enter the Video Subject"))
                else:
                    with st.spinner(f"Researching \"{params.video_subject}\"..."):
                        research = ai_images.research_topic(
                            params.video_subject,
                            language=params.video_language,
                            api_key=google_ai_key,
                        )
                        if research:
                            st.session_state["topic_research"] = research.get("topic_research", "")
                            st.session_state["ai_visual_style"] = research.get("visual_style", "")
                        else:
                            st.error("Research failed. Check your Google AI API key.")

    with btn_cols[1]:
        if st.button("Generate Script + Keywords", key="auto_generate_script", type="primary", use_container_width=True):
            with st.spinner(tr("Generating Video Script and Keywords")):
                script = llm.generate_script(
                    video_subject=params.video_subject,
                    language=params.video_language,
                    paragraph_number=paragraph_number,
                    target_duration=target_duration,
                    research_context=st.session_state.get("topic_research", ""),
                )
                terms = llm.generate_terms(params.video_subject, script)
                if "Error: " in script:
                    st.error(tr(script))
                elif "Error: " in terms:
                    st.error(tr(terms))
                else:
                    st.session_state["video_script"] = script
                    st.session_state["video_terms"] = ", ".join(terms)

    with btn_cols[2]:
        if st.button("Regenerate Keywords Only", key="auto_generate_terms", use_container_width=True):
            if params.video_script or st.session_state.get("video_script"):
                with st.spinner(tr("Generating Video Keywords")):
                    _script = params.video_script or st.session_state.get("video_script", "")
                    terms = llm.generate_terms(params.video_subject, _script)
                    if "Error: " in terms:
                        st.error(tr(terms))
                    else:
                        st.session_state["video_terms"] = ", ".join(terms)

    # ── Research context (collapsible) ──
    if st.session_state["topic_research"]:
        with st.expander("Research Context", expanded=False):
            topic_research = st.text_area(
                "Research Context",
                value=st.session_state["topic_research"],
                height=120,
                label_visibility="collapsed",
            )
            st.session_state["topic_research"] = topic_research
            if st.button("Clear Research", key="clear_research"):
                st.session_state["topic_research"] = ""
                st.session_state["ai_visual_style"] = ""
                st.rerun()

    # ── Script & Keywords ──
    script_col, terms_col = st.columns([3, 1])
    with script_col:
        params.video_script = st.text_area(
            tr("Video Script"), value=st.session_state["video_script"], height=250
        )
        # Script stats
        _current_script = params.video_script or st.session_state.get("video_script", "")
        if _current_script:
            _paras = [p for p in _current_script.split("\n\n") if p.strip()]
            _words = len(_current_script.split())
            _est_secs = int(_words / wps)
            st.caption(f"{len(_paras)} paragraphs  ·  {_words} words  ·  ~{_est_secs}s estimated")
    with terms_col:
        params.video_terms = st.text_area(
            tr("Video Keywords"), value=st.session_state["video_terms"], height=250
        )

# =====================================================================
# STEP 2: VIDEO / AUDIO / SUBTITLES
# =====================================================================
with st.container(border=True):
    st.subheader("Step 2: Settings")
    video_col, audio_col, subs_col = st.columns(3)

    # --- VIDEO COLUMN ---
    with video_col:
        st.markdown("**Video**")
        video_sources = [
            (tr("Pexels"), "pexels"),
            (tr("Pixabay"), "pixabay"),
            ("AI Generated (Imagen)", "ai_generated"),
            (tr("Local file"), "local"),
            (tr("TikTok"), "douyin"),
            (tr("Bilibili"), "bilibili"),
            (tr("Xiaohongshu"), "xiaohongshu"),
        ]
        saved_video_source_name = config.app.get("video_source", "pexels")
        saved_video_source_index = [v[1] for v in video_sources].index(saved_video_source_name) if saved_video_source_name in [v[1] for v in video_sources] else 0
        selected_index = st.selectbox(
            tr("Video Source"),
            options=range(len(video_sources)),
            format_func=lambda x: video_sources[x][0],
            index=saved_video_source_index,
        )
        params.video_source = video_sources[selected_index][1]
        config.app["video_source"] = params.video_source

        if params.video_source == "local":
            uploaded_files = st.file_uploader(
                "Upload Local Files",
                type=["mp4", "mov", "avi", "flv", "mkv", "jpg", "jpeg", "png"],
                accept_multiple_files=True,
            )

        video_aspect_ratios = [
            (tr("Portrait"), VideoAspect.portrait.value),
            (tr("Landscape"), VideoAspect.landscape.value),
        ]
        selected_index = st.selectbox(
            tr("Video Ratio"),
            options=range(len(video_aspect_ratios)),
            format_func=lambda x: video_aspect_ratios[x][0],
        )
        params.video_aspect = VideoAspect(video_aspect_ratios[selected_index][1])

        video_transition_modes = [
            (tr("None"), VideoTransitionMode.none.value),
            ("Smart (content-aware)", VideoTransitionMode.smart.value),
            (tr("Shuffle"), VideoTransitionMode.shuffle.value),
            (tr("FadeIn"), VideoTransitionMode.fade_in.value),
            (tr("FadeOut"), VideoTransitionMode.fade_out.value),
            (tr("SlideIn"), VideoTransitionMode.slide_in.value),
            (tr("SlideOut"), VideoTransitionMode.slide_out.value),
        ]
        selected_index = st.selectbox(
            tr("Video Transition Mode"),
            options=range(len(video_transition_modes)),
            format_func=lambda x: video_transition_modes[x][0],
            index=0,
        )
        params.video_transition_mode = VideoTransitionMode(video_transition_modes[selected_index][1])

        video_concat_modes = [
            (tr("Sequential"), "sequential"),
            (tr("Random"), "random"),
            (tr("Semantic Text Alignment"), "semantic"),
        ]
        selected_index = st.selectbox(
            tr("Video Concat Mode"),
            index=0,
            options=range(len(video_concat_modes)),
            format_func=lambda x: video_concat_modes[x][0],
        )
        params.video_concat_mode = VideoConcatMode(video_concat_modes[selected_index][1])

        if params.video_source != "ai_generated":
            params.video_clip_duration = st.selectbox(
                tr("Clip Duration"), options=[2, 3, 4, 5, 6, 7, 8, 9, 10], index=1
            )
        else:
            params.video_clip_duration = 5

        params.video_count = st.selectbox(
            tr("Number of Videos Generated Simultaneously"),
            options=[1, 2, 3, 4, 5], index=0,
        )

        # Semantic settings in collapsible
        if params.video_concat_mode.value == "semantic":
            with st.expander("Semantic Settings", expanded=False):
                try:
                    import sentence_transformers
                    st.success("Semantic search ready")
                except ImportError:
                    st.warning("Install: `pip install sentence-transformers`")

                segmentation_methods = [
                    (tr("Split by Sentences"), "sentences"),
                    (tr("Split by Paragraphs"), "paragraphs"),
                ]
                seg_idx = st.selectbox("Segmentation", options=range(len(segmentation_methods)),
                    format_func=lambda x: segmentation_methods[x][0], index=0)
                params.segmentation_method = segmentation_methods[seg_idx][1]
                params.min_segment_length = st.slider("Min Segment Length", 10, 100, 25, step=5)
                params.similarity_threshold = st.slider("Similarity Threshold", 0.0, 1.0, 0.5, step=0.05)
                params.diversity_threshold = st.slider("Diversity Threshold", 1, 20, 5)
                params.max_video_reuse = st.slider("Max Video Reuse", 1, 10, 2)
                params.search_pool_size = st.slider("Search Pool Size", 10, 200, 50, step=10)

                semantic_models = [
                    ("MPNet Base V2", "all-mpnet-base-v2"),
                    ("MiniLM L6 V2", "all-MiniLM-L6-v2"),
                    ("MiniLM L12 V2", "all-MiniLM-L12-v2"),
                ]
                saved_sm = config.app.get("semantic_search_model", "all-mpnet-base-v2")
                sm_idx = next((i for i, (_, v) in enumerate(semantic_models) if v == saved_sm), 0)
                model_idx = st.selectbox("Semantic Model", options=range(len(semantic_models)),
                    format_func=lambda x: semantic_models[x][0], index=sm_idx)
                params.semantic_model = semantic_models[model_idx][1]

                # Image similarity
                params.enable_image_similarity = st.checkbox("Enable Image Similarity", value=False)
                if params.enable_image_similarity:
                    params.image_similarity_threshold = st.slider("Image Similarity Threshold", 0.0, 1.0, 0.7, step=0.05)
                    params.image_similarity_model = "clip-vit-base-patch32"
                else:
                    params.image_similarity_threshold = 0.7
                    params.image_similarity_model = "clip-vit-base-patch32"
        else:
            params.segmentation_method = "sentences"
            params.min_segment_length = 25
            params.similarity_threshold = 0.5
            params.diversity_threshold = 5
            params.max_video_reuse = 2
            params.search_pool_size = 50
            params.semantic_model = config.app.get("semantic_search_model", "all-mpnet-base-v2")
            params.enable_image_similarity = False
            params.image_similarity_threshold = 0.7
            params.image_similarity_model = "clip-vit-base-patch32"

    # --- AUDIO COLUMN ---
    with audio_col:
        st.markdown("**Audio**")
        tts_servers = [
            ("azure-tts-v1", "Azure TTS V1"),
            ("azure-tts-v2", "Azure TTS V2"),
            ("siliconflow", "SiliconFlow TTS"),
            ("chatterbox", "Chatterbox TTS"),
            ("elevenlabs", "ElevenLabs TTS"),
        ]
        saved_tts_server = config.ui.get("tts_server", "azure-tts-v1")
        saved_tts_server_index = next((i for i, (v, _) in enumerate(tts_servers) if v == saved_tts_server), 0)

        selected_tts_server_index = st.selectbox(
            tr("TTS Servers"),
            options=range(len(tts_servers)),
            format_func=lambda x: tts_servers[x][1],
            index=saved_tts_server_index,
        )
        selected_tts_server = tts_servers[selected_tts_server_index][0]
        config.ui["tts_server"] = selected_tts_server

        filtered_voices = []
        if selected_tts_server == "siliconflow":
            filtered_voices = voice.get_siliconflow_voices()
        elif selected_tts_server == "chatterbox":
            filtered_voices = voice.get_chatterbox_voices()
        elif selected_tts_server == "elevenlabs":
            filtered_voices = voice.get_elevenlabs_voices()
        else:
            all_voices = voice.get_all_azure_voices(filter_locals=None)
            for v in all_voices:
                if selected_tts_server == "azure-tts-v2":
                    if "V2" in v:
                        filtered_voices.append(v)
                else:
                    if "V2" not in v:
                        filtered_voices.append(v)

        def make_friendly_name(v):
            if v.startswith("elevenlabs:"):
                parts = v.split(":", 2)
                if len(parts) >= 3:
                    return parts[2]
            return v.replace("Female", tr("Female")).replace("Male", tr("Male")).replace("Neural", "")

        friendly_names = {v: make_friendly_name(v) for v in filtered_voices}
        saved_voice_name = config.ui.get("voice_name", "")
        saved_voice_name_index = 0
        if saved_voice_name in friendly_names:
            saved_voice_name_index = list(friendly_names.keys()).index(saved_voice_name)
        else:
            for i, v in enumerate(filtered_voices):
                if v.lower().startswith(st.session_state["ui_language"].lower()):
                    saved_voice_name_index = i
                    break
        if saved_voice_name_index >= len(friendly_names) and friendly_names:
            saved_voice_name_index = 0

        voice_name = ""
        if friendly_names:
            selected_friendly_name = st.selectbox(
                tr("Speech Synthesis"),
                options=list(friendly_names.values()),
                index=min(saved_voice_name_index, len(friendly_names) - 1) if friendly_names else 0,
            )
            voice_name = list(friendly_names.keys())[list(friendly_names.values()).index(selected_friendly_name)]
            params.voice_name = voice_name
            config.ui["voice_name"] = voice_name
        else:
            st.warning(tr("No voices available for the selected TTS server. Please select another server."))
            params.voice_name = ""
            config.ui["voice_name"] = ""

        if friendly_names and st.button(tr("Play Voice")):
            play_content = params.video_subject or params.video_script or tr("Voice Example")
            with st.spinner(tr("Synthesizing Voice")):
                temp_dir = utils.storage_dir("temp", create=True)
                audio_file = os.path.join(temp_dir, f"tmp-voice-{str(uuid4())}.mp3")
                sub_maker = voice.tts(text=play_content, voice_name=voice_name,
                    voice_rate=params.voice_rate, voice_file=audio_file, voice_volume=params.voice_volume)
                if not sub_maker:
                    sub_maker = voice.tts(text="This is an example voice.", voice_name=voice_name,
                        voice_rate=params.voice_rate, voice_file=audio_file, voice_volume=params.voice_volume)
                if sub_maker and os.path.exists(audio_file):
                    st.audio(audio_file, format="audio/mp3")
                    os.remove(audio_file)

        # TTS-specific API keys in expander
        with st.expander("TTS API Keys", expanded=False):
            if selected_tts_server == "azure-tts-v2" or (voice_name and voice.is_azure_v2_voice(voice_name)):
                azure_speech_region = st.text_input(tr("Speech Region"), value=config.azure.get("speech_region", ""))
                azure_speech_key = st.text_input(tr("Speech Key"), value=config.azure.get("speech_key", ""), type="password")
                config.azure["speech_region"] = azure_speech_region
                config.azure["speech_key"] = azure_speech_key
            if selected_tts_server == "siliconflow" or (voice_name and voice.is_siliconflow_voice(voice_name)):
                siliconflow_api_key = st.text_input("SiliconFlow API Key", value=config.siliconflow.get("api_key", ""), type="password")
                config.siliconflow["api_key"] = siliconflow_api_key
            if selected_tts_server == "elevenlabs" or (voice_name and voice.is_elevenlabs_voice(voice_name)):
                elevenlabs_api_key = st.text_input("ElevenLabs API Key", value=config.elevenlabs.get("api_key", ""), type="password")
                config.elevenlabs["api_key"] = elevenlabs_api_key

        # Chatterbox voice cloning info
        if selected_tts_server == "chatterbox" and friendly_names:
            with st.expander("Voice Cloning", expanded=False):
                reference_audio_dir = os.path.join(root_dir, "reference_audio")
                if os.path.exists(reference_audio_dir):
                    audio_files = [f for f in os.listdir(reference_audio_dir) if f.lower().endswith(('.wav', '.mp3', '.flac', '.m4a'))]
                    st.write(f"{len(audio_files)} reference audio files found")
                else:
                    st.info("Create `reference_audio/` folder for voice cloning")

        params.voice_volume = st.selectbox(tr("Speech Volume"), options=[0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0, 4.0, 5.0], index=2)
        params.voice_rate = st.selectbox(tr("Speech Rate"), options=[0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.8, 2.0], index=2)

        bgm_options = [
            (tr("No Background Music"), ""),
            (tr("Random Background Music"), "random"),
            (tr("Custom Background Music"), "custom"),
        ]
        selected_index = st.selectbox(
            tr("Background Music"), index=1,
            options=range(len(bgm_options)),
            format_func=lambda x: bgm_options[x][0],
        )
        params.bgm_type = bgm_options[selected_index][1]
        if params.bgm_type == "custom":
            custom_bgm_file = st.text_input(tr("Custom Background Music File"), key="custom_bgm_file_input")
            if custom_bgm_file and os.path.exists(custom_bgm_file):
                params.bgm_file = custom_bgm_file
        params.bgm_volume = st.selectbox(tr("Background Music Volume"),
            options=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0], index=2)

    # --- SUBTITLES COLUMN ---
    with subs_col:
        st.markdown("**Subtitles**")
        params.subtitle_enabled = st.checkbox(tr("Enable Subtitles"), value=True)
        font_names = get_all_fonts()
        saved_font_name = config.ui.get("font_name", "MicrosoftYaHeiBold.ttc")
        saved_font_name_index = font_names.index(saved_font_name) if saved_font_name in font_names else 0
        params.font_name = st.selectbox(tr("Font"), font_names, index=saved_font_name_index)
        config.ui["font_name"] = params.font_name

        subtitle_positions = [
            (tr("Top"), "top"), (tr("Center"), "center"),
            (tr("Bottom"), "bottom"), (tr("Custom"), "custom"),
        ]
        selected_index = st.selectbox(tr("Position"), index=2,
            options=range(len(subtitle_positions)),
            format_func=lambda x: subtitle_positions[x][0])
        params.subtitle_position = subtitle_positions[selected_index][1]

        if params.subtitle_position == "custom":
            custom_position = st.text_input(tr("Custom Position (% from top)"), value="70.0", key="custom_position_input")
            try:
                params.custom_position = float(custom_position)
            except ValueError:
                st.error(tr("Please enter a valid number"))

        font_cols = st.columns([0.3, 0.7])
        with font_cols[0]:
            params.text_fore_color = st.color_picker(tr("Font Color"), config.ui.get("text_fore_color", "#FFFFFF"))
            config.ui["text_fore_color"] = params.text_fore_color
        with font_cols[1]:
            params.font_size = st.slider(tr("Font Size"), 30, 100, config.ui.get("font_size", 60))
            config.ui["font_size"] = params.font_size

        stroke_cols = st.columns([0.3, 0.7])
        with stroke_cols[0]:
            params.stroke_color = st.color_picker(tr("Stroke Color"), "#000000")
        with stroke_cols[1]:
            params.stroke_width = st.slider(tr("Stroke Width"), 0.0, 10.0, 1.5)

        with st.expander("Word Highlighting", expanded=False):
            params.enable_word_highlighting = st.checkbox(
                tr("Enable Word Highlighting (If unchecked, the settings below will not take effect)"),
                value=config.ui.get("enable_word_highlighting", False))
            config.ui["enable_word_highlighting"] = params.enable_word_highlighting
            if params.enable_word_highlighting:
                params.word_highlight_color = st.color_picker(tr("Highlight Color"), config.ui.get("highlight_color", "#ff0000"))
                config.ui["highlight_color"] = params.word_highlight_color
                params.max_chars_per_line = st.slider(tr("Max Characters Per Line"), 20, 80, config.ui.get("max_chars_per_line", 40))
                config.ui["max_chars_per_line"] = params.max_chars_per_line
                params.max_lines_per_subtitle = st.slider(tr("Max Lines Per Subtitle"), 1, 4, config.ui.get("max_lines_per_subtitle", 2))
                config.ui["max_lines_per_subtitle"] = params.max_lines_per_subtitle
            else:
                params.word_highlight_color = config.ui.get("highlight_color", "#ff0000")
                params.max_chars_per_line = config.ui.get("max_chars_per_line", 40)
                params.max_lines_per_subtitle = config.ui.get("max_lines_per_subtitle", 2)

# =====================================================================
# STEP 3: AI IMAGES (only when source = ai_generated)
# =====================================================================
if params.video_source == "ai_generated":
    with st.container(border=True):
        st.subheader("Step 3: AI Images")

        script_text = params.video_script or st.session_state.get("video_script", "")
        if script_text:
            current_paragraphs = [p.strip() for p in script_text.split("\n\n") if p.strip()]
            st.info(f"**{len(current_paragraphs)} paragraphs** = **{len(current_paragraphs)} images** (1 per paragraph). Each clip matches its paragraph audio duration.")
        else:
            st.info(f"**{paragraph_number} images** will be generated. Generate a script first.")

        if "ai_visual_style" not in st.session_state:
            st.session_state["ai_visual_style"] = config.app.get("ai_visual_style", "")

        ai_visual_style = st.text_area(
            "Visual Style & References",
            value=st.session_state["ai_visual_style"],
            height=80,
            placeholder="Describe visual aesthetic, color palette, mood. Auto-filled from Research.",
            help="The AI will use this to guide all image prompts consistently.",
        )
        st.session_state["ai_visual_style"] = ai_visual_style
        config.app["ai_visual_style"] = ai_visual_style

        if st.button("Generate Image Prompts", key="gen_ai_prompts", use_container_width=True):
            script = params.video_script or st.session_state.get("video_script", "")
            if not script:
                st.error("Please write or generate a video script first.")
            else:
                with st.spinner("Generating image prompts (1 per paragraph)..."):
                    script_paragraphs = [p.strip() for p in script.split("\n\n") if p.strip()]
                    if not script_paragraphs:
                        script_paragraphs = [script]
                    prompts = ai_images.generate_image_prompts(
                        script_paragraphs, params.video_language or "en",
                        visual_style=ai_visual_style,
                        research_context=st.session_state.get("topic_research", ""),
                    )
                    st.session_state["ai_image_prompts"] = prompts

        if st.session_state["ai_image_prompts"]:
            st.write(f"**{len(st.session_state['ai_image_prompts'])} prompts (1 per paragraph):**")
            updated_prompts = []
            for i, prompt in enumerate(st.session_state["ai_image_prompts"]):
                edited = st.text_area(
                    f"Scene {i + 1}", value=prompt, height=70, key=f"ai_prompt_{i}",
                )
                updated_prompts.append(edited)
            st.session_state["ai_image_prompts"] = updated_prompts

            sb_col1, sb_col2 = st.columns(2)
            with sb_col1:
                if st.button("🖼️ Preview Storyboard", key="gen_storyboard", use_container_width=True):
                    script = params.video_script or st.session_state.get("video_script", "")
                    if script:
                        with st.spinner("Generating storyboard images..."):
                            script_paragraphs = [p.strip() for p in script.split("\n\n") if p.strip()]
                            if not script_paragraphs:
                                script_paragraphs = [script]
                            storyboard = ai_images.generate_storyboard(
                                paragraphs=script_paragraphs,
                                api_key=config.app.get("gemini_api_key", ""),
                                aspect_ratio=str(params.video_aspect.value) if hasattr(params.video_aspect, 'value') else "9:16",
                                predefined_prompts=st.session_state["ai_image_prompts"],
                                visual_style=st.session_state.get("ai_visual_style", ""),
                                research_context=st.session_state.get("topic_research", ""),
                            )
                            st.session_state["storyboard"] = storyboard
            with sb_col2:
                if st.button("Clear All", key="clear_ai_prompts", use_container_width=True):
                    st.session_state["ai_image_prompts"] = []
                    st.session_state["storyboard"] = []
                    st.rerun()

        # Storyboard Preview
        if st.session_state.get("storyboard"):
            st.write("---")
            st.write("**Storyboard Preview**")
            cols_per_row = 4
            storyboard = st.session_state["storyboard"]
            for row_start in range(0, len(storyboard), cols_per_row):
                row_items = storyboard[row_start:row_start + cols_per_row]
                cols = st.columns(cols_per_row)
                for col_idx, item in enumerate(row_items):
                    with cols[col_idx]:
                        idx = item["index"]
                        if item["image_path"] and os.path.exists(item["image_path"]):
                            st.image(item["image_path"], use_container_width=True)
                        else:
                            st.warning("Failed")
                        st.caption(f"**Scene {idx + 1}**")
                        st.caption(item["paragraph"][:80] + "..." if len(item["paragraph"]) > 80 else item["paragraph"])
                        if st.button("🔄", key=f"regen_img_{idx}", help="Regenerate this image"):
                            with st.spinner(f"Regenerating..."):
                                new_path = ai_images.regenerate_single_image(
                                    prompt=item["prompt"],
                                    api_key=config.app.get("gemini_api_key", ""),
                                    aspect_ratio=str(params.video_aspect.value) if hasattr(params.video_aspect, 'value') else "9:16",
                                    old_image_path=item.get("image_path"),
                                )
                                if new_path:
                                    st.session_state["storyboard"][idx]["image_path"] = new_path
                                    st.rerun()

start_button = st.button(tr("Generate Video"), use_container_width=True, type="primary")
if start_button:
    config.save_config()
    task_id = str(uuid4())
    if not params.video_subject and not params.video_script:
        st.error(tr("Video Script and Subject Cannot Both Be Empty"))
        scroll_to_bottom()
        st.stop()

    if params.video_source not in ["pexels", "pixabay", "local", "ai_generated"]:
        st.error(tr("Please Select a Valid Video Source"))
        scroll_to_bottom()
        st.stop()

    if params.video_source == "ai_generated" and not config.app.get("gemini_api_key", ""):
        st.error("Please enter your Google AI API Key in Basic Settings to use AI Generated images")
        scroll_to_bottom()
        st.stop()

    if params.video_source == "pexels" and not config.app.get("pexels_api_keys", ""):
        st.error(tr("Please Enter the Pexels API Key"))
        scroll_to_bottom()
        st.stop()

    if params.video_source == "pixabay" and not config.app.get("pixabay_api_keys", ""):
        st.error(tr("Please Enter the Pixabay API Key"))
        scroll_to_bottom()
        st.stop()

    if uploaded_files:
        local_videos_dir = utils.storage_dir("local_videos", create=True)
        for file in uploaded_files:
            file_path = os.path.join(local_videos_dir, f"{file.file_id}_{file.name}")
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
                m = MaterialInfo()
                m.provider = "local"
                m.url = file_path
                if not params.video_materials:
                    params.video_materials = []
                params.video_materials.append(m)

    # Pass AI image settings if source is ai_generated
    if params.video_source == "ai_generated":
        ai_prompts = st.session_state.get("ai_image_prompts", [])
        if ai_prompts:
            params.ai_image_prompts = ai_prompts
        # ai_image_count = paragraph_number (1 image per paragraph)
        params.ai_image_count = config.app.get("paragraph_number", 8)
        params.paragraph_number = params.ai_image_count

    log_container = st.empty()
    log_records = []

    def log_received(msg):
        if config.ui["hide_log"]:
            return
        with log_container:
            log_records.append(msg)
            st.code("\n".join(log_records))

    logger.add(log_received)

    st.toast(tr("Generating Video"))
    logger.info(tr("Start Generating Video"))
    logger.info(utils.to_json(params))
    scroll_to_bottom()

    result = tm.start(task_id=task_id, params=params)
    if not result or "videos" not in result:
        st.error(tr("Video Generation Failed"))
        logger.error(tr("Video Generation Failed"))
        scroll_to_bottom()
        st.stop()

    video_files = result.get("videos", [])
    st.success(tr("Video Generation Completed"))
    try:
        if video_files:
            player_cols = st.columns(len(video_files) * 2 + 1)
            for i, url in enumerate(video_files):
                player_cols[i * 2 + 1].video(url)
    except Exception:
        pass

    # Show AI image generation details
    ai_details = result.get("ai_image_details", [])
    if ai_details:
        with st.expander(f"AI Generated Images ({len(ai_details)} clips)", expanded=False):
            for i, detail in enumerate(ai_details):
                st.markdown(f"**Clip {i + 1}**")
                st.text(detail.get("prompt", ""))
                img_path = detail.get("image_path", "")
                if img_path and os.path.exists(img_path):
                    st.image(img_path, width=300)
                st.divider()

    open_task_folder(task_id)
    logger.info(tr("Video Generation Completed"))
    scroll_to_bottom()

config.save_config()
