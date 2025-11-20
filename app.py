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
Bạn là hướng dẫn viên du lịch Tây Ninh.

Người dùng hỏi: "{user_input}"

Dữ liệu du lịch:
---
{json.dumps(tourism_data, ensure_ascii=False, indent=2)}
---

❗ Chỉ trả lời dựa trên dữ liệu, không tự bịa thêm.
Hãy trả lời tự nhiên, thân thiện, chính xác.
    """

    # ======================================
    # 🤖 GỌI OPENROUTER + DEEPSEEK
    # ======================================

    OPENROUTER_API_KEY = "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"

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://dulichtn.streamlit.app/",       
        "X-Title": "Chatbot Tay Ninh"
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

    # Tạo khung chat cho bot
    placeholder = st.chat_message("assistant").empty()
    partial_text = ""

    try:
        with requests.post(url, headers=headers, json=payload, stream=True) as r:
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

    if partial_text.strip() == "":
    partial_text = "⚠️ Không nhận được phản hồi từ mô hình!"

        
    # LƯU tin nhắn của bot
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






