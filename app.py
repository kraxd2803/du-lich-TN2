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

def clean_rag_data(text):
    if not text: return ""
    # 1. Xóa các đường link http/https
    text = re.sub(r'http\S+', '', text)
    # 2. Xóa chữ "Link Google Maps:" thừa ra
    text = text.replace("Link Google Maps:", "")
    # 3. Xóa khoảng trắng thừa
    return text.strip()
    
# ======================================
# STREAMLIT UI
# ======================================
st.set_page_config(page_title="Chatbot Du Lịch Tây Ninh", page_icon="🗺️")
st.title("🗺️ Chatbot Du Lịch Tây Ninh – Gemini Streaming")
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

    # 2. Xử lý RAG và Prompt
    related_data = ""
    user_norm = normalize(user_input)
    
    # Tìm dữ liệu liên quan
    for place in tourism_data:
        place_norm = normalize(place)
        if place_norm in user_norm:
            raw_data = tourism_data[place]
            related_data = clean_rag_data(raw_data)
            if len(related_data) > 3000:
                related_data = related_data[:3000] + "..."
            break

    # Cấu hình Prompt
    lh = "Bạn là hướng dẫn viên du lịch Tây Ninh am hiểu. Trả lời tiếng Việt, trình bày đẹp, ngắn gọn."

    if related_data:
        prompt_user = f"""{lh}
        Dựa vào thông tin sau để trả lời (không bịa đặt):
        --- DỮ LIỆU ---
        {related_data}
        ---------------
        Câu hỏi: {user_input}
        """
    else:
        # Prompt "mở" hơn cho các câu chào hỏi xã giao
        prompt_user = f"""{lh}
        Câu hỏi: {user_input}
        (Nếu là chào hỏi, hãy chào lại thân thiện. Nếu hỏi về Tây Ninh mà không có dữ liệu, hãy dùng kiến thức chung).
        """

    # 3. Gọi Gemini API (Logic lấy text siêu bền vững)
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_text = ""
        gemini_config = {"max_output_tokens": 512} 

        try:
            # --- GỌI STREAMING ---
            stream = client.models.generate_content_stream(
                model="gemini-2.5-flash", 
                contents=prompt_user,
                config=gemini_config
            )

            for chunk in stream:
                chunk_text = ""
                # Logic lấy text đa tầng (Deep Extraction)
                try:
                    # Ưu tiên 1: Lấy trực tiếp .text
                    if hasattr(chunk, "text") and chunk.text:
                        chunk_text = chunk.text
                    # Ưu tiên 2: Lấy từ candidates > parts (phòng khi .text bị None)
                    elif hasattr(chunk, "candidates") and chunk.candidates:
                        parts = chunk.candidates[0].content.parts
                        chunk_text = "".join([p.text for p in parts if p.text])
                except Exception:
                    pass
                
                if chunk_text:
                    full_text += chunk_text
                    placeholder.markdown(full_text)

            # Kiểm tra cuối cùng
            if not full_text.strip():
                raise RuntimeError("Empty Stream")

        except Exception as e_stream:
            # --- FALLBACK: GỌI SYNC (Dự phòng) ---
            try:
                resp = client.models.generate_content(
                    model="gemini-2.5-flash", 
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
                        # Kiểm tra candidate và content có tồn tại không
                        if hasattr(candidate, "content") and candidate.content:
                            parts = getattr(candidate.content, "parts", None) # Lấy parts an toàn
                            
                            # Chỉ lặp nếu parts tồn tại và là list
                            if parts and isinstance(parts, list):
                                full_text = "".join([p.text for p in parts if hasattr(p, 'text') and p.text])
                            else:
                                # Nếu không có parts (thường do bị chặn)
                                full_text = "🚫 Phản hồi bị chặn nội dung cấp thấp."
                        except Exception as e_candidate:
                        # Lỗi khác khi truy cập candidates
                            full_text = f"🚫 Lỗi truy cập phản hồi: {e_candidate}"
    
                if not full_text or full_text.startswith("🚫"):
                            # Nếu vẫn rỗng, kiểm tra lại lỗi chặn cấp cao
                    if hasattr(resp, "prompt_feedback") and resp.prompt_feedback.block_reason:
                        reason = resp.prompt_feedback.block_reason.name
                        full_text = f"🚫 BỊ CHẶN: Phản hồi vi phạm chính sách an toàn ({reason})."
                    elif full_text == "":
                         full_text = "⚠️ Gemini không phản hồi (Phản hồi rỗng hoàn toàn)."

                 placeholder.markdown(full_text)

            except Exception as e_sync:
                st.error("❌ Lỗi kết nối:")
                st.code(f"Stream Error: {e_stream}\nSync Error: {e_sync}")
                st.stop()
        
        # 4. Lưu lịch sử
        st.session_state.messages.append({"role": "assistant", "content": full_text})
        st.session_state.last_bot = full_text

    # 5. Hiển thị ảnh (nếu có keyword địa điểm trong câu hỏi)
    # Logic: Chỉ hiện ảnh nếu tìm thấy key trong tourism_data trùng với câu hỏi
    found_img = False
    for place in tourism_data.keys():
        if normalize(place) in normalize(user_input):
            if place in images and isinstance(images[place], list):
                if not found_img: 
                    st.divider()
                    st.caption(f"📸 Hình ảnh gợi ý: {place}")
                    found_img = True
                cols = st.columns(min(len(images[place]), 3))
                for idx, col in enumerate(cols):
                    col.image(images[place][idx], use_container_width=True)
            break # Chỉ hiện ảnh của 1 địa điểm chính nhất

    # 6. Hiển thị thời tiết
    st.divider()
    cols_weather = st.columns(2)
    lat, lon = 10.5359, 106.4137
    weather = get_weather_simple(lat, lon)
    
    if weather:
        current = weather.get("current_weather", {})
        temp = current.get("temperature", "--")
        with cols_weather[0]:
            st.info(f"🌤️ Nhiệt độ Tây Ninh: **{temp}°C**")








