import streamlit as st
import pandas as pd
import io
from PIL import Image, ImageOps

# -----------------------------
# Put your LAB_RULES, normalize_value, analyze_text_for_lab_values, summarize_results, and extract_text_from_file functions here
# -----------------------------
# (Insert your complete lab analysis code blocks above this dashboard UI block)

# ---------- Page & Sidebar ----------
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

# ---------- Main Panel ----------
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
                    st.warning(
                        f"{row['Test']}: {row['Status']} — {row['Meaning']}"
                    )
        else:
            st.error("No recognized lab values found. Make sure test names match supported rules.")
else:
    st.info("Upload lab report files and click 'Analyze Reports' to begin.")

# ---------- Footer/Help ----------
st.write("---")
st.caption("Demo for educational use only. Extraction accuracy depends on the report format.")
