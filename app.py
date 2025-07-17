# app.py

import streamlit as st
from PIL import Image
from utils import run_ocr, summarize_text, save_to_azure_blob_csv_append

st.set_page_config(page_title="OCR × ChatGPT 要約アプリ", layout="centered")
st.title("📝 教科書OCR & 要約アプリ")

# セッション初期化
if "ocr_text" not in st.session_state:
    st.session_state.ocr_text = ""

if "summary_text" not in st.session_state:
    st.session_state.summary_text = ""

# ファイルアップロード
uploaded_file = st.file_uploader("画像をアップロードしてください", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="アップロード画像", use_container_width=True)

    if st.button("OCR実行"):
        st.session_state.ocr_text = run_ocr(image)
        st.session_state.summary_text = ""  # 前の要約はリセット

# OCR結果の表示と要約ボタン
if st.session_state.ocr_text:
    st.subheader("📄 OCR結果")
    st.text(st.session_state.ocr_text)

    if st.button("要約する"):
        st.session_state.summary_text = summarize_text(st.session_state.ocr_text)

# 要約結果と保存
if st.session_state.summary_text:
    st.subheader("🧠 要約結果")
    st.text(st.session_state.summary_text)

    if uploaded_file is not None and st.button("CSVで保存"):
        save_message = save_to_azure_blob_csv_append(
            ocr_text=st.session_state.ocr_text,
            summary_text=st.session_state.summary_text,
            file_name=uploaded_file.name
        )
        st.success(save_message)

# CSV履歴表示（任意機能）
st.subheader("📋 OCR履歴一覧を見る")
if st.button("履歴を表示"):
    from azure.storage.blob import BlobServiceClient
    import pandas as pd
    from io import StringIO

    try:
        blob_service = BlobServiceClient.from_connection_string(st.secrets["AZURE_CONNECTION_STRING"])
        blob_client = blob_service.get_container_client("ocr-results").get_blob_client("ocr_result.csv")
        csv_data = blob_client.download_blob().readall().decode("utf-8")
        df = pd.read_csv(StringIO(csv_data))
        st.dataframe(df)
    except Exception as e:
        st.error(f"履歴読み込みに失敗しました: {e}")
