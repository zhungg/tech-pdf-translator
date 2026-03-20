import streamlit as st
import fitz  # PyMuPDF
import re
import io
import os
import time
import urllib.request
from groq import Groq

# Configure Streamlit page
st.set_page_config(page_title="In-place PDF Translator", page_icon="📄", layout="wide")

st.title("High-Fidelity In-place PDF Translator (English to Vietnamese)")
st.write("Upload a PDF to translate its text while preserving layout, images, and formulas.")

# API Key input
api_key = st.text_input("Groq API Key (bắt đầu bằng gsk_)", type="password")
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

@st.cache_resource
def download_vietnamese_font():
    """Tự động tải font tiếng Việt chuẩn Google để trị dứt điểm lỗi ô vuông"""
    font_path = "NotoSans-Regular.ttf"
    if not os.path.exists(font_path):
        try:
            url = "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf"
            urllib.request.urlretrieve(url, font_path)
        except Exception as e:
            st.error(f"Lỗi tải font: {e}")
    return font_path

def is_math_or_table(text):
    """
    Bộ lọc thông minh: 
    1. Bỏ qua công thức toán học
    2. Bỏ qua bảng biểu, tiêu đề ngắn (dưới 6 từ) để giữ form
    3. Bỏ qua các khối chứa quá nhiều số liệu
    """
    text = text.strip()
    words = text.split()
    
    # Bỏ qua chữ quá ngắn (thường là tiêu đề, ô trong bảng, chú thích ảnh)
    if len(words) < 6:
        return True
        
    # Bỏ qua nếu chứa nhiều số liệu (mật độ số > 20%)
    digits = sum(c.isdigit() for c in text)
    if digits / max(len(text), 1) > 0.2:
        return True
        
    # Bỏ qua công thức
    math_symbols = ['$', '\\int', '\\sum', '\\alpha', '\\beta', '\\gamma', '\\theta', '\\mu', '\\pi', '^', '_']
    if any(sym in text for sym in math_symbols):
        return True
        
    return False

def translate_text(text, client):
    """Gửi đoạn văn bản cho Groq với Kỷ luật thép."""
    system_prompt = """
    Bạn là một máy dịch thuật kỹ thuật (Điện tử Viễn thông).
    QUY TẮC BẮT BUỘC:
    1. CHỈ xuất ra bản dịch tiếng Việt.
    2. KHÔNG BAO GIỜ thêm lời chào, xin lỗi, hay giải thích (Tuyệt đối không dùng các câu như "Dưới đây là bản dịch", "Tôi đã sao chép").
    3. Giữ nguyên thuật ngữ tiếng Anh nếu khó dịch.
    """
    try:
        time.sleep(1) 
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            model="llama-3.1-8b-instant", 
            temperature=0.1 # Giảm sự sáng tạo để AI bớt "nói nhảm"
        )
        # Lọc bỏ một lần nữa nếu AI ngoan cố trả lời bằng dấu ngoặc kép hoặc lời dẫn
        result = chat_completion.choices[0].message.content.strip()
        result = re.sub(r'^(Dưới đây là|Bản dịch|Tôi xin lỗi).*?:', '', result, flags=re.IGNORECASE).strip()
        return result
    except Exception as e:
        return text

if uploaded_file is not None and api_key:
    client = Groq(api_key=api_key)
    font_path = download_vietnamese_font()
    
    if st.button("Translate PDF"):
        with st.spinner("Đang biên dịch đoạn văn, bảo vệ bảng biểu và hình ảnh..."):
            try:
                pdf_bytes = uploaded_file.read()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                
                font_name = "noto" if os.path.exists(font_path) else "helv"
                
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
                            
                            # Chỉ dịch nếu KHÔNG phải là bảng/công thức/tiêu đề ngắn
                            if not is_math_or_table(original_text):
                                translated_text = translate_text(original_text, client)
                                
                                if translated_text and translated_text != original_text:
                                    # Xóa chữ cũ
                                    page.add_redact_annot(rect, fill=(1, 1, 1))
                                    page.apply_redactions()
                                    
                                    # Vẽ chữ mới với font tải sẵn
                                    current_size = 11 
                                    while current_size > 4:
                                        rc = page.insert_textbox(
                                            rect, 
                                            translated_text, 
                                            fontsize=current_size, 
                                            fontname=font_name,
                                            fontfile=font_path,
                                            color=(0, 0, 0),
                                            align=0
                                        )
                                        if rc >= 0: break 
                                        current_size -= 0.5
                    
                    progress_bar.progress((page_num + 1) / total_pages)
                
                output_pdf = io.BytesIO()
                doc.save(output_pdf)
                doc.close()
                
                st.success("🎉 Dịch thành công! Đã fix lỗi font và bảng biểu.")
                st.download_button(
                    label="Tải PDF đã dịch",
                    data=output_pdf.getvalue(),
                    file_name="translated_document_fixed.pdf",
                    mime="application/pdf"
                )
                
            except Exception as e:
                st.error(f"Lỗi hệ thống: {e}")
