import streamlit as st
from PIL import Image
from utils import run_ocr, summarize_text, save_to_azure_blob_csv_append
from datetime import datetime

st.set_page_config(page_title="OCR & 要約アプリ", layout="centered")
st.title("📄 画像OCR & 要約アプリ（Azure版）")

# セッションステートの初期化
if "ocr_text" not in st.session_state:
    st.session_state.ocr_text = ""
if "summary" not in st.session_state:
    st.session_state.summary = ""

uploaded_file = st.file_uploader("画像をアップロードしてください（手書き・印刷文字）", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="アップロードされた画像", use_column_width=True)

    # OCR実行ボタン
    if st.button("OCR実行"):
        st.session_state.ocr_text = run_ocr(image)
        if st.session_state.ocr_text:
            st.success("✅ OCR結果を取得しました")
        else:
            st.warning("⚠️ OCR結果が取得できませんでした。")

    # OCR結果があれば表示
    if st.session_state.ocr_text:
        st.subheader("OCR結果")
        st.text_area("OCR抽出テキスト", st.session_state.ocr_text, height=200)

        # 要約ボタン
        if st.button("要約する"):
            st.session_state.summary = summarize_text(st.session_state.ocr_text)

        # 要約結果があれば表示
        if st.session_state.summary:
            st.subheader("要約")
            st.write(st.session_state.summary)

            # 保存ボタン
            if st.button("CSVに保存"):
                success, msg = save_to_azure_blob_csv_append({
                    "日付": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "ファイル名": uploaded_file.name,
                    "OCR結果": st.session_state.ocr_text,
                    "要約": st.session_state.summary
                })
                if success:
                    st.success(msg)
                else:
                    st.error(msg)
