import streamlit as st
import pandas as pd
import io
from PIL import Image, ImageOps
import pdfplumber
import pytesseract
import re

# LAB_RULES dictionary here (copy from your code)
LAB_RULES = {
    # ... include your full lab rules dictionary here ...
}

# Function: Normalize value (copy from your code)
def normalize_value(value):
    value = str(value).replace(",", "").strip()
    if value.startswith('<') or value.startswith('>'):
        value = value[1:]
    if "Lakh" in value or "Lac" in value:
        try:
            num = float(re.findall(r"[\d\.]+", value)[0])
            return num * 100000
        except:
            return None
    match_num_unit = re.match(r"(\d+\.?\d*)\s*([a-zA-Z%/µ]+)?", value)
    if match_num_unit:
        try:
            return float(match_num_unit.group(1))
        except ValueError:
            return None
    try:
        return float(re.findall(r"[\d\.]+", value)[0])
    except:
        return None

# Function: Extract text from uploaded file stream
def extract_text_from_file(file_stream, filename):
    text = ""
    if filename.lower().endswith(".pdf"):
        try:
            with pdfplumber.open(file_stream) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            st.error(f"PDF text extraction failed: {e}")
    elif filename.lower().endswith((".png", ".jpg", ".jpeg")):
        try:
            image = Image.open(file_stream).convert("RGB")
            gray = ImageOps.grayscale(image)
            text = pytesseract.image_to_string(gray)
        except Exception as e:
            st.error(f"Image OCR failed: {e}")
            text = ""
    else:
        st.error("Unsupported file format.")
        text = ""
    return text

# Function: Analyze extracted text for lab values
def analyze_text_for_lab_values(text):
    results = []
    text_low = text.lower()
    for test, rule in LAB_RULES.items():
        pattern = rf"{re.escape(test)}[^0-9]*(\d+\.?\d*)"
        match = re.search(pattern, text_low)
        if match:
            value = float(match.group(1))
            ref_range_match = re.search(rf"{re.escape(test)}.*?\d+\.?\d*.*?(\d+\.?\d*)\s*-\s*(\d+\.?\d*)", text_low)
            if ref_range_match:
                low_ref, high_ref = float(ref_range_match.group(1)), float(ref_range_match.group(2))
                current_low, current_high = low_ref, high_ref
                range_str = f"{low_ref} - {high_ref} {rule['unit']}"
            else:
                current_low, current_high = rule["low"], rule["high"]
                range_str = f"{rule['low']} - {rule['high']} {rule['unit']}"

            status = "Unknown"
            if isinstance(value, (int, float)):
                if value < current_low:
                    status = f"LOW ({value} {rule.get('unit', '')})"
                elif value > current_high:
                    status = f"HIGH ({value} {rule.get('unit', '')})"
                else:
                    status = f"Normal ({value} {rule.get('unit', '')})"
            else:
                status = f"Value: {value}"

            results.append({
                "Test": test.upper(),
                "Value": value,
                "Reference Range": range_str,
                "Status": status,
                "Meaning": rule["meaning"]
            })
    return pd.DataFrame(results) if results else pd.DataFrame(columns=["Test", "Value", "Reference Range", "Status", "Meaning"])

# Function: Summarize results
def summarize_results(df):
    if df is None or df.empty:
        return "⚠ No recognized tests found in this report."
    if 'Status' not in df.columns:
        return "⚠ Analysis did not produce standard status column."
    abnormal = df[df["Status"].str.contains("HIGH|LOW", case=False, na=False)]
    if abnormal.empty:
        return "✅ All analyzed values appear within expected ranges."
    else:
        notes = []
        for _, row in abnormal.iterrows():
            test_name = row.get('Test', 'Unknown Test')
            status_detail = row.get('Status', 'Unknown Status')
            meaning_detail = row.get('Meaning', 'No meaning provided')
            if "HIGH" in status_detail:
                notes.append(f"High {test_name} → {meaning_detail}")
            elif "LOW" in status_detail:
                notes.append(f"Low {test_name} → {meaning_detail}")
        return "⚠ Abnormal findings detected:\n- " + "\n- ".join(notes) if notes else "✅ No major abnormalities detected among analyzed tests."

# Streamlit UI
st.set_page_config(
    page_title="Universal Lab Report Analyzer",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

with st.sidebar:
    st.header("Lab Report Upload")
    uploaded_files = st.file_uploader(
        "Upload PDF or Image Reports",
        accept_multiple_files=True,
        type=['pdf', 'png', 'jpg', 'jpeg']
    )
    st.markdown(
        """
        <small>🔒 Private, local processing. <br>
        ⚠ Demo only — not medical advice.</small>
        """, unsafe_allow_html=True
    )
    analyze_btn = st.button("Analyze Reports", use_container_width=True)

st.title("🩺 Universal Lab Report Analyzer")
st.write("Automatically extracts, normalizes, and analyzes lab values from uploaded medical reports.")

if uploaded_files and analyze_btn:
    for uploaded_file in uploaded_files:
        st.subheader(f"📄 File: {uploaded_file.name}")
        file_stream = io.BytesIO(uploaded_file.read())
        extracted_text = extract_text_from_file(file_stream, uploaded_file.name)
        with st.expander("🔹 Extracted Text (Preview)", expanded=False):
            st.text_area("Extracted Text Preview", value=extracted_text[:1000], height=150)
        results_df = analyze_text_for_lab_values(extracted_text)
        if not results_df.empty:
            st.subheader("🔬 Analysis Results")
            st.dataframe(results_df, use_container_width=True)
            st.subheader("🏁 Summary")
            summary_text = summarize_results(results_df)
            st.info(summary_text)
            abnormal = results_df[results_df["Status"].str.contains("HIGH|LOW", case=False, na=False)]
            if not abnormal.empty:
                st.markdown("#### ⚠ Abnormal Values")
                for _, row in abnormal.iterrows():
                    st.warning(f"{row['Test']}: {row['Status']} — {row['Meaning']}")
        else:
            st.error("No recognized lab values found. Make sure test names match supported rules.")
else:
    st.info("Upload lab report files and click 'Analyze Reports' to begin.")

st.write("---")
st.caption("Demo for educational use only. Extraction accuracy depends on the report format.")
