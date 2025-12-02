import streamlit as st
import google.genai as genai
import requests
import json
import re
from unidecode import unidecode
from datetime import datetime

# ======================================
# CONFIG GEMINI
# ======================================
MODEL_NAME = "gemini-2.5-pro"
client = genai.Client(
    api_key=st.secrets["gemini_key"],
)

# ======================================
# LOAD DATA (TỐI ƯU: CHỈ DÙNG images.json)
# ======================================
IMAGES_FILE = "images.json"
GUIDE_IMAGE_FILE = "huongdan.png"

# Load ảnh và tạo danh sách địa điểm từ key của ảnh
images = {}
tourism_data = {}
try:
    with open(IMAGES_FILE, "r", encoding="utf-8") as f:
        images = json.load(f)
        
    # TẠO DANH SÁCH ĐỊA ĐIỂM TỪ KEY CỦA FILE ẢNH
    # (Dùng để tìm kiếm tên địa điểm trong câu hỏi của User)
    tourism_data = {place: "" for place in images.keys()} 

except Exception as e:
    images = {}
    tourism_data = {}
    st.error(f"❌ Lỗi tải file images.json: {e}") 
    st.warning("⚠️ Không tìm thấy images.json hoặc JSON không hợp lệ. Tính năng tìm kiếm ảnh bị vô hiệu hóa.")


# ======================================
# UTILITIES
# ======================================
def normalize(text):
    if not text:
        return ""
    t = unidecode(text.lower())
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@st.cache_data(ttl=300)
def get_weather(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&current_weather=true&hourly=precipitation_probability&timezone=auto"
    )
    try:
        res = requests.get(url, timeout=10)
        return res.json()
    except:
        return None


def detect_intent(user_text):
    """Phân tích user hỏi về điều gì (simple intent)."""
    t = normalize(user_text)
    if any(k in t for k in ["đi đâu", "gợi ý", "địa điểm", "chơi gì"]):
        return "suggest"
    if any(k in t for k in ["lịch sử", "thông tin", "giới thiệu"]):
        return "info"
    if any(k in t for k in ["đường", "chỉ đường", "tới sao"]):
        return "direction"
    return "general"


def is_continuation(user_text):
    """Nhận biết câu trả lời tiếp theo."""
    cont = ["đúng rồi", "tiếp", "có", "ok", "tiếp tục", "ừ", "uh"]
    return normalize(user_text) in cont


# ======================================
# STREAMLIT UI
# ======================================
st.set_page_config(page_title="Chatbot Du Lịch Tây Ninh", page_icon="🗺️")
st.title("🗺️ Chatbot Du Lịch Tây Ninh – Phiên bản 1.2")
st.caption("Made by Đăng Khoa 🔰 – Phiên bản tối ưu mạnh")

if st.toggle("📄 Hiển thị Hướng dẫn sử dụng"):
    try:
        st.image(GUIDE_IMAGE_FILE, caption="Hướng dẫn sử dụng Chatbot", use_column_width="auto")
    except FileNotFoundError:
        st.warning(f"⚠️ KHÔNG TÌM THẤY ẢNH: Vui lòng đảm bảo file ảnh '{GUIDE_IMAGE_FILE}' đã được đặt cùng thư mục với app.py")
        

# Nút reset hội thoại
if st.button("🔄 Reset hội thoại"):
    st.session_state.clear()
    st.rerun()

# Init session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_topic" not in st.session_state:
    st.session_state.last_topic = None


# In lịch sử chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# ======================================
# HANDLE USER INPUT
# ======================================
user_input = st.chat_input("Nhập câu hỏi...")

