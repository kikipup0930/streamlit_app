import streamlit as st
from datetime import datetime
from utils import run_ocr, summarize_text, save_to_azure_blob_csv_append

st.set_page_config(page_title="OCR & 要約アプリ", page_icon="🧠")
st.title("📄 OCR × 要約ツール")

uploaded_file = st.file_uploader("アップロード画像", type=["png", "jpg", "jpeg"])

ocr_text = ""
summary = ""

if uploaded_file:
    st.image(uploaded_file, caption="アップロード画像", use_column_width=True)

    if st.button("🧠 OCR実行"):
        try:
            ocr_text = run_ocr(uploaded_file)
            if ocr_text:
                st.success("✅ OCR結果取得成功")
                st.text_area("📘 OCR結果", ocr_text, height=200)
                st.session_state.ocr_text = ocr_text
                st.session_state.uploaded_file_name = uploaded_file.name
            else:
                st.warning("⚠️ OCR結果が取得できませんでした。")
        except Exception as e:
            st.error(f"❌ OCRエラー: {e}")

    if "ocr_text" in st.session_state and st.button("📝 要約する"):
        try:
            summary = summarize_text(st.session_state.ocr_text)
            st.text_area("✏️ 要約結果", summary, height=200)
            st.session_state.summary = summary
        except Exception as e:
            st.error(f"❌ 要約エラー: {e}")

    if "summary" in st.session_state and st.button("💾 保存"):
        try:
            save_to_azure_blob_csv_append({
                "日付": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ファイル名": st.session_state.uploaded_file_name,
                "OCR結果": st.session_state.ocr_text,
                "要約": st.session_state.summary
            })
            st.success("✅ 保存成功")
        except Exception as e:
            st.error(f"❌ 保存エラー: {e}")
