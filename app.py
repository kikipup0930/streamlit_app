# app.py

import streamlit as st
from PIL import Image
from utils import run_ocr, summarize_text

st.set_page_config(page_title="OCR × ChatGPT 要約アプリ", layout="centered")
st.title("📝 教科書OCR & 要約アプリ")

uploaded_file = st.file_uploader("画像をアップロードしてください", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="アップロード画像", use_column_width=True)

    if st.button("OCR実行"):
        ocr_text = run_ocr(image)
        st.subheader("📄 OCR結果")
        st.text(ocr_text if ocr_text.strip() else "⚠️ OCR結果が空です")

        if ocr_text.strip():
            if st.button("要約する"):
                summary = summarize_text(ocr_text)
                st.subheader("🧠 要約結果")
                st.text(summary)
