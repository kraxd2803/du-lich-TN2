import streamlit as st
import google.genai as genai
import requests
import json
import re
from unidecode import unidecode
from datetime import datetime

# ======================================
# CONFIG GEMINI (SDK mới)
# ======================================
# Make sure you set st.secrets["gemini_key"] in Streamlit Cloud
client = genai.Client(
    api_key=st.secrets["gemini_key"],
    http_options={"api_version": "v1alpha"}  # v1alpha hoặc v1 tùy account
)

# ======================================
# DATA FILES
# ======================================
DATA_FILE = "data_tayninh.txt"
IMAGES_FILE = "images.json"

# Load dữ liệu ảnh
try:
    with open(IMAGES_FILE, "r", encoding="utf-8") as f:
        images = json.load(f)
except Exception:
    images = {}
    st.warning("⚠️ Không tìm thấy images.json hoặc JSON không hợp lệ")

# Load dữ liệu du lịch
try:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        raw_text = f.read()
except Exception:
    raw_text = ""
    st.error("❌ Không tìm thấy file data_tayninh.txt")

# Chia dữ liệu theo địa điểm (### Tên địa điểm)
tourism_data = {}
current_key = None
for line in raw_text.splitlines():
    line = line.strip()
    if line.startswith("###"):
        place = line.replace("###", "").strip()
        tourism_data[place] = ""
        current_key = place
    elif current_key:
        tourism_data[current_key] += line + "\n"

# ======================================
# UTIL FUNCTIONS
# ======================================
def normalize(text):
    if not text:
        return ""
    t = unidecode(text.lower())
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def is_new_question(user_msg, last_bot_msg):
    if not last_bot_msg:
        return True
    nm = normalize(user_msg)
    if len(nm.split()) <= 3:
        return False
    if any(x in nm for x in ["tai sao", "o dau", "gio mo cua", "la gi", "du lich", "bao nhieu"]):
        return True
    return False

@st.cache_data(ttl=300)
def get_weather_simple(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&current_weather=true&hourly=precipitation_probability&timezone=auto"
    )
    try:
        res = requests.get(url, timeout=10)
        return res.json()
    except Exception:
        return None

# ======================================
# STREAMLIT UI
# ======================================
st.set_page_config(page_title="Chatbot Du Lịch Tây Ninh", page_icon="🗺️")
st.title("🗺️ Chatbot Du Lịch Tây Ninh – Gemini Streaming")
st.caption("Made by Đăng Khoa 🔰 - 1.0")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_bot" not in st.session_state:
    st.session_state.last_bot = ""

# Show conversation
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Nhập câu hỏi...")

if user_input:
    # show user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # find related data (only send related chunk)
    related_data = ""
    for place in tourism_data:
        if place.lower() in user_input.lower():
            related_data = tourism_data[place]
            break
    if related_data == "":
        related_data = "Không tìm thấy dữ liệu trực tiếp trong kho dữ liệu."

    # build prompt
    new_question = is_new_question(user_input, st.session_state.last_bot)
    if new_question:
        lh = "Bạn là chatbot du lịch tỉnh Tây Ninh. Trả lời ngắn gọn, chính xác, tiếng Việt."
        prompt_user = f"{lh}\n\nCâu hỏi:\n{user_input}\n\nDữ liệu tham khảo:\n{related_data}\n"
    else:
        prompt_user = f"Tiếp tục cuộc trò chuyện. Tin nhắn user: {user_input}\n\nDữ liệu tham khảo:\n{related_data}\n"

    # place holder for assistant
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_text = ""

        # Try streaming first (Gemini generate_content with stream=True)
        try:
            stream = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt_user,
                stream=True,
                # You can pass additional generation parameters here if needed
                # e.g. max_output_tokens=512, temperature=0.3
            )

            # stream is an iterator of chunks
            for chunk in stream:
                # chunk may expose .text or .content or .delta depending on SDK
                chunk_text = ""
                try:
                    # most recent SDKs provide .text
                    if hasattr(chunk, "text") and chunk.text:
                        chunk_text = chunk.text
                    # otherwise try content/parts
                    elif hasattr(chunk, "content") and isinstance(chunk.content, dict):
                        # new formats may put parts under content
                        parts = chunk.content.get("parts") if isinstance(chunk.content.get("parts"), list) else None
                        if parts:
                            chunk_text = "".join([p.get("text", "") for p in parts])
                    # some SDK versions: chunk.delta ? try to extract
                    elif hasattr(chunk, "delta"):
                        d = getattr(chunk, "delta")
                        if isinstance(d, dict):
                            chunk_text = d.get("content", "") or d.get("text", "")
                except Exception:
                    chunk_text = ""

                if chunk_text:
                    full_text += chunk_text
                    # update placeholder progressively
                    # use markdown so newlines render properly
                    placeholder.markdown(full_text)

            # streaming finished
            if full_text.strip() == "":
                # empty stream — fallback to sync call below
                raise RuntimeError("Empty stream")

        except Exception as e_stream:
            # fallback: try non-stream generate_content (sync)
            try:
                resp = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt_user,
                    stream=False,
                )
                # resp may have .text or .candidates etc.
                sync_text = ""
                try:
                    if hasattr(resp, "text") and resp.text:
                        sync_text = resp.text
                    elif hasattr(resp, "candidates") and isinstance(resp.candidates, list):
                        cand = resp.candidates[0]
                        # older/newer formats
                        if hasattr(cand, "content") and isinstance(cand.content, dict):
                            parts = cand.content.get("parts", [])
                            sync_text = "".join([p.get("text", "") for p in parts])
                        elif hasattr(cand, "text"):
                            sync_text = cand.text
                except Exception:
                    sync_text = ""

                if sync_text.strip() == "":
                    raise RuntimeError("Empty sync response")
                full_text = sync_text
                placeholder.markdown(full_text)
            except Exception as e_sync:
                # both stream and sync failed
                err_msg = "⚠️ Không nhận được phản hồi từ Gemini API. Vui lòng kiểm tra API key / quota."
                placeholder.markdown(err_msg)
                # remove last user message to avoid blocking next queries
                try:
                    st.session_state.messages.pop()
                except Exception:
                    pass
                # stop further execution for this run
                st.session_state.last_bot = ""
                st.stop()

        # save to history
        st.session_state.messages.append({"role": "assistant", "content": full_text})
        st.session_state.last_bot = full_text

    # show related images if any
    for place in tourism_data.keys():
        if place.lower() in user_input.lower() and place in images and isinstance(images[place], list):
            st.subheader(f"📸 Hình ảnh về {place}")
            for url in images[place]:
                st.image(url, use_container_width=True)

    # show weather
    st.subheader("🌤️ Thời tiết hiện tại tại Tây Ninh")
    lat, lon = 10.5359, 106.4137
    weather = get_weather_simple(lat, lon)
    if weather:
        current = weather.get("current_weather", {})
        temp = current.get("temperature", "?")
        time = current.get("time", "?")
        current_hour = datetime.now().hour
        rain_prob_list = weather.get("hourly", {}).get("precipitation_probability", [0]*24)
        rain_prob = rain_prob_list[current_hour] if current_hour < len(rain_prob_list) else "?"
        col1, col2 = st.columns(2)
        with col1:
            st.metric("🌡️ Nhiệt độ", f"{temp}°C")
        with col2:
            st.metric("🌧️ Khả năng mưa", f"{rain_prob}%")
        st.caption(f"⏱️ Cập nhật lúc: {time}")
    else:
        st.error("⚠️ Không thể tải dữ liệu thời tiết!")

    st.session_state.messages.append({"role": "user", "content": user_msg})
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.last_bot = response




