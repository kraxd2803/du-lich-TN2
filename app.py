import streamlit as st
import google.generativeai as genai
import re
from unidecode import unidecode

# ======================================
# 🔑 CONFIG GEMINI
# ======================================
genai.configure(api_key=st.secrets["gemini_key"])

model = genai.GenerativeModel(
    "gemini-1.5-flash",  # nhanh + rẻ + ổn định
)

# ======================================
# 📌 HÀM XỬ LÝ
# ======================================

# Chuẩn hóa chuỗi
def normalize(text):
    if not text:
        return ""
    text = unidecode(text.lower())
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return text.strip()

# Phân tích ý định: câu mới hay tiếp tục?
def is_new_question(user_msg, last_bot_msg):
    if not last_bot_msg:
        return True
    nm = normalize(user_msg)
    if len(nm.split()) <= 3:
        return False
    if any(x in nm for x in ["tai sao", "o dau", "gio mo cua", "la gi", "du lich"]):
        return True
    return False

# ======================================
# 💬 STREAMLIT UI
# ======================================

st.set_page_config(page_title="Chatbot Tây Ninh", page_icon="🗺️")
st.title("🗺️ Chatbot Du Lịch Tây Ninh 2025")
st.caption("Hỗ trợ 24/7 – Dữ liệu du lịch tỉnh Tây Ninh 🇻🇳")

# Lưu lịch sử chat
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_bot" not in st.session_state:
    st.session_state.last_bot = ""

# Hiển thị lịch sử
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Nhập tin nhắn
user_msg = st.chat_input("Nhập câu hỏi du lịch...")

if user_msg:
    # Hiển thị tin nhắn user
    with st.chat_message("user"):
        st.write(user_msg)

    # Phân tích ý định
    new_question = is_new_question(user_msg, st.session_state.last_bot)

    # Prompt chính gửi vào AI
    if new_question:
        prompt = f"""
Bạn là chatbot du lịch tỉnh Tây Ninh.
Trả lời ngắn gọn – chính xác – dễ hiểu – tiếng Việt.

Câu hỏi:
{user_msg}
"""
    else:
        prompt = f"""
Tiếp tục cuộc trò chuyện trước đó.
Trả lời dựa trên nội dung user vừa nói.

Tin nhắn user:
{user_msg}
"""

    # Gọi Gemini với streaming
    with st.chat_message("assistant"):
        stream = model.generate_content(prompt, stream=True)
        response = st.write_stream(stream)

    # Lưu lại
    st.session_state.messages.append({"role": "user", "content": user_msg})
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.last_bot = response
