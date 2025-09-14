import streamlit as st
import pandas as pd
import io
from PIL import Image, ImageOps
import pdfplumber
import pytesseract
import re

# ---------------- LAB_RULES dictionary ----------------
LAB_RULES = {
    # --- Diabetes / Sugar ---
    "glucose": {"low": 70, "high": 99, "unit": "mg/dL", "meaning": "Diabetes risk if high"},
    "fasting blood sugar": {"low": 74, "high": 106, "unit": "mg/dL", "meaning": "Diabetes risk if high"},
    "postprandial glucose": {"low": 70, "high": 140, "unit": "mg/dL", "meaning": "Elevated after meals indicates diabetes"},
    "hba1c": {"low": 4, "high": 6.4, "unit": "%", "meaning": "Diabetes marker; >6.5% indicates diabetes"},

    # --- CBC (Complete Blood Count) ---
    "hemoglobin": {"low": 12, "high": 16.5, "unit": "g/dL", "meaning": "Low may indicate anemia"},
    "wbc": {"low": 4000, "high": 11000, "unit": "/µL", "meaning": "Abnormal count may indicate infection"},
    "platelets": {"low": 150000, "high": 450000, "unit": "/µL", "meaning": "Low = bleeding risk; High = clotting risk"},
    "rbc": {"low": 4.2, "high": 5.9, "unit": "M/µL", "meaning": "Low = anemia; High = dehydration/polycythemia"},
    "hematocrit": {"low": 36, "high": 50, "unit": "%", "meaning": "Low = anemia; High = dehydration"},
    "mcv": {"low": 80, "high": 100, "unit": "fL", "meaning": "Red cell size; low = microcytic anemia"},
    "mch": {"low": 27, "high": 33, "unit": "pg", "meaning": "Hemoglobin per RBC; low = anemia"},
    "mchc": {"low": 32, "high": 36, "unit": "g/dL", "meaning": "RBC concentration; low = iron deficiency"},
    "esr": {"low": 0, "high": 20, "unit": "mm/hr", "meaning": "High = inflammation/infection"},

    # --- Lipid Profile ---
    "cholesterol": {"low": 0, "high": 200, "unit": "mg/dL", "meaning": "High indicates cardiovascular risk"},
    "ldl": {"low": 0, "high": 100, "unit": "mg/dL", "meaning": "High LDL = bad cholesterol"},
    "hdl": {"low": 40, "high": 60, "unit": "mg/dL", "meaning": "Low HDL increases heart risk"},
    "triglyceride": {"low": 0, "high": 150, "unit": "mg/dL", "meaning": "High indicates metabolic risk"},

    # --- Kidney Function ---
    "creatinine": {"low": 0.6, "high": 1.2, "unit": "mg/dL", "meaning": "High = kidney dysfunction"},
    "urea": {"low": 19, "high": 43, "unit": "mg/dL", "meaning": "Kidney function marker"},
    "uric acid": {"low": 3.4, "high": 7.0, "unit": "mg/dL", "meaning": "High = gout or kidney issue"},
    "bun": {"low": 7, "high": 20, "unit": "mg/dL", "meaning": "Kidney function marker"},

    # --- Liver Function ---
    "sgpt": {"low": 0, "high": 40, "unit": "U/L", "meaning": "High = liver damage"},
    "sgot": {"low": 0, "high": 40, "unit": "U/L", "meaning": "High = liver/muscle damage"},
    "bilirubin": {"low": 0.3, "high": 1.2, "unit": "mg/dL", "meaning": "High = jaundice/liver issue"},
    "alkaline phosphatase": {"low": 44, "high": 147, "unit": "U/L", "meaning": "High = liver/bone disease"},
    "total protein": {"low": 6.0, "high": 8.3, "unit": "g/dL", "meaning": "Low = malnutrition/liver issue"},
    "albumin": {"low": 3.5, "high": 5.5, "unit": "g/dL", "meaning": "Low = malnutrition/liver/kidney disease"},

    # --- Thyroid ---
    "tsh": {"low": 0.4, "high": 4.0, "unit": "µIU/mL", "meaning": "Thyroid disorder if abnormal"},
    "t3": {"low": 80, "high": 200, "unit": "ng/dL", "meaning": "Thyroid hormone"},
    "t4": {"low": 5.0, "high": 12.0, "unit": "µg/dL", "meaning": "Thyroid hormone"},

    # --- Vitamins & Minerals ---
    "vitamin d": {"low": 30, "high": 100, "unit": "ng/mL", "meaning": "Low = Vitamin D deficiency"},
    "vitamin b12": {"low": 187, "high": 833, "unit": "pg/mL", "meaning": "Low = Vitamin B12 deficiency"},
    "calcium": {"low": 8.5, "high": 10.5, "unit": "mg/dL", "meaning": "Abnormal = bone/metabolic issue"},
    "sodium": {"low": 135, "high": 145, "unit": "mmol/L", "meaning": "Electrolyte imbalance if abnormal"},
    "potassium": {"low": 3.5, "high": 5.1, "unit": "mmol/L", "meaning": "Abnormal = heart/muscle issues"},

    # --- Tumor Markers ---
    "psa": {"low": 0, "high": 4, "unit": "ng/mL", "meaning": "Prostate cancer marker"},
    "ca 15-3": {"low": 0, "high": 30, "unit": "U/mL", "meaning": "Breast cancer progression marker"},
    "ca-125": {"low": 0, "high": 35, "unit": "U/mL", "meaning": "Ovarian cancer marker"},
    "cea": {"low": 0, "high": 5, "unit": "ng/mL", "meaning": "Colon cancer marker"},
    "afp": {"low": 0, "high": 10, "unit": "ng/mL", "meaning": "Liver cancer marker"},

    # --- Allergy ---
    "ige": {"low": 0, "high": 87, "unit": "IU/mL", "meaning": "High = allergy or asthma risk"},
}
# ---------------- Normalize Value ----------------
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

