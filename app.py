import streamlit as st
import requests
import json

# ======================================
# 📚 TẢI DỮ LIỆU TXT
# ======================================

DATA_FILE = "data_tayninh.txt"


IMAGES_FILE = "images.json"

try:
    with open(IMAGES_FILE, "r", encoding="utf-8") as f:
        images = json.load(f)
except:
    images = {}
    st.warning("⚠️ Không tìm thấy images.json")


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

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Nhập câu hỏi...")

if user_input:

    # Hiển thị tin nhắn người dùng
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # ======================================
    # 🧠 PROMPT
    # ======================================
    st.write("💡 Đang suy nghĩ...")
    prompt = f"""
Bạn là hướng dẫn viên du lịch Tây Ninh mới bao gồm cả tỉnh Long An cũ sau sáp nhập .

Người dùng hỏi: "{user_input}"

Dữ liệu du lịch:
---
{json.dumps(tourism_data, ensure_ascii=False, indent=2)}
---

❗ Trả lời phần lớn dựa trên dữ liệu, có thể kết hợp với thông tin của bạn nhưng phải đảm bảo đó là thông tin chính xác tuyệt đối , không tự bịa thêm.
Hãy trả lời tự nhiên, thân thiện, chính xác , chỉ sử dụng tiếng việt.
    """

    # ======================================
    # 🤖 GỌI OPENROUTER + DEEPSEEK
    # ======================================

    OPENROUTER_API_KEY = "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"

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://du-lich-tn2-yhnjgcbmxdl9pvtjjmksi4.streamlit.app",       
        "X-Title": "Chatbot Tay Ninh",
        "User-Agent": "OpenRouter-Chatbot/1.0"

    }

    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [
            {"role": "system", "content": "Bạn là hướng dẫn viên du lịch Tây Ninh."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4,
        "stream": True     # 🔥 BẮT BUỘC để nhận text từng phần
    }

    placeholder = st.chat_message("assistant").empty()
    partial_text = ""

    try:
        with requests.post(url, headers=headers, json=payload, stream=True, timeout=30) as r:
            for line in r.iter_lines():
                if not line:
                    continue

                decoded = line.decode("utf-8")

                if decoded.startswith("data: "):
                    data_str = decoded.replace("data: ", "")

                    if data_str == "[DONE]":
                        break

                    try:
                        data_json = json.loads(data_str)
                        delta = data_json["choices"][0]["delta"]

                        if "content" in delta:
                            partial_text += delta["content"]
                            placeholder.markdown(partial_text)

                    except:
                        pass

    except Exception as e:
        partial_text = f"⚠️ Lỗi khi stream: {e}"
        placeholder.markdown(partial_text)

    # Nếu không nhận được gì thì cảnh báo
    if partial_text.strip() == "":
        partial_text = "⚠️ Không nhận được phản hồi từ mô hình!"

    # Lưu tin nhắn của bot
    st.session_state.messages.append({
        "role": "assistant",
        "content": partial_text
    })

    for place in tourism_data.keys():
        if place.lower() in user_input.lower():
            if place in images:
                st.subheader(f"📸 Hình ảnh về {place}")
                for url in images[place]:
                    st.image(url, use_container_width=True)

    def get_weather_simple(lat, lon):
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current_weather=true"
            "&hourly=precipitation_probability"
            "&timezone=auto"
        )
        try:
            res = requests.get(url)
            return res.json()
        except:
            return None

    st.subheader("🌤️ Thời tiết hiện tại tại Tây Ninh")

# Toạ độ Tây Ninh
    lat, lon = 10.5359,106.4137

    weather = get_weather_simple(lat, lon)

    if weather:
        current = weather.get("current_weather", {})
        temp = current.get("temperature", "?")
        time = current.get("time", "?")

    # Khả năng mưa (lấy giờ đầu tiên)
        rain_prob = weather.get("hourly", {}).get("precipitation_probability", ["?"])[0]

        col1, col2 = st.columns(2)

        with col1:
            st.metric("🌡️ Nhiệt độ", f"{temp}°C")

        with col2:
            st.metric("🌧️ Khả năng mưa", f"{rain_prob}%")

        st.caption(f"⏱️ Cập nhật lúc: {time}")

    else:
        st.error("⚠️ Không thể tải dữ liệu thời tiết!")
        



















