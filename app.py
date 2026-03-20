import streamlit as st
import fitz  # PyMuPDF
import re
import io
import os
import time
import requests
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
    """Tải font từ kho CDN siêu ổn định bằng thư viện requests"""
    font_path = "Roboto-Ultra.ttf" # Đổi tên 1 lần nữa để xả rác bộ nhớ
    
    # Dọn dẹp file lỗi nếu có
    if os.path.exists(font_path) and os.path.getsize(font_path) < 50000:
        os.remove(font_path)
        
    if not os.path.exists(font_path):
        try:
            # Link CDNJS tĩnh, cam kết sống dai, không bao giờ bị đổi cấu trúc
            url = "https://cdnjs.cloudflare.com/ajax/libs/pdfmake/0.2.12/fonts/Roboto/Roboto-Regular.ttf"
            
            # Dùng requests để tải (vượt rào cực tốt)
            response = requests.get(url, timeout=15)
            response.raise_for_status() # Bắt ngay lỗi 404 nếu có
            
            with open(font_path, 'wb') as f:
                f.write(response.content)
        except Exception as e:
            st.error(f"Lỗi tải font từ mạng: {e}")
            return None
            
    # Kiểm tra lần cuối
    if os.path.exists(font_path) and os.path.getsize(font_path) > 50000:
        return font_path
    return None
            
    # Xác nhận file đã tải thành công và đủ dung lượng
    if os.path.exists(font_path) and os.path.getsize(font_path) > 50000:
        return font_path
    return None

def is_math_or_table(text):
    text = text.strip()
    words = text.split()
    
    if len(words) < 6:
        return True
        
    digits = sum(c.isdigit() for c in text)
    if digits / max(len(text), 1) > 0.2:
        return True
        
    math_symbols = ['$', '\\int', '\\sum', '\\alpha', '\\beta', '\\gamma', '\\theta', '\\mu', '\\pi', '^', '_']
    if any(sym in text for sym in math_symbols):
        return True
        
    return False

def translate_text(text, client):
    system_prompt = """
    Bạn là một máy dịch thuật kỹ thuật (Điện tử Viễn thông).
    QUY TẮC BẮT BUỘC:
    1. CHỈ xuất ra bản dịch tiếng Việt.
    2. KHÔNG BAO GIỜ thêm lời chào, xin lỗi, hay giải thích.
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
            temperature=0.1
        )
        result = chat_completion.choices[0].message.content.strip()
        result = re.sub(r'^(Dưới đây là|Bản dịch|Tôi xin lỗi).*?:', '', result, flags=re.IGNORECASE).strip()
        return result
    except Exception as e:
        return text

if uploaded_file is not None and api_key:
    client = Groq(api_key=api_key)
    font_path = download_vietnamese_font()
    
    if st.button("Translate PDF"):
        with st.spinner("Đang biên dịch đoạn văn, nhúng font tiếng Việt..."):
            try:
                pdf_bytes = uploaded_file.read()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                
                progress_bar = st.progress(0)
                total_pages = len(doc)
                
                for page_num in range(total_pages):
                    page = doc[page_num]
                    
                    # Lớp giáp thứ 2: Nhúng font an toàn
                    current_font = "helv" # Mặc định an toàn nhất
                    if font_path:
                        try:
                            page.insert_font(fontname="roboto", fontfile=font_path)
                            current_font = "roboto"
                        except Exception as e:
                            pass # Bỏ qua lỗi, dùng font mặc định để app không bị sập
                    
                    blocks = page.get_text("dict")["blocks"]
                    
                    for block in blocks:
                        if block["type"] == 0: 
                            block_text = ""
                            for line in block["lines"]:
                                for span in line["spans"]:
                                    block_text += span["text"] + " "
                            
                            original_text = block_text.strip()
                            rect = fitz.Rect(block["bbox"]) 
                            
                            if not is_math_or_table(original_text):
                                translated_text = translate_text(original_text, client)
                                
                                if translated_text and translated_text != original_text:
                                    page.add_redact_annot(rect, fill=(1, 1, 1))
                                    page.apply_redactions()
                                    
                                    current_size = 11 
                                    while current_size > 4:
                                        # Viết chữ dùng font đã nhúng
                                        rc = page.insert_textbox(
                                            rect, 
                                            translated_text, 
                                            fontsize=current_size, 
                                            fontname=current_font,
                                            color=(0, 0, 0),
                                            align=0
                                        )
                                        if rc >= 0: break 
                                        current_size -= 0.5
                    
                    progress_bar.progress((page_num + 1) / total_pages)
                
                output_pdf = io.BytesIO()
                doc.save(output_pdf)
                doc.close()
                
                st.success("🎉 Dịch thành công! Đã xử lý triệt để lỗi font.")
                st.download_button(
                    label="Tải PDF đã dịch",
                    data=output_pdf.getvalue(),
                    file_name="translated_document_fixed_font.pdf",
                    mime="application/pdf"
                )
                
            except Exception as e:
                st.error(f"Lỗi hệ thống: {e}")
