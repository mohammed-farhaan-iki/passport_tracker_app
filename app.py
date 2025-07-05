import streamlit as st
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import io
import re
import requests
from pdf2image import convert_from_bytes

# ✅ Tesseract path (adjust as needed)
pytesseract.pytesseract.tesseract_cmd = r"C:\Tesseract-OCR\tesseract.exe"

# 📌 Preprocessing image for better OCR accuracy
def preprocess_image(image):
    image = image.convert('L')  # Grayscale
    image = image.filter(ImageFilter.MedianFilter())  # Noise reduction
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2)  # Boost contrast
    return image

# 🔍 OCR with config
def extract_text_from_image(image_data):
    img = preprocess_image(Image.open(io.BytesIO(image_data)))
    config = "--psm 6 -c preserve_interword_spaces=1"
    text = pytesseract.image_to_string(img, config=config)
    return text

# 📄 PDF handling
def extract_text_from_pdf(file_bytes, poppler_path):
    images = convert_from_bytes(file_bytes, poppler_path=poppler_path)
    img = preprocess_image(images[0])
    config = "--psm 6 -c preserve_interword_spaces=1"
    text = pytesseract.image_to_string(img, config=config)
    return text, images[0]

# 🧠 Passport data extraction
def parse_passport_data(text):
    text = text.replace('\n', ' ').replace('<<', '<').upper()
    mrz_lines = re.findall(r'P<[^ ]+|[A-Z0-9<]{40,}', text)
    mrz = ' '.join(mrz_lines) if mrz_lines else ""

    # Name extraction from MRZ
    name = "N/A"
    name_match = re.search(r'P<([A-Z<]+)<<?([A-Z<]+)', mrz)
    if name_match:
        surname = name_match.group(1).replace('<', ' ').strip().title()
        given_names = name_match.group(2).replace('<', ' ').strip().title()
        name = f"{given_names} {surname}"

    # Passport number
    passport_number_match = re.search(r'\b([A-Z][0-9]{7,8})\b', text)
    passport_number = passport_number_match.group(1) if passport_number_match else "N/A"

    # Country code
    country_code = "N/A"
    code_by_label = re.search(r'(?:NATIONALITY|COUNTRY CODE)[:\s]*([A-Z]{3})', text)
    if code_by_label:
        country_code = code_by_label.group(1)
    else:
        mrz_code_match = re.search(r'^P<([A-Z]{3})', mrz)
        if mrz_code_match:
            country_code = mrz_code_match.group(1)
        elif "IND" in text:
            country_code = "IND"

    # Dates
    dob_match = re.search(r'(?:DATE OF BIRTH|DOB|BIRTH DATE)[:\s-]*([0-9]{2}[/-][0-9]{2}[/-][0-9]{4})', text, re.IGNORECASE)
    doi_match = re.search(r'DATE OF ISSUE[:\s]*([0-9]{2}[/-][0-9]{2}[/-][0-9]{4})', text)
    doe_match = re.search(r'DATE OF EXPIRY[:\s]*([0-9]{2}[/-][0-9]{2}[/-][0-9]{4})', text)
    dates = re.findall(r'([0-9]{2}[/-][0-9]{2}[/-][0-9]{4})', text)

    date_of_birth = dob_match.group(1) if dob_match else (dates[0] if len(dates) > 0 else "N/A")
    date_of_issue = doi_match.group(1) if doi_match else (dates[1] if len(dates) > 1 else "N/A")
    date_of_expiry = doe_match.group(1) if doe_match else (dates[2] if len(dates) > 2 else "N/A")

    return {
        "Name": name,
        "Passport Number": passport_number,
        "Code": country_code,
        "Date of Birth": date_of_birth,
        "Date of Issue": date_of_issue,
        "Date of Expiry": date_of_expiry
    }

# 📤 Upload to Google Sheet
def upload_to_sheet(data):
    url = "https://script.google.com/macros/s/AKfycbwJzsQJ1rBXcgoTbajbIzYOH0czUM958RJZbv2DDKMDluzOp25WK2xBHIwtZbNF6394qA/exec"
    response = requests.post(url, json={
        "name": data.get("Name", ""),
        "passport_number": data.get("Passport Number", ""),
        "code": data.get("Code", ""),
        "date_of_birth": data.get("Date of Birth", ""),
        "date_of_issue": data.get("Date of Issue", ""),
        "date_of_expiry": data.get("Date of Expiry", "")
    })
    st.write("🔍 Data sent to Google Sheet:", data)
    if response.status_code == 200:
        st.success("✅ Uploaded to Google Sheet!")
    else:
        st.error("❌ Failed to upload.")

# 🖥️ Streamlit UI
st.title("🛂 Passport Scanner (Enhanced Accuracy)")

uploaded_file = st.file_uploader("📥 Upload Passport Image or PDF", type=["jpg", "jpeg", "png", "pdf"])

if uploaded_file:
    file_bytes = uploaded_file.read()

    if uploaded_file.type == "application/pdf":
        st.info("📄 PDF uploaded. Converting...")
        text, img_preview = extract_text_from_pdf(
            file_bytes,
            poppler_path=r"C:\Users\Mohammed Farhaan\Downloads\Release-24.08.0-0\poppler-24.08.0\Library\bin"
        )
        st.image(img_preview, caption="PDF Page 1", use_container_width=True)
    else:
        st.image(uploaded_file, caption="Uploaded Image", use_container_width=True)
        text = extract_text_from_image(file_bytes)

    parsed_data = parse_passport_data(text)

    st.subheader("✏️ Review & Edit Extracted Data")

    default_fields = {
        "Name": "",
        "Passport Number": "",
        "Code": "",
        "Date of Birth": "",
        "Date of Issue": "",
        "Date of Expiry": ""
    }
    
    with st.form("edit_form"):
        cols = st.columns(2)
        edited_data = {}

        for i, (key, default_val) in enumerate(default_fields.items()):
            with cols[i % 2]:
                edited_data[key] = st.text_input(key, parsed_data.get(key, default_val))


        submitted = st.form_submit_button("📤 Upload to Google Sheet")
        if submitted:
            upload_to_sheet(edited_data)

    with st.expander("📝 Raw OCR Text"):
        st.text(text)
        st.json(edited_data)

