# utils.py

import io
from PIL import Image, ImageOps, ImageFilter
import requests
from openai import OpenAI
from azure.storage.blob import BlobServiceClient
import streamlit as st

# Secrets
AZURE_ENDPOINT = st.secrets["AZURE_ENDPOINT"]
AZURE_KEY = st.secrets["AZURE_KEY"]
AZURE_CONTAINER = st.secrets["AZURE_CONTAINER"]
AZURE_CONNECTION_STRING = st.secrets["AZURE_CONNECTION_STRING"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

def preprocess_image(image: Image.Image) -> Image.Image:
    image = image.convert("L")  # グレースケール
    image = image.filter(ImageFilter.MedianFilter(size=3))
    image = ImageOps.autocontrast(image)
    return image

def run_ocr(image: Image.Image) -> str:
    image = preprocess_image(image)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
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
        result = response.json()

        # 📋 Azure OCR結果を確認用に表示
        st.subheader("🔍 Azure OCRレスポンス（開発用）")
        st.json(result)

        # 🧠 柔軟な構造対応：pagesがなくてもlines探す
        text_lines = []
        read_result = result.get("readResult", {})
        pages = read_result.get("pages", [])
        
        if pages:
            for page in pages:
                for line in page.get("lines", []):
                    text_lines.append(line.get("content", ""))
        else:
            st.warning("⚠️ 'pages' が見つかりませんでした。構造を確認してください。")

        final_text = "\n".join(text_lines).strip()
        return final_text if final_text else "（OCR結果が空です）"

    except Exception as e:
        st.error(f"❌ OCRエラー: {e}")
        return "（OCR失敗）"


def summarize(text: str) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "以下のOCRテキストを要約してください。"},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"要約エラー: {e}")
        return "要約失敗"

def save_to_blob(filename: str, content: str):
    try:
        blob_service = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        container = blob_service.get_container_client(AZURE_CONTAINER)
        blob = container.get_blob_client(filename)
        blob.upload_blob(content.encode("utf-8"), overwrite=True)
    except Exception as e:
        st.error(f"保存エラー: {e}")
