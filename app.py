# app.py

import streamlit as st
from PIL import Image
import datetime
import re
from utils import run_ocr, summarize, save_to_blob

st.set_page_config(page_title="OCR + GPT要約", layout="centered")
st.title("📝 手書きOCR + GPT要約アプリ")

uploaded_file = st.file_uploader("画像をアップロードしてください", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="アップロードされた画像", use_column_width=True)

    if st.button("OCR + 要約を実行"):
        with st.spinner("🔍 Azure OCRを実行中..."):
            ocr_text = run_ocr(image)

        st.subheader("📄 OCR結果")
        st.text(ocr_text if ocr_text else "（テキストが検出されませんでした）")

        if not ocr_text.strip():
            st.warning("⚠️ OCRからテキストが抽出できなかったため、要約と保存はスキップされます。")
        else:
            with st.spinner("🧠 GPTで要約中..."):
                summary = summarize(ocr_text)

            st.subheader("📝 GPT要約")
            st.text(summary)

            with st.spinner("💾 Azure Blob に保存中..."):
                # 🔒 ファイル名を安全かつ短く整形
                basename = uploaded_file.name.rsplit(".", 1)[0]
                basename = re.sub(r"[^\w\-]", "_", basename)  # 記号除去
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{basename[:50]}_{timestamp}.txt"

                # 🔐 保存内容をまとめる
                content = f"OCR結果:\n{ocr_text}\n\n要約:\n{summary}"
                save_to_blob(filename, content)

            st.success("✅ 完了しました！Azureに保存されました。")
