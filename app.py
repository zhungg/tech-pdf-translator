import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai
import re
import io
import os

# Configure Streamlit page
st.set_page_config(page_title="In-place PDF Translator", page_icon="📄", layout="wide")

st.title("High-Fidelity In-place PDF Translator (English to Vietnamese)")
st.write("Upload a PDF to translate its text while preserving layout, images, and formulas.")

# API Key input
api_key = st.text_input("Gemini API Key", type="password")
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

def is_math_or_technical(text):
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
    """Sử dụng model_instance đã được khởi tạo để dịch"""
    prompt = f"""
    Bạn là một chuyên gia dịch thuật kỹ thuật. Hãy dịch đoạn văn bản sau sang tiếng Việt học thuật.
    Yêu cầu: 
    1. Giữ nguyên các ký hiệu công thức, biến số.
    2. Chỉ trả về bản dịch, không thêm lời dẫn.
    
    Văn bản: {text}
    """
    try:
        response = model_instance.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return text

if uploaded_file is not None and api_key:
    # Cấu hình AI
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    if st.button("Translate PDF"):
        with st.spinner("Đang phẫu thuật PDF và dịch thuật..."):
            try:
                pdf_bytes = uploaded_file.read()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                
                # KIỂM TRA FONT: Ưu tiên NotoSans-Regular.ttf nếu Hùng đã upload lên GitHub
                font_path = "NotoSans-Regular.ttf"
                if os.path.exists(font_path):
                    user_font = font_path
                    font_name = "noto"
                else:
                    st.warning("Không tìm thấy file NotoSans-Regular.ttf. Chữ tiếng Việt có thể bị lỗi font.")
                    user_font = None
                    font_name = "helv" # Sẽ bị lỗi tiếng Việt nếu dùng font này
                
                progress_bar = st.progress(0)
                total_pages = len(doc)
                
                for page_num in range(total_pages):
                    page = doc[page_num]
                    blocks = page.get_text("dict")["blocks"]
                    
                    for block in blocks:
                        if block["type"] == 0: # Text block
                            for line in block["lines"]:
                                for span in line["spans"]:
                                    original_text = span["text"]
                                    rect = fitz.Rect(span["bbox"])
                                    color = span["color"]
                                    font_size = span["size"]
                                    
                                    if not is_math_or_technical(original_text):
                                        # GỌI HÀM DỊCH: Truyền 'model' vào thay vì 'client'
                                        translated_text = translate_text(original_text, model)
                                        
                                        if translated_text and translated_text != original_text:
                                            # Xóa chữ cũ (Redaction)
                                            page.add_redact_annot(rect, fill=(1, 1, 1))
                                            page.apply_redactions()
                                            
                                            # Xử lý màu sắc RGB
                                            r = ((color >> 16) & 255) / 255.0
                                            g = ((color >> 8) & 255) / 255.0
                                            b = (color & 255) / 255.0
                                            
                                            # Chèn chữ mới với font tiếng Việt
                                            current_size = font_size
                                            while current_size > 4:
                                                rc = page.insert_textbox(
                                                    rect, 
                                                    translated_text, 
                                                    fontsize=current_size, 
                                                    fontname=font_name,
                                                    fontfile=user_font, # Dùng file font đã tải
                                                    color=(r, g, b),
                                                    align=0
                                                )
                                                if rc >= 0: break
                                                current_size -= 0.5
                    
                    progress_bar.progress((page_num + 1) / total_pages)
                
                # Xuất file
                output_pdf = io.BytesIO()
                doc.save(output_pdf)
                doc.close()
                
                st.success("Đã dịch xong!")
                st.download_button(
                    label="Tải PDF đã dịch",
                    data=output_pdf.getvalue(),
                    file_name="translated_document.pdf",
                    mime="application/pdf"
                )
                
            except Exception as e:
                st.error(f"Lỗi hệ thống: {e}")
