import streamlit as st
import fitz  # PyMuPDF
import re
import io
import os
import time
from groq import Groq

# Configure Streamlit page
st.set_page_config(page_title="In-place PDF Translator", page_icon="📄", layout="wide")

st.title("High-Fidelity In-place PDF Translator (English to Vietnamese)")
st.write("Upload a PDF to translate its text while preserving layout, images, and formulas.")

# API Key input (Đã đổi tên hiển thị)
api_key = st.text_input("Groq API Key (bắt đầu bằng gsk_)", type="password")
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

def is_math_or_technical(text):
    text = text.strip()
    if not text or len(text) < 2:
        return True
    if re.match(r'^[\d\s\.,\-\+\*/=()\[\]{}]+$', text):
        return True
    math_symbols = ['$', '\\int', '\\sum', '\\alpha', '\\beta', '\\gamma', '\\theta', '\\mu', '\\pi', '^', '_']
    if any(sym in text for sym in math_symbols):
        return True
    if len(text) <= 5 and not re.search(r'[a-zA-Z]{3,}', text):
        return True
    return False

def translate_text(text, client):
    """Gửi đoạn văn bản cho Groq dịch."""
    prompt = f"""
    Bạn là một chuyên gia dịch thuật tài liệu kỹ thuật chuyên ngành Điện tử Viễn thông. 
    Hãy dịch đoạn văn bản sau sang tiếng Việt học thuật.
    Yêu cầu: 
    1. Giữ nguyên các ký hiệu công thức, biến số.
    2. Chỉ trả về bản dịch, không thêm lời dẫn hay giải thích.
    
    Văn bản: {text}
    """
    try:
        # Tốc độ Groq cực nhanh, chỉ cần nghỉ 1 giây là đủ
        time.sleep(1) 
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant", 
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"Lỗi API Groq khi dịch đoạn '{text[:20]}...': {e}")
        return text

if uploaded_file is not None and api_key:
    # Khởi tạo máy chủ Groq
    client = Groq(api_key=api_key)
    
    if st.button("Translate PDF"):
        with st.spinner("Đang phân tích và dịch thuật với Llama 3..."):
            try:
                pdf_bytes = uploaded_file.read()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                
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
                        if block["type"] == 0: 
                            block_text = ""
                            for line in block["lines"]:
                                for span in line["spans"]:
                                    block_text += span["text"] + " "
                            
                            original_text = block_text.strip()
                            rect = fitz.Rect(block["bbox"]) 
                            
                            if not is_math_or_technical(original_text):
                                # Truyền client của Groq vào hàm dịch
                                translated_text = translate_text(original_text, client)
                                
                                if translated_text and translated_text != original_text:
                                    page.add_redact_annot(rect, fill=(1, 1, 1))
                                    page.apply_redactions()
                                    
                                    current_size = 12 
                                    while current_size > 4:
                                        rc = page.insert_textbox(
                                            rect, 
                                            translated_text, 
                                            fontsize=current_size, 
                                            fontname=font_name,
                                            fontfile=user_font,
                                            color=(0, 0, 0),
                                            align=0
                                        )
                                        if rc >= 0: break 
                                        current_size -= 0.5
                    
                    progress_bar.progress((page_num + 1) / total_pages)
                
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
