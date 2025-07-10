# app.py

import streamlit as st
from PIL import Image
from utils import run_ocr, summarize, save_to_blob
import datetime
import re

st.set_page_config(page_title="OCR + 要約", layout="centered")
st.title("📝 OCR + GPT要約 アプリ")

uploaded_file = st.file_uploader("画像をアップロードしてください", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="アップロード画像", use_column_width=True)

    if st.button("OCR + 要約を実行"):
        ocr_text = run_ocr(image)
        st.subheader("📄 OCR結果")
        st.text(ocr_text)

        if ocr_text.strip():
            summary = summarize(ocr_text)
            st.subheader("📝 要約")
            st.text(summary)

            # ファイル名を整形（最大80文字）
            base = re.sub(r"[^\w\-]", "_", uploaded_file.name.rsplit(".", 1)[0])
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{base[:50]}_{timestamp}.txt"

            content = f"OCR結果:\n{ocr_text}\n\n要約:\n{summary}"
            save_to_blob(filename, content)
            st.success("✅ Azureに保存しました")
        else:
            st.warning("⚠️ OCR結果が空です")
