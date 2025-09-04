import streamlit as st
from datetime import datetime
from utils import run_ocr, summarize_text, save_to_azure_blob_csv_append

st.set_page_config(page_title="OCR履歴アプリ", layout="centered")
st.title("📄 OCR履歴アプリ")

uploaded_file = st.file_uploader("画像ファイルをアップロード", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    st.image(uploaded_file, caption="アップロード画像", use_column_width=True)

    with st.spinner("OCRを実行中..."):
        ocr_text = run_ocr(uploaded_file)
    st.success("✅ OCR完了")
    st.subheader("📝 OCR結果")
    st.text(ocr_text)

    with st.spinner("要約を生成中..."):
        summary = summarize_text(ocr_text)
    st.success("✅ 要約完了")
    st.subheader("📄 要約")
    st.text(summary)

    if st.button("💾 Azureに保存"):
        data = {
            "日時": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ファイル名": uploaded_file.name,
            "OCR結果": ocr_text,
            "要約": summary
        }
        save_to_azure_blob_csv_append("ocr_result.csv", data)
        st.success("✅ 保存完了（Azure Blob）")