# ---------------- Extract full text from all PDF pages ----------------
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
    else:
        st.error("Unsupported file format.")
    return text

# ---------------- Extract all tables from all pages ----------------
def extract_all_tables_from_pdf(file_stream):
    all_tables = []
    try:
        with pdfplumber.open(file_stream) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    df = pd.DataFrame(table)
                    all_tables.append(df)
    except Exception as e:
        st.error(f"Table extraction failed: {e}")
    if all_tables:
        combined_df = pd.concat(all_tables, ignore_index=True)
        return combined_df
    else:
        return pd.DataFrame()

# ---------------- Analyze text for lab values ----------------
def analyze_text_for_lab_values(text):
    results = []
    text_low = text.lower()
    for test, rule in LAB_RULES.items():
        pattern = rf"{re.escape(test)}\s*[:\-]*\s*([\d\.]+)"
        match = re.search(pattern, text_low)
        if match:
            value = float(match.group(1))
            ref_range_match = re.search(
                rf"{re.escape(test)}.*?(\d+\.?\d*)\s*-\s*(\d+\.?\d*)",
                text_low
            )
            if ref_range_match:
                low_ref, high_ref = float(ref_range_match.group(1)), float(ref_range_match.group(2))
                current_low, current_high = low_ref, high_ref
                range_str = f"{low_ref} - {high_ref} {rule['unit']}"
            else:
                current_low, current_high = rule["low"], rule["high"]
                range_str = f"{rule['low']} - {rule['high']} {rule['unit']}"
            if value < current_low:
                status = f"LOW ({value} {rule.get('unit', '')})"
            elif value > current_high:
                status = f"HIGH ({value} {rule.get('unit', '')})"
            else:
                status = f"Normal ({value} {rule.get('unit', '')})"
            results.append({
                "Test": test.upper(),
                "Value": value,
                "Reference Range": range_str,
                "Status": status,
                "Meaning": rule["meaning"]
            })
    return pd.DataFrame(results) if results else pd.DataFrame(columns=["Test", "Value", "Reference Range", "Status", "Meaning"])

# ---------------- Summarize results ----------------
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
        return "⚠ Abnormal findings detected:\n- " + "\n- ".join(notes)

# ---------------- Streamlit dashboard UI ----------------
st.set_page_config(page_title="Universal Lab Report Analyzer", page_icon="🩺", layout="wide", initial_sidebar_state="expanded")

with st.sidebar:
    st.header("Lab Report Upload")
    uploaded_files = st.file_uploader("Upload PDF or Image Reports", accept_multiple_files=True, type=['pdf', 'png', 'jpg', 'jpeg'])
    st.markdown("<small>🔒 Private, local processing. <br>⚠ Demo only — not medical advice.</small>", unsafe_allow_html=True)
    analyze_btn = st.button("Analyze Reports", use_container_width=True)

st.title("🩺 Universal Lab Report Analyzer")
st.write("Automatically extracts, normalizes, and analyzes lab values from uploaded medical reports.")

if uploaded_files and analyze_btn:
    full_text = ""
    all_tables = []

    # First extract all text and tables from all files
    for uploaded_file in uploaded_files:
        file_stream = io.BytesIO(uploaded_file.read())

        # Extract full text
        extracted_text = extract_text_from_file(file_stream, uploaded_file.name)
        full_text += extracted_text + "\n\n"

        # Important: Reset BytesIO stream position before next extraction
        file_stream.seek(0)

        # Extract all tables from this file
        tables_df = extract_all_tables_from_pdf(file_stream)
        if not tables_df.empty:
            all_tables.append(tables_df)

    # Combine all tables into one DataFrame if exists
    if all_tables:
        combined_tables_df = pd.concat(all_tables, ignore_index=True)
        st.subheader("🔢 Combined Extracted Tables")
        st.dataframe(combined_tables_df)
    else:
        st.info("No tables found in the uploaded reports.")

    # Show full extracted text preview
    with st.expander("🔹 Full Extracted Text Preview (All Pages)"):
        st.text_area("Extracted Text", full_text, height=400)

    # Analyze the combined full text
    results_df = analyze_text_for_lab_values(full_text)

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
        st.error("No recognized lab values found in the analyzed reports.")

else:
    st.info("Upload lab report files and click 'Analyze Reports' to begin.")

st.write("---")
st.caption("Demo for educational use only. Extraction accuracy depends on the report format.")
