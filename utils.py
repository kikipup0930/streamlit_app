# utils.py

import io
import pandas as pd
from io import StringIO
from datetime import datetime
from PIL import Image, ImageOps, ImageFilter
import requests
import streamlit as st
from openai import OpenAI
from azure.storage.blob import BlobServiceClient

AZURE_ENDPOINT = st.secrets["AZURE_ENDPOINT"]
AZURE_KEY = st.secrets["AZURE_KEY"]
AZURE_CONNECTION_STRING = st.secrets["AZURE_CONNECTION_STRING"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

def preprocess_image(image: Image.Image) -> Image.Image:
    image = image.convert("L")
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

        # ✅ デバッグ用にレスポンス全体を表示
        st.subheader("🔍 Azure OCR レスポンス")
        st.json(result)

        read_result = result.get("readResult", {})

        if "content" in read_result and read_result["content"].strip():
            return read_result["content"].strip()

        if "pages" in read_result:
            lines = []
            for page in read_result["pages"]:
                lines += [line.get("content", "") for line in page.get("lines", [])]
            if lines:
                return "\n".join(lines)

        if "blocks" in read_result:
            return "\n".join([block.get("content", "") for block in read_result["blocks"]])

        st.warning("⚠️ OCR結果が取得できませんでした。")
        return ""

    except Exception as e:
        st.error(f"❌ OCRエラー: {e}")
        return ""

def summarize_text(text: str) -> str:
    try:
        res = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "以下のOCRテキストを簡潔に日本語で要約してください。"},
                {"role": "user", "content": text}
            ]
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"要約失敗: {e}")
        return "要約に失敗しました"

def save_to_azure_blob_csv_append(ocr_text: str, summary_text: str, file_name: str,
                                   container_name="ocr-results", blob_name="ocr_result.csv") -> str:
    try:
        blob_service = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        container = blob_service.get_container_client(container_name)
        if not container.exists():
            container.create_container()

        blob = container.get_blob_client(blob_name)
        new_row = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_name": file_name,
            "ocr_text": ocr_text.replace("\n", " "),
            "summary_text": summary_text.replace("\n", " ")
        }])

        try:
            data = blob.download_blob().readall().decode("utf-8")
            df = pd.read_csv(StringIO(data))
            combined = pd.concat([df, new_row], ignore_index=True)
        except:
            combined = new_row

        buf = StringIO()
        combined.to_csv(buf, index=False)
        blob.upload_blob(buf.getvalue(), overwrite=True)
        return "✅ 保存成功"
    except Exception as e:
        return f"❌ 保存エラー: {e}"
