import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai
import re
import io
import os
import time

# Configure Streamlit page
st.set_page_config(page_title="In-place PDF Translator", page_icon="📄", layout="wide")

st.title("High-Fidelity In-place PDF Translator (English to Vietnamese)")
st.write("Upload a PDF to translate its text while preserving layout, images, and formulas.")

# API Key input
api_key = st.text_input("Gemini API Key", type="password")
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

def is_math_or_technical(text):
    """Lọc bỏ các công thức toán, số liệu và biến số kỹ thuật ngắn."""
    text = text.strip()
    if not text or len(text) < 2:
        return True
    
    # Check if it's just numbers or basic math
    if re.match(r'^[\d\s\.,\-\+\*/=()\[\]{}]+$', text):
        return True
        
    # Check for common LaTeX/Math symbols
    math_symbols = ['$', '\\int', '\\sum', '\\alpha', '\\beta', '\\gamma', '\\theta', '\\mu', '\\pi', '^', '_']
    if any(sym in text for sym in math_symbols):
        return True
        
    # Check if it's a short technical variable (e.g., TiO2, x)
    if len(text) <= 5 and not re.search(r'[a-zA-Z]{3,}', text):
        return True
        
    return False

def translate_text(text, model_instance):
    """Gửi đoạn văn bản cho Gemini dịch."""
    prompt = f"""
    Bạn là một chuyên gia dịch thuật tài liệu kỹ thuật chuyên ngành Điện tử Viễn thông. 
    Hãy dịch đoạn văn bản sau sang tiếng Việt học thuật.
    Yêu cầu: 
    1. Giữ nguyên các ký hiệu công thức, biến số.
    2. Chỉ trả về bản dịch, không thêm lời dẫn hay giải thích.
    
    Văn bản: {text}
    """
    try:
        # Nghỉ 2 giây để tránh vượt quá giới hạn 15 request/phút của gói Free
        time.sleep(2) 
        response = model_instance.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        # Báo lỗi màu đỏ ra màn hình nếu API bị lỗi
        st.error(f"Lỗi API khi dịch đoạn '{text[:20]}...': {e}")
        return text

if uploaded_file is not None and api_key:
    # Cấu hình AI
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    if st.button("Translate PDF"):
        with st.spinner("Đang phân tích và dịch thuật (quá trình này sẽ hơi chậm để tránh lỗi quá tải API)..."):
            try:
                # Load the PDF
                pdf_bytes = uploaded_file.read()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                
                # Setup Font tiếng Việt
                font_path = "NotoSans-Regular.ttf"
                if os.path.exists(font_path):
                    user_font = font_path
                    font_name = "noto"
                else:
                    st.warning("⚠️ Không tìm thấy file NotoSans-Regular.ttf trên GitHub. Chữ tiếng Việt có thể bị lỗi.")
                    user_font = None
                    font_name = "helv"
                
                progress_bar = st.progress(0)
                total_pages = len(doc)
                
                for page_num in range(total_pages):
                    page = doc[page_num]
                    blocks = page.get_text("dict")["blocks"]
                    
                    for block in blocks:
                        if block["type"] == 0: # Chỉ xử lý Text block
                            # 1. Gộp toàn bộ chữ trong 1 khối để dịch 1 lần
                            block_text = ""
                            for line in block["lines"]:
                                for span in line["spans"]:
                                    block_text += span["text"] + " "
                            
                            original_text = block_text.strip()
                            rect = fitz.Rect(block["bbox"]) # Lấy tọa độ của cả khối
                            
                            # 2. Lọc & Dịch
                            if not is_math_or_technical(original_text):
                                translated_text = translate_text(original_text, model)
                                
                                # 3. Xóa chữ cũ và ghi chữ mới
                                if translated_text and translated_text != original_text:
                                    # Xóa nền
                                    page.add_redact_annot(rect, fill=(1, 1, 1))
                                    page.apply_redactions()
                                    
                                    # Auto-scale chữ tiếng Việt cho vừa khung
                                    current_size = 12 
                                    while current_size > 4:
                                        rc = page.insert_textbox(
                                            rect, 
                                            translated_text, 
                                            fontsize=current_size, 
                                            fontname=font_name,
                                            fontfile=user_font,
                                            color=(0, 0, 0), # Text màu đen
                                            align=0
                                        )
                                        if rc >= 0: break # Vừa vặn thì thoát vòng lặp
                                        current_size -= 0.5
                    
                    # Cập nhật thanh tiến trình sau mỗi trang
                    progress_bar.progress((page_num + 1) / total_pages)
                
                # Xuất file PDF mới
                output_pdf = io.BytesIO()
                doc.save(output_pdf)
                doc.close()
                
                st.success("🎉 Đã dịch xong hoàn tất!")
                st.download_button(
                    label="Tải PDF đã dịch",
                    data=output_pdf.getvalue(),
                    file_name="translated_document.pdf",
                    mime="application/pdf"
                )
                
            except Exception as e:
                st.error(f"Lỗi hệ thống: {e}")
