# utils.py

import io
from PIL import Image
import requests
from azure.storage.blob import BlobServiceClient
from openai import OpenAI
import streamlit as st

# 🔐 シークレットの読み込み
AZURE_ENDPOINT = st.secrets["AZURE_ENDPOINT"]
AZURE_KEY = st.secrets["AZURE_KEY"]
AZURE_CONTAINER = st.secrets["AZURE_CONTAINER"]
AZURE_CONNECTION_STRING = st.secrets["AZURE_CONNECTION_STRING"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

# 🔍 Azure OCR 実行関数
def run_ocr(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    img_bytes = buffer.getvalue()

    try:
        response = requests.post(
            url=f"{AZURE_ENDPOINT}/computervision/imageanalysis:analyze?api-version=2023-10-01&features=read",
            headers={
                "Ocp-Apim-Subscription-Key": AZURE_KEY,
                "Content-Type": "application/octet-stream"
            },
            params={"language": "ja", "model-version": "latest"},
            data=img_bytes
        )
        response.raise_for_status()
        result = response.json()

        # 🧪 デバッグ用：APIの全レスポンスを表示（開発時のみ）
        st.subheader("🧪 Azure OCR API レスポンス（開発用）")
        st.json(result)

        # 📄 行ごとの文字列を結合して1つのテキストに
        pages = result.get("readResult", {}).get("pages", [])
        if not pages:
            st.warning("⚠️ OCR結果にページデータが含まれていません。")
            return ""

        lines = pages[0].get("lines", [])
        text = "\n".join([line.get("content", "") for line in lines])
        if not text:
            st.warning("⚠️ OCR結果が空です。画像に文字が含まれていない可能性があります。")
        return text

    except Exception as e:
        st.error(f"❌ OCR実行中にエラーが発生しました: {e}")
        return ""

# 🤖 OpenAI GPT による要約関数
def summarize(text: str) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "以下の日本語のOCRテキストを簡潔に要約してください。"
                },
                {
                    "role": "user",
                    "content": text
                }
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"❌ 要約生成中にエラーが発生しました: {e}")
        return "要約に失敗しました。"


# 💾 Azure Blob Storage に保存する関数
def save_to_blob(filename: str, content: str):
    try:
        blob_service = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        container_client = blob_service.get_container_client(AZURE_CONTAINER)
        blob_client = container_client.get_blob_client(filename)
        blob_client.upload_blob(content.encode("utf-8"), overwrite=True)
    except Exception as e:
        st.error(f"❌ Azure保存中にエラーが発生しました: {e}")
