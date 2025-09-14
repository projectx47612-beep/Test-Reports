# =============================================
# 🩺 Universal Lab Report Analyzer - Merged & Improved (Demo)
# =============================================
# ⚠️ Demo only — not medical advice. Extraction and analysis
#    accuracy depend heavily on report format.


import streamlit as st
import re
import pdfplumber
import pytesseract
import pandas as pd
from PIL import Image, ImageOps
import camelot
import tabula
import io # Import io module for file handling

# -----------------------------
# Expanded Dictionary of Tests
# -----------------------------
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

# ------------------------
# 1. Extract data from PDF/Image
# ------------------------
def extract_text_from_file(file_path, filename):
    """Attempts to extract text from PDF or image."""
    text = ""
    if filename.lower().endswith(".pdf"):
        # Try text extraction first
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print(f"PDF text extraction failed: {e}")

        # If text extraction failed or was sparse, try table extraction then OCR
        if not text.strip():
             print("PDF text extraction failed or returned empty. Trying table extraction...")
             all_tests_from_tables = []
             try:
                 # Try Camelot
                 tables = camelot.read_pdf(file_path, pages="all", flavor="stream", suppress_stdout=True)
                 if tables:
                     for t in tables:
                         df = t.df
                         for _, row in df.iterrows():
                             row_list = row.dropna().astype(str).tolist()
                             if len(row_list) >= 3: # Basic heuristic for Test, Value, Ref
                                all_tests_from_tables.append(row_list)
             except Exception as e:
                 print(f"Camelot failed: {e}")

             if not all_tests_from_tables:
                 print("Table extraction failed. Trying OCR on PDF pages...")
                 try:
                     # Convert PDF pages to images and perform OCR
                     # Note: This requires converting PDF pages to images, which is more complex
                     # and might require external libraries or subprocess calls not directly available here.
                     # As a fallback, we will read the file content and try OCR on the whole file
                     # if it's treated as an image (less reliable for multi-page PDFs).
                     file_path.seek(0) # Reset file pointer
                     image = Image.open(file_path).convert("RGB") # This will likely only read the first page or fail
                     gray = ImageOps.grayscale(image)
                     text = pytesseract.image_to_string(gray)
                 except Exception as e:
                     print(f"PDF to Image/OCR fallback failed: {e}")
             else:
                 # If table extraction worked, concatenate relevant columns to form text
                 text = "\n".join([" ".join(row) for row in all_tests_from_tables])


    elif filename.lower().endswith((".png", ".jpg", ".jpeg")):
        try:
            image = Image.open(file_path).convert("RGB")
            gray = ImageOps.grayscale(image)
            # Simple preprocessing for OCR
            w, h = gray.size
            # Resize small images for better OCR accuracy (unconditionally)
            if w < 1000:
                gray = gray.resize((int(w*1.5), int(h*1.5)), Image.Resampling.LANCZOS)

            text = pytesseract.image_to_string(gray)
        except Exception as e:
            print(f"Image OCR failed: {e}")
            text = ""
    else:
        print("Unsupported file format.")
        text = ""

    return text

# ------------------------
# 2. Normalize numbers
# ------------------------
def normalize_value(value):
    """Extract numeric part, handle units like Lakh."""
    value = str(value).replace(",", "").strip()
    # Handle ranges like "<10" or ">5"
    if value.startswith('<') or value.startswith('>'):
        value = value[1:] # Remove the sign for parsing
    # Handle units like Lakh (assuming it means * 100000)
    if "Lakh" in value or "Lac" in value:
         try:
            num = float(re.findall(r"[\d\.]+", value)[0])
            return num * 100000
         except:
             return None
    # Handle common units in value itself (e.g., 10.5 g/dL)
    match_num_unit = re.match(r"(\d+\.?\d*)\s*([a-zA-Z%/µ]+)?", value)
    if match_num_unit:
        try:
            return float(match_num_unit.group(1))
        except ValueError:
            return None

    # Default: just try to find a number
    try:
        return float(re.findall(r"[\d\.]+", value)[0])
    except:
        return None

# ------------------------
# 3. Analyze Text for Lab Values
# ------------------------
def analyze_text_for_lab_values(text):
    results = []
    text_low = text.lower()

    for test, rule in LAB_RULES.items():
        # Use regex to find test name followed by a number (value)
        # This pattern is a basic attempt and may need refinement
        pattern = rf"{re.escape(test)}[^0-9]*(\d+\.?\d*)"
        match = re.search(pattern, text_low)
        if match:
            value = float(match.group(1))
            # Attempt to find a reference range nearby (heuristic)
            # This is very basic and might not work well for all reports
            ref_range_match = re.search(rf"{re.escape(test)}.*?\d+\.?\d*.*?(\d+\.?\d*)\s*-\s*(\d+\.?\d*)", text_low)
            if ref_range_match:
                low_ref, high_ref = float(ref_range_match.group(1)), float(ref_range_match.group(2))
                # Update rule range if found in text, but keep the default as fallback
                current_low, current_high = low_ref, high_ref
                range_str = f"{low_ref} - {high_ref} {rule['unit']}"
            else:
                current_low, current_high = rule["low"], rule["high"]
                range_str = f"{rule['low']} - {rule['high']} {rule['unit']}"


            status = "Unknown"
            if isinstance(value, (int, float)):
                if value < current_low:
                    status = f"LOW ({value} {rule.get('unit', '')})" # Use .get for safety
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


# -----------------------------
# Final Summary
# -----------------------------
def summarize_results(df):
    if df is None or df.empty:
        return "⚠ No recognized tests found in this report."

    # Ensure Status column exists before filtering
    if 'Status' not in df.columns:
         return "⚠ Analysis did not produce standard status column."

    abnormal = df[df["Status"].str.contains("HIGH|LOW", case=False, na=False)] # Add na=False

    if abnormal.empty:
        return "✅ All analyzed values appear within expected ranges."
    else:
        notes = []
        for _, row in abnormal.iterrows():
            # Ensure columns exist before accessing
            test_name = row.get('Test', 'Unknown Test')
            status_detail = row.get('Status', 'Unknown Status')
            meaning_detail = row.get('Meaning', 'No meaning provided')

            if "HIGH" in status_detail:
                notes.append(f"High {test_name} → {meaning_detail}")
            elif "LOW" in status_detail:
                notes.append(f"Low {test_name} → {meaning_detail}")
            # else: This case is handled by filtering 'abnormal'


        return "⚠ Abnormal findings detected:\n- " + "\n- ".join(notes) if notes else "✅ No major abnormalities detected among analyzed tests."


# -----------------------------
# Run in Colab
# -----------------------------
uploaded = files.upload()

for filename, file_content in uploaded.items():
    print(f"\n📄 Processing file: {filename}\n")

    # Use BytesIO to allow file to be read multiple times
    file_stream = io.BytesIO(file_content)

    # Extract text using the improved function
    extracted_text = extract_text_from_file(file_stream, filename)

    if extracted_text:
        print("🔹 Extracted Text (preview):\n")
        print(extracted_text[:1000])  # preview

        # Analyze the extracted text for lab values
        results_df = analyze_text_for_lab_values(extracted_text)

        if not results_df.empty:
            print("\n🔬 Analysis Results:")
            display(results_df)

            print("\n🏁 Final Summary:")
            print(summarize_results(results_df))
        else:
            print("\n⚠ No recognized lab values found in the extracted text.")
            print("\nHint: Ensure test names match keys in LAB_RULES or refine regex pattern.")

    else:
        print("\n❌ Failed to extract any text from the file.")
