# app.py

import streamlit as st
from PIL import Image
from utils import run_ocr, summarize_text

# ページ設定
st.set_page_config(page_title="OCR × ChatGPT 要約アプリ", layout="centered")
st.title("📝 教科書OCR & 要約アプリ")

# セッションステート初期化
if "ocr_text" not in st.session_state:
    st.session_state.ocr_text = ""

if "summary_text" not in st.session_state:
    st.session_state.summary_text = ""

# ファイルアップロード
uploaded_file = st.file_uploader("画像をアップロードしてください", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="アップロード画像", use_container_width=True)

    # OCR実行ボタン
    if st.button("OCR実行"):
        st.session_state.ocr_text = run_ocr(image)
        st.session_state.summary_text = ""  # 要約をリセット

# OCR結果の表示
if st.session_state.ocr_text:
    st.subheader("📄 OCR結果")
    st.text(st.session_state.ocr_text)

    # 要約ボタン
    if st.button("要約する"):
        st.session_state.summary_text = summarize_text(st.session_state.ocr_text)

# 要約結果の表示
if st.session_state.summary_text:
    st.subheader("🧠 要約結果")
    st.text(st.session_state.summary_text)

from utils import save_to_azure_blob_csv

# 要約後に保存
if st.button("CSVで保存"):
    save_message = save_to_azure_blob_csv(
        st.session_state.ocr_text,
        st.session_state.summary_text
    )
    st.success(save_message)

