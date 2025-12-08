import streamlit as st
import google.genai as genai
import requests
import json
import re
from unidecode import unidecode
from datetime import datetime
import time


# CONFIG GEMINI
MODEL_NAME = "gemini-2.5-flash-lite"
client = genai.Client(
    api_key=st.secrets["gemini_key"],
)


# LOAD DATA
IMAGES_FILE = "images.json"
GUIDE_IMAGE_FILE = "huongdan.png"
recomend_file="goiy.png"

# Load ảnh và tạo ds địa điểm từ key
images = {}
tourism_data = {}
try:
    with open(IMAGES_FILE, "r", encoding="utf-8") as f:
        images = json.load(f)
        
    # TẠO DANH SÁCH ĐỊA ĐIỂM TỪ KEY CỦA FILE ẢNH
    tourism_data = {place: "" for place in images.keys()} 

except Exception as e:
    images = {}
    tourism_data = {}
    st.error(f"❌ Lỗi tải file images.json: {e}") 
    st.warning("⚠️ Không tìm thấy images.json hoặc JSON không hợp lệ. Tính năng tìm kiếm ảnh bị vô hiệu hóa.")



# UTILITIES
def normalize(text):
    if not text:
        return ""
    t = unidecode(text.lower())
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@st.cache_data(ttl=600)
def get_weather(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&current_weather=true&hourly=precipitation_probability&timezone=auto"
    )
    try:
        res = requests.get(url, timeout=30)
        return res.json()
    except:
        st.warning(f"Weather API error: {e}")
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


# STREAMLIT UI
st.set_page_config(page_title="Chatbot Du Lịch Tây Ninh", page_icon="⚡️")
st.title("⚡️ Chatbot Du Lịch Tây Ninh – Phiên bản 1.2")
st.caption("Made by Đăng Khoa 🔰 – Phiên bản tối ưu mạnh 🍀")
st.caption("🎯⚠️ Giới hạn của chatbot: thông tin có độ chính xác không phải là tuyệt đối nhưng nằm ở mức có thể tham khảo!")

if st.toggle("📄 Hiển thị Hướng dẫn sử dụng"):
    try:
        st.image(GUIDE_IMAGE_FILE, caption="Hướng dẫn sử dụng Chatbot", use_column_width="auto")
    except FileNotFoundError:
        st.warning(f"⚠️ KHÔNG TÌM THẤY ẢNH: Vui lòng đảm bảo file ảnh '{GUIDE_IMAGE_FILE}' đã được đặt cùng thư mục với app.py")

if st.toggle("📄 Hiển thị gợi ý sử dụng"):
    try:
        st.image(recomend_file, caption="Gợi ý sử dụng Chatbot", use_column_width="auto")
    except FileNotFoundError:
        st.warning(f"⚠️ KHÔNG TÌM THẤY ẢNH: Vui lòng đảm bảo file ảnh '{recomend_file}' đã được đặt cùng thư mục với app.py")

st.divider()
st.caption("Thời tiết tại Tân An (Trung tâm hành chính - Chính trị của tỉnh)")
    
# Tọa độ Tân An
lat, lon = 10.7788, 106.3533
w = get_weather(lat, lon)

temp = "--"
prob = "--"

if w:
    try:
        # 1. Lấy nhiệt độ hiện tại (current)
        current = w.get("current_weather", {})
        temp = current.get("temperature", "--")

        # 2. Lấy phần trăm mưa gần nhất (hourly)
        hourly = w.get("hourly", {})
        times = hourly.get("time", [])
        rain = hourly.get("precipitation_probability", [])

        if times and rain:
            now = datetime.now().replace(microsecond=0) # Lấy thời gian hiện tại
                
            # Tính khoảng cách thời gian giữa các dự báo và thời điểm hiện tại
            diffs = []
            for t in times:
                try:
                    # Chuyển đổi và loại bỏ thông tin múi giờ để so sánh an toàn hơn
                    diffs.append(abs(datetime.fromisoformat(t).replace(tzinfo=None) - now))
                except:
                    # Bỏ qua nếu có lỗi định dạng thời gian
                    pass
                
                # Chỉ xử lý nếu tìm thấy ít nhất một mốc thời gian hợp lệ
            if diffs and min(diffs).total_seconds() < 3600: # Đảm bảo mốc thời gian gần (trong vòng 1 giờ)
                idx = diffs.index(min(diffs))
                prob = rain[idx]
                
    except Exception as e:
        # Nếu có bất kỳ lỗi nào trong quá trình xử lý JSON
        # print(f"Lỗi xử lý thời tiết: {e}") # Có thể dùng để debug nếu có terminal
        pass

