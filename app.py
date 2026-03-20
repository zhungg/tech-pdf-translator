import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai
import re
import io

# Configure Streamlit page
st.set_page_config(page_title="In-place PDF Translator", page_icon="📄", layout="wide")

st.title("High-Fidelity In-place PDF Translator (English to Vietnamese)")
st.write("Upload a PDF to translate its text while preserving layout, images, and formulas.")

# API Key input
api_key = st.text_input("Gemini API Key", type="password")
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

def is_math_or_technical(text):
    """
    Pre-filtering rule to detect if a block consists only of math symbols, 
    formulas, numbers, or technical variables.
    """
    text = text.strip()
    if not text:
        return True
    
    # Check if it's just numbers or basic punctuation
    if re.match(r'^[\d\s\.,\-\+\*/=()\[\]{}]+$', text):
        return True
        
    # Check for common LaTeX/Math symbols
    math_symbols = ['$', '\\int', '\\sum', '\\alpha', '\\beta', '\\gamma', '\\theta', '\\mu', '\\pi']
    if any(sym in text for sym in math_symbols):
        return True
        
    # Check if it's a short technical variable (e.g., TiO2, x, y)
    if len(text) <= 5 and not re.search(r'[a-zA-Z]{3,}', text):
        return True
        
    return False

def translate_text(text, client):
    """Translate conversational English to formal academic Vietnamese."""
    prompt = f"""
    You are an expert technical translator. Translate the following English text to formal academic Vietnamese.
    Do not include any introductory or concluding remarks, just output the translated text.
    Preserve any technical terms or formatting.
    
    English:
    {text}
    """
    try:
        response = client.models.generate_content(
            model='gemini-3.1-pro-preview',
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        st.error(f"Translation error: {e}")
        return text

if uploaded_file is not None and api_key:
    client = genai.Client(api_key=api_key)
    
    if st.button("Translate PDF"):
        with st.spinner("Processing PDF..."):
            try:
                # Load the PDF
                pdf_bytes = uploaded_file.read()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                
                # Use a built-in font that supports basic Unicode, or load Noto Sans if available locally
                # doc.insert_font(fontname="noto", fontfile="path/to/NotoSans-Regular.ttf")
                font_name = "helv" 
                
                progress_bar = st.progress(0)
                total_pages = len(doc)
                
                for page_num in range(total_pages):
                    page = doc[page_num]
                    
                    # 1. Precise Extraction
                    blocks = page.get_text("dict")["blocks"]
                    
                    for block in blocks:
                        if block["type"] == 0: # Text block
                            for line in block["lines"]:
                                for span in line["spans"]:
                                    text = span["text"]
                                    rect = fitz.Rect(span["bbox"])
                                    color = span["color"]
                                    font_size = span["size"]
                                    
                                    # 2. Verification & Error Reduction
                                    if not is_math_or_technical(text):
                                        # 3. Translation
                                        translated_text = translate_text(text, client)
                                        
                                        if translated_text and translated_text != text:
                                            # 4. Clean Redaction
                                            # Add redaction annotation and apply it to remove original text
                                            page.add_redact_annot(rect, fill=(1, 1, 1)) # Assuming white background
                                            page.apply_redactions()
                                            
                                            # 5. Smart Re-insertion
                                            # Convert integer color to RGB tuple for PyMuPDF
                                            r = ((color >> 16) & 255) / 255.0
                                            g = ((color >> 8) & 255) / 255.0
                                            b = (color & 255) / 255.0
                                            
                                            # Auto-scale font size to fit the original bounding box
                                            current_font_size = font_size
                                            while current_font_size > 4:
                                                rc = page.insert_textbox(
                                                    rect, 
                                                    translated_text, 
                                                    fontsize=current_font_size, 
                                                    fontname=font_name, 
                                                    color=(r, g, b),
                                                    align=0 # Left align
                                                )
                                                if rc >= 0: # Successfully inserted
                                                    break
                                                current_font_size -= 1
                    
                    progress_bar.progress((page_num + 1) / total_pages)
                
                # Save the modified PDF
                output_pdf = io.BytesIO()
                doc.save(output_pdf)
                doc.close()
                
                st.success("Translation complete!")
                
                st.download_button(
                    label="Download Translated PDF",
                    data=output_pdf.getvalue(),
                    file_name="translated_document.pdf",
                    mime="application/pdf"
                )
                
            except Exception as e:
                st.error(f"An error occurred: {e}")
