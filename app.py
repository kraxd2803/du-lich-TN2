import streamlit as st
import requests
import json
from datetime import datetime

# ======================================
# 📚 TẢI DỮ LIỆU TXT & JSON
# ======================================

DATA_FILE = "data_tayninh.txt"
IMAGES_FILE = "images.json"

# Load dữ liệu ảnh
try:
    with open(IMAGES_FILE, "r", encoding="utf-8") as f:
        images = json.load(f)
except:
    images = {}
    st.warning("⚠️ Không tìm thấy images.json")

# Load dữ liệu du lịch
try:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        raw_text = f.read()
except:
    raw_text = ""
    st.error("❌ Không tìm thấy file data_tayninh.txt")

# Chia dữ liệu theo địa điểm
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
# 🌐 STREAMLIT UI
# ======================================

st.set_page_config(page_title="Chatbot Du Lịch Tây Ninh", page_icon="🗺️")
st.title("🗺️ Chatbot Du Lịch Tây Ninh – BETA Version")
st.caption("Made by Đăng Khoa 🔰 - 1.0")
st.image("huongdan.png", caption="Hướng dẫn sử dụng Chatbot", use_container_width=True)

if "messages" not in st.session_state:
    st.session_state.messages = []

# Hiển thị lịch sử chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Nhập câu hỏi...")

if user_input:

    # ⬆️ Lưu tin nhắn user
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # ======================================
    # 🔍 LỌC DỮ LIỆU LIÊN QUAN
    # ======================================
    related_data = ""

    for place in tourism_data:
        if place.lower() in user_input.lower():
            related_data = tourism_data[place]
            break

    if related_data == "":
        related_data = "Không tìm thấy dữ liệu trực tiếp trong kho dữ liệu."

    # ======================================
    # 🧠 TẠO PROMPT
    # ======================================
    st.write("💡 Đang suy nghĩ...")

    MAX_PROMPT_LENGTH = 3000

    full_prompt = f"""
Bạn là hướng dẫn viên du lịch Tây Ninh mới bao gồm cả tỉnh Long An cũ sau sáp nhập.

Người dùng hỏi: "{user_input}"

Dữ liệu du lịch:
---
{related_data}
---

❗ Trả lời dựa trên dữ liệu là chính, có thể kết hợp kiến thức ngoài nhưng tuyệt đối không bịa.
Chỉ trả lời bằng tiếng Việt, giọng thân thiện, chính xác.
"""

    prompt = full_prompt[:MAX_PROMPT_LENGTH]

    # ======================================
    # 🤖 GỌI OPENROUTER
    # ======================================

    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://du-lich-tn2-yhnjgcbmxdl9pvtjjmksi4.streamlit.app/",
        "X-Title": "Chatbot Tay Ninh",
    }

    payload = {
        "model": "openai/gpt-4.1-mini",
        "messages": [
            {"role": "system", "content": "Bạn là hướng dẫn viên du lịch Tây Ninh."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "stream": False
    }

    placeholder = st.chat_message("assistant").empty()
    partial_text = ""

    # ======================================
    # 🛰️ GỌI API KHÔNG STREAM (ổn định nhất)
    # ======================================
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response_json = response.json()
        partial_text = response_json["choices"][0]["message"]["content"]
        placeholder.markdown(partial_text)

    except Exception as e:
        partial_text = ""

    # ======================================
    # 🔁 FALLBACK nếu phản hồi rỗng
    # ======================================
    if partial_text.strip() == "":
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=60)
            reply = r.json()["choices"][0]["message"]["content"]
            partial_text = reply
            placeholder.markdown(reply)

        except:
            partial_text = "⚠️ Không nhận được phản hồi từ mô hình!"
            placeholder.markdown(partial_text)
            st.session_state.messages.pop()  # Xoá tin nhắn lỗi
            st.stop()

    # Lưu lại phản hồi assistant
    st.session_state.messages.append({
        "role": "assistant",
        "content": partial_text
    })

    # ======================================
    # 📸 HIỂN THỊ HÌNH ẢNH LIÊN QUAN
    # ======================================
    for place in tourism_data.keys():
        if place.lower() in user_input.lower() and place in images and isinstance(images[place], list):
            st.subheader(f"📸 Hình ảnh về {place}")
            for url in images[place]:
                st.image(url, use_container_width=True)

    # ======================================
    # 🌤️ THỜI TIẾT TÂY NINH
    # ======================================
    @st.cache_data(ttl=300)
    def get_weather_simple(lat, lon):
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current_weather=true&hourly=precipitation_probability&timezone=auto"
        )
        try:
            res = requests.get(url)
            return res.json()
        except:
            return None

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
