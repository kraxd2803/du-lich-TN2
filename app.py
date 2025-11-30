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

    # 2. Bỏ qua RAG (TẠM THỜI) và tạo Prompt ĐƠN GIẢN
    # LH: Loại bỏ System Instruction nghiêm ngặt để kiểm tra
    lh = "Bạn là chatbot du lịch tỉnh Tây Ninh. Trả lời ngắn gọn, chính xác, tiếng Việt."
    prompt_user = f"{lh}\n\nCâu hỏi:\n{user_input}\n"
    
    # 4. Gọi Gemini API (Sửa lỗi Indentation và Logic)
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_text = ""
        
        # Cấu hình Token Output (256 tokens)
        gemini_config = {"max_output_tokens": 256} 

        # --- BẮT ĐẦU GỌI API ---
        try:
            # A. Thử Streaming
            stream = client.models.generate_content_stream(
                model="gemini-2.5-flash", 
                contents=prompt_user,
                config=gemini_config
            )

            for chunk in stream:
                chunk_text = ""
                try:
                    if hasattr(chunk, "text") and chunk.text:
                        chunk_text = chunk.text
                except Exception:
                    pass
                
                if chunk_text:
                    full_text += chunk_text
                    placeholder.markdown(full_text)

            if not full_text.strip():
                raise RuntimeError("Phản hồi rỗng (Có thể bị lọc nội dung).") 

        except Exception as e_stream:
            # B. Nếu Stream lỗi -> Fallback sang gọi Sync
            try:
                resp = client.models.generate_content(
                    model="gemini-2.5-flash", 
                    contents=prompt_user,
                    config=gemini_config
                )
                
                # --- LOGIC XỬ LÝ PHẢN HỒI RẮN CHẮC HƠN (ĐÃ SỬA LỖI THỤT LỀ) ---
                full_text = ""
                
                # 1. KIỂM TRA LỖI LỌC AN TOÀN TRƯỚC
                if (hasattr(resp, "prompt_feedback") and resp.prompt_feedback is not None and 
                    hasattr(resp.prompt_feedback, "block_reason") and resp.prompt_feedback.block_reason):
                    
                    reason_name = resp.prompt_feedback.block_reason.name if hasattr(resp.prompt_feedback.block_reason, 'name') else 'Lý do không xác định'
                    full_text = f"🚫 Nội dung bị chặn do vi phạm chính sách an toàn: **{reason_name}**"
                
                # 2. KIỂM TRA XEM CÓ TEXT TRẢ VỀ KHÔNG
                elif hasattr(resp, "text") and resp.text:
                    full_text = resp.text
                
                # 3. Nếu vẫn không có nội dung
                if not full_text:
                     full_text = "⚠️ Phản hồi rỗng hoặc không có nội dung liên quan."

                placeholder.markdown(full_text)

            except Exception as e_sync:
                # C. Cả 2 đều lỗi -> In lỗi chi tiết
                st.error("❌ Đã xảy ra lỗi kết nối Gemini:")
                st.write("Lỗi Stream:", e_stream)
                st.write("Lỗi Sync:", e_sync)
                st.stop()
        
        # --- KẾT THÚC GỌI API ---

        # 5. Lưu lịch sử
        st.session_state.messages.append({"role": "assistant", "content": full_text})
        st.session_state.last_bot = full_text
        
        # 6. Hiển thị ảnh liên quan (Đã loại bỏ logic RAG phức tạp, chỉ giữ lại hiển thị)
        # BẠN CẦN THÊM LẠI LOGIC TÌM KIẾM PLACE TẠI ĐÂY NẾU MUỐN HIỂN THỊ ẢNH
        
    # 7. Hiển thị thời tiết (Đã sửa lỗi thụt lề)
    st.divider()
    cols_weather = st.columns(2)
    lat, lon = 10.5359, 106.4137 # Tọa độ Tây Ninh
    weather = get_weather_simple(lat, lon)
    
    if weather:
        current = weather.get("current_weather", {})
        temp = current.get("temperature", "--")
        
        with cols_weather[0]:
            st.info(f"🌤️ Nhiệt độ Tây Ninh: **{temp}°C**")
    if weather:
        current = weather.get("current_weather", {})
        temp = current.get("temperature", "--")
        
        with cols_weather[0]:
            st.info(f"🌤️ Nhiệt độ Tây Ninh: **{temp}°C**")



















