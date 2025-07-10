# app.py

import streamlit as st
from PIL import Image
from utils import run_ocr, summarize, save_to_blob

st.set_page_config(page_title="OCR + GPT要約", layout="centered")
st.title("📝 手書きOCR + GPT要約")

uploaded_file = st.file_uploader("画像をアップロードしてください", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="アップロード画像", use_column_width=True)

    if st.button("OCR + 要約を実行"):
        with st.spinner("🔍 Azure OCRを実行中..."):
            ocr_text = run_ocr(image)

        st.subheader("📄 OCR結果")
        st.text(ocr_text)

        with st.spinner("🧠 GPTで要約中..."):
            summary = summarize(ocr_text)

        st.subheader("📝 GPT要約")
        st.text(summary)

        with st.spinner("💾 Azure Blob に保存中..."):
            filename = uploaded_file.name.rsplit(".", 1)[0] + ".txt"
            content = f"OCR結果:\n{ocr_text}\n\n要約:\n{summary}"
            save_to_blob(filename, content)

        st.success("✅ 完了しました！Azureに保存されました。")