c1, c2 = st.columns(2)
with c1:
    # Đảm bảo nhiệt độ luôn được hiển thị ở dạng chuỗi, không lỗi nếu là số
    st.info(f"🌤️ Nhiệt độ Tân An: **{temp}°C**")
with c2:
    st.info(f"🌧️ Khả năng mưa: **{prob}%**")

# Nếu cả hai đều không lấy được dữ liệu, đưa ra cảnh báo chung
if temp == "--" and prob == "--":
    st.warning("⚠️ Không lấy được dữ liệu thời tiết ổn định (Lỗi kết nối API thời tiết).")

# Nút reset
if st.button("🔄 Reset hội thoại"):
    st.session_state.clear()
    st.rerun()

# Init session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_topic" not in st.session_state:
    st.session_state.last_topic = None
if "request_times" not in st.session_state: 
    st.session_state.request_times = []


# print lịch sử chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])



# USER INPUT

user_input = st.chat_input("Nhập câu hỏi...")

if user_input:
    current_time = time.time()


    # 1. KTRA RATE LIMIT TÙY CHỈNH (7 RPM)
    # Lọc bỏ các request đã quá 60 giây (tính từ thời điểm hiện tại)
    
    st.session_state.request_times = [
        t for t in st.session_state.request_times if current_time - t <= 60
    ]
    
    current_count = len(st.session_state.request_times)
    
    if current_count >= 7: # Cảnh báo nếu request thứ 8 được gửi trong 60 giây
        st.warning(
            "⚠️ **CẢNH BÁO TỐC ĐỘ:** Bạn đã hỏi **quá 5 lần trong 1 phút!** "
            "Nếu bạn tiếp tục hỏi nhanh, ứng dụng có thể bị lỗi 'Hết Quota' (429)."
            "Vui lòng chờ một lát rồi thử lại."
        )
        # Ngừng xử lý input nếu quá giới hạn 5 RPM
        st.stop()
    else:
        # Nếu chưa quá 8 RPM, thêm timestamp của request hiện tại
        st.session_state.request_times.append(current_time)

    # 1. Hiển thị User chat
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
        
    # 2. XÁC ĐỊNH NGỮ CẢNH
    if is_continuation(user_input) and st.session_state.last_topic:
        intent = st.session_state.last_topic
    else:
        intent = detect_intent(user_input)
        st.session_state.last_topic = intent


    # 3. TÌM PLACE CHO IMAGES
    found_place = None
    user_norm = normalize(user_input)
    for place in tourism_data: 
        if normalize(place) in user_norm:
            found_place = place
            break


    # 4. MAIN PROMPT:>
    system_role = """
Bạn là hướng dẫn viên địa lí, lịch sử, du lịch Tây Ninh, Long An thân thiện.
Luôn trả lời theo các nguyên tắc:
- Trình bày gọn, rõ, ưu tiên bullet.
- Không bịa thông tin.
- Nếu không chắc, hãy nói rõ.
- Ưu tiên dữ liệu liên quan Tây Ninh và Long An.
- Bối cảnh Tây Ninh và Long An đã sáp nhập, trung tâm hành chính - chính trị đặt tại thành phố Tân An.
- PHẢI SỬ DỤNG DỮ LIỆU KINH TẾ/DÂN SỐ/DIỆN TÍCH ĐƯỢC CUNG CẤP DƯỚI ĐÂY.
"""
    tayninh_data = """
# DỮ LIỆU CƠ BẢN VỀ TỈNH TÂY NINH (GIẢ ĐỊNH SAU KHI SÁP NHẬP VỚI LONG AN)
- Tây Ninh là một tỉnh thuộc vùng Đông Nam Bộ, Việt Nam và có quy mô kinh tế đứng thứ 10 cả nước, nằm trong Vùng kinh tế trọng điểm phía Nam.
- Vị trí địa lý: Cầu nối giữa Thành phố Hồ Chí Minh và thủ đô Phnôm Pênh (Campuchia), khu vực chuyển tiếp giữa Đông Nam Bộ với Đồng bằng sông Cửu Long.
- Phân chia hành chính: Hiện có 96 đơn vị hành chính cấp xã (14 phường và 82 xã).
- Tổng diện tích: 8.536,44 km2.
- Dân số (Sau sáp nhập): Khoảng 3.254.170 người (thấp nhất khu vực Đông Nam Bộ).
- Dữ liệu kinh tế (Theo dữ liệu sáp nhập tỉnh, thành Việt Nam năm 2025):
  - Diện tích: 8.536 km², xếp thứ 18.
  - Dân số: 3.254.170 người, xếp thứ 18.
  - GRDP 2024: 312.456.603 triệu VNĐ, xếp thứ 10.
  - Thu ngân sách 2024: 39.704.480 triệu VNĐ, xếp thứ 12.
  - Thu nhập bình quân: 58,54 triệu VNĐ/năm, xếp thứ 16.
- Giả định bối cảnh: Tây Ninh và Long An đã sáp nhập, thủ phủ là Tân An.
"""

    prompt = f"""
{system_role}
{tayninh_data}

Ngữ cảnh người dùng đang hỏi thuộc nhóm: **{intent}**

Câu hỏi của người dùng: {user_input}

Hãy trả lời ngắn gọn, mạch lạc và thân thiện, sử dụng theo ngôn ngữ mà người dùng hỏi.
"""


    # 5. GỌI GEMINI SYNC
    full_text = ""

    with st.spinner("🤖 Đang suy nghĩ và tổng hợp thông tin..."):
        
        # Khởi tạo placeholder để giữ vị trí cho câu trả lời
        placeholder = st.empty() 

        try:
            # GỌI API VỚI PROMPT ĐẦY ĐỦ ('prompt')
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt 
            )
            
            # Lấy text sàe
            try:
                full_text = response.text
                
                # Kiểm tra lỗi chặn (Nếu cần)
                if not full_text.strip():
                    if hasattr(response, "prompt_feedback") and response.prompt_feedback is not None:
                        feedback = response.prompt_feedback
                        if hasattr(feedback, "block_reason") and feedback.block_reason is not None:
                            full_text = f"🚫 BỊ CHẶN: Phản hồi vi phạm chính sách an toàn ({feedback.block_reason.name})."
                        else:
                            full_text = "⚠️ Gemini không phản hồi (Phản hồi rỗng)."
                    else:
                        full_text = "⚠️ Gemini không phản hồi (Phản hồi rỗng)."

            except Exception:
                full_text = "⚠️ Không thể đọc phản hồi từ Gemini do lỗi nội bộ."
            
            # Hiển thị câu trả lời (sau khi spinner đã biến mất)
            placeholder.markdown(full_text)

        except Exception as e:
            full_text = f"❌ Lỗi kết nối API: {e}"
            st.error(full_text)
            st.stop()
            
    # Lưu vào ss
    st.session_state.messages.append({"role": "assistant", "content": full_text})


    # 6. PRINT IMAGES 
    if found_place and found_place in images:
        st.divider()
        st.caption(f"📸 Hình ảnh gợi ý: {found_place}")
        cols = st.columns(min(len(images[found_place]), 3))
        for i, col in enumerate(cols):
            col.image(images[found_place][i], use_container_width=True)
























