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
# SỬ DỤNG MÔ HÌNH PRO CHO KIẾN THỨC CHUNG SAU KHI BỎ RAG
MODEL_NAME = "gemini-2.5-pro" 
client = genai.Client(
    api_key=st.secrets["gemini_key"],
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

# Load dữ liệu du lịch (Vẫn tải dữ liệu để tìm kiếm tên địa điểm cho chức năng ảnh)
tourism_data = {}
try:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        raw_text = f.read()
    current_key = None
    for line in raw_text.splitlines():
        line = line.strip()
        if line.startswith("###"):
            # LÀM SẠCH KEY ĐỂ DÙNG TÌM KIẾM ẢNH
            place = line.replace("###", "").strip() 
            tourism_data[place] = ""
            current_key = place
        elif current_key:
            tourism_data[current_key] += line + "\n"

except Exception:
    raw_text = ""
    st.error("❌ Không tìm thấy file data_tayninh.txt")

# ======================================
# UTIL FUNCTIONS
# ======================================
def normalize(text):
    if not text:
        return ""
    # Chuyển chữ có dấu thành không dấu và làm sạch
    t = unidecode(text.lower())
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()

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
st.title("🗺️ Chatbot Du Lịch Tây Ninh – Ổn định tối đa (Sync)")
st.caption("Made by Đăng Khoa 🔰 - 1.1")

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
    # 1. Hiển thị tin nhắn User
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 2. Xử lý Prompt (KHÔNG CÓ RAG)
    found_place = None # Reset cờ tìm kiếm ảnh

    # TÌM KIẾM TÊN ĐỊA ĐIỂM CHỈ ĐỂ HIỂN THỊ ẢNH
    user_norm = normalize(user_input)
    for place in tourism_data:
        place_norm = normalize(place)
        if place_norm in user_norm:
            found_place = place # LƯU TÊN ĐỊA ĐIỂM ĐỂ DÙNG HIỂN THỊ ẢNH
            break
    
    # Cấu hình Prompt (Vai trò và Bối cảnh sáp nhập)
    lh = "Bạn là hướng dẫn viên du lịch Tây Ninh am hiểu, thân thiện, trả lời bằng tiếng Việt. (Lưu ý: Tây Ninh hiện nay bao gồm cả khu vực Long An cũ, thủ phủ tại Tân An, hiệu lực từ 01/07/2025)."

    # Prompt Mở (Chỉ sử dụng kiến thức chung của Gemini)
    prompt_user = f"""{lh}
    Hãy trả lời câu hỏi của khách hàng một cách thân thiện, dựa trên kiến thức chung của bạn về Tây Ninh và Long An cũ (trước khi sáp nhập 2 tỉnh).

    Câu hỏi: {user_input}
    """
    
    # 3. Gọi Gemini API (Logic chỉ dùng Sync - Ổn định tối đa)
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_text = ""
        gemini_config = {"max_output_tokens": 1024} 

        try:
            # --- GỌI SYNC (Đồng bộ) ---
            # Sử dụng mô hình PRO để có thông tin chi tiết tốt nhất
            resp = client.models.generate_content(
                model=MODEL_NAME, 
                contents=prompt_user,
                config=gemini_config
            )
            
            # Logic lấy text cho Sync (Deep Extraction)
            full_text = ""
            
            if hasattr(resp, "text") and resp.text:
                full_text = resp.text
            
            elif hasattr(resp, "candidates") and resp.candidates:
                try:
                    candidate = resp.candidates[0]
                    if hasattr(candidate, "content") and candidate.content:
                        parts = getattr(candidate.content, "parts", None) 
                        if parts and isinstance(parts, list):
                            full_text = "".join([p.text for p in parts if hasattr(p, 'text') and p.text])
                except Exception as e_candidate:
                    full_text = f"🚫 Lỗi truy cập phản hồi: {e_candidate}"
            
            # Kiểm tra lỗi chặn sau khi đã cố gắng lấy text
            if not full_text or full_text.startswith("🚫"):
                if hasattr(resp, "prompt_feedback") and resp.prompt_feedback is not None:
                    feedback = resp.prompt_feedback
                    if hasattr(feedback, "block_reason") and feedback.block_reason is not None:
                        reason = feedback.block_reason.name
                        full_text = f"🚫 BỊ CHẶN: Phản hồi vi phạm chính sách an toàn ({reason})."
                    elif full_text == "":
                        full_text = "⚠️ Gemini không phản hồi (Phản hồi rỗng hoàn toàn)."
                elif full_text == "":
                    full_text = "⚠️ Gemini không phản hồi (Phản hồi rỗng hoàn toàn)."

            placeholder.markdown(full_text)

        except Exception as e:
            # Báo lỗi kết nối nếu Sync thất bại
            st.error("❌ Lỗi kết nối API:")
            st.code(f"Sync Error: {e}")
            st.stop()
    
    # 4. Lưu lịch sử
    st.session_state.messages.append({"role": "assistant", "content": full_text})
    st.session_state.last_bot = full_text

    # 5. Hiển thị ảnh (nếu có keyword địa điểm trong câu hỏi)
    if found_place and found_place in images and isinstance(images[found_place], list):
        st.divider()
        st.caption(f"📸 Hình ảnh gợi ý: {found_place}")
        cols = st.columns(min(len(images[found_place]), 3))
        for idx, col in enumerate(cols):
            col.image(images[found_place][idx], use_container_width=True)

    # 6. Hiển thị thời tiết (Sử dụng tọa độ Tân An)
    st.divider()
    cols_weather = st.columns(2)
    # Tọa độ Tân An (thủ phủ mới)
    lat, lon = 10.7788, 106.3533 
    weather = get_weather_simple(lat, lon)

    if weather:
        current = weather.get("current_weather", {})
        temp = current.get("temperature", "--")
        with cols_weather[0]:
            st.info(f"🌤️ Nhiệt độ Tân An (Tây Ninh mới): **{temp}°C**")
