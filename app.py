import streamlit as st
from PIL import Image
from utils import run_ocr, summarize_text, save_to_azure_blob_csv_append
from datetime import datetime

st.set_page_config(page_title="OCR & 要約アプリ", layout="centered")

st.title("📄 画像OCR & 要約アプリ（Azure版）")

uploaded_file = st.file_uploader("画像をアップロードしてください（手書き・印刷文字）", type=["png", "jpg", "jpeg"])

ocr_text = ""
summary = ""

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="アップロードされた画像", use_column_width=True)

    if st.button("🔍 OCR実行"):
        ocr_text = run_ocr(image)
        if ocr_text:
            st.success("✅ OCR結果を取得しました")
        else:
            st.warning("⚠️ OCR結果が取得できませんでした。")

    if ocr_text:
        st.subheader("📄 OCR結果")
        st.text_area("OCR抽出テキスト", ocr_text, height=200)

        if st.button("🧠 要約する"):
            summary = summarize_text(ocr_text)
            st.subheader("📝 要約")
            st.write(summary)

        if summary:
            if st.button("💾 CSVに保存"):
                success, msg = save_to_azure_blob_csv_append({
                    "日付": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "ファイル名": uploaded_file.name,
                    "OCR結果": ocr_text,
                    "要約": summary
                })
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