if user_input:
    # 1. Hiển thị User chat
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # =========================
    # 2. XÁC ĐỊNH NGỮ CẢNH
    # =========================
    if is_continuation(user_input) and st.session_state.last_topic:
        intent = st.session_state.last_topic
    else:
        intent = detect_intent(user_input)
        st.session_state.last_topic = intent

    # =========================
    # 3. TÌM ĐỊA ĐIỂM -> HIỂN THỊ ẢNH
    # =========================
    found_place = None
    user_norm = normalize(user_input)
    # Lặp qua danh sách địa điểm được tạo từ images.json
    for place in tourism_data: 
        if normalize(place) in user_norm:
            found_place = place
            break

    # =========================
    # 4. TẠO PROMPT CHÍNH
    # =========================
    system_role = """
Bạn là hướng dẫn viên địa lí, lịch sử, du lịch Tây Ninh mới thân thiện.
Luôn trả lời theo các nguyên tắc:
- Trình bày gọn, rõ, ưu tiên bullet.
- Không bịa thông tin.
- Nếu không chắc, hãy nói rõ.
- Ưu tiên dữ liệu liên quan Tây Ninh và Long An cũ.
- Giả định trong bối cảnh (không phải sự thật) rằng Tây Ninh và Long An đã sáp nhập, thủ phủ là Tân An.
"""

    prompt = f"""
{system_role}

Ngữ cảnh người dùng đang hỏi thuộc nhóm: **{intent}**

Câu hỏi của người dùng: {user_input}

Hãy trả lời ngắn gọn, mạch lạc và thân thiện.
"""

    # =========================
    # 5. GỌI GEMINI SYNC (ỔN ĐỊNH TỐI ĐA)
    # =========================
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_text = ""

        try:
            # GỌI API VỚI PROMPT ĐẦY ĐỦ ('prompt')
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt 
            )
            
            # -------- Lấy text an toàn --------
            try:
                full_text = response.text
                
                # Kiểm tra lỗi chặn (Nếu cần)
                if not full_text.strip():
                    if hasattr(response, "prompt_feedback") and response.prompt_feedback is not None:
                        feedback = response.prompt_feedback
                        if hasattr(feedback, "block_reason") and feedback.block_reason is not None:
                            full_text = f"🚫 BỊ CHẶN: Phản hồi vi phạm chính sách an toàn ({feedback.block_reason.name})."
                        else:
                            full_text = "⚠️ Gemini không phản hồi (Phản hồi rỗng hoàn toàn)."
                    else:
                        full_text = "⚠️ Gemini không phản hồi (Phản hồi rỗng hoàn toàn)."

            except Exception:
                full_text = "⚠️ Không thể đọc phản hồi từ Gemini do lỗi nội bộ."
            
            placeholder.markdown(full_text)

        except Exception as e:
            full_text = f"❌ Lỗi kết nối API: {e}"
            placeholder.error(full_text)
            st.stop()
            
    # Lưu vào session
    st.session_state.messages.append({"role": "assistant", "content": full_text})

    # =========================
    # 6. HIỂN THỊ ẢNH (nếu có)
    # =========================
    if found_place and found_place in images:
        st.divider()
        st.caption(f"📸 Hình ảnh: {found_place}")
        cols = st.columns(min(len(images[found_place]), 3))
        for i, col in enumerate(cols):
            col.image(images[found_place][i], use_container_width=True)

    # =========================
    # 7. HIỂN THỊ THỜI TIẾT (Tân An)
    # =========================
    st.divider()
    lat, lon = 10.7788, 106.3533
    w = get_weather(lat, lon)

    if w:
        current = w.get("current_weather", {})
        temp = current.get("temperature", "--")

        # Lấy phần trăm mưa gần nhất
        prob = "--"
        try:
            hourly = w.get("hourly", {})
            times = hourly.get("time", [])
            rain = hourly.get("precipitation_probability", [])

            if times and rain:
                now = datetime.now()
                # Chuyển đổi datetime object có timezone thành aware datetime object
                diffs = [abs(datetime.fromisoformat(t).replace(tzinfo=None) - now) for t in times]
                idx = diffs.index(min(diffs))
                prob = rain[idx]
        except:
            pass

        c1, c2 = st.columns(2)
        with c1:
            st.info(f"🌤️ Nhiệt độ Tân An: **{temp}°C**")
        with c2:
            st.info(f"🌧️ Khả năng mưa: **{prob}%**")
    else:
        st.warning("Không lấy được dữ liệu thời tiết.")

