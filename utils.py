# utils.py

import io
import csv
from datetime import datetime
from io import StringIO
from PIL import Image, ImageOps, ImageFilter
import requests
import streamlit as st
from openai import OpenAI
from azure.storage.blob import BlobServiceClient

# AzureとOpenAIのシークレット
AZURE_ENDPOINT = st.secrets["AZURE_ENDPOINT"]
AZURE_KEY = st.secrets["AZURE_KEY"]
AZURE_STORAGE_CONNECTION_STRING = st.secrets["AZURE_STORAGE_CONNECTION_STRING"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

# OpenAIクライアント（新構文）
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
            params={
                "language": "ja",
                "model-version": "latest"
            },
            data=img_bytes
        )

        if response.status_code != 200:
            return f"⚠️ APIエラー: {response.status_code}\n{response.text}"

        result = response.json()
        text = ""
        for block in result.get("readResult", {}).get("blocks", []):
            for line in block.get("lines", []):
                text += line.get("text", "") + "\n"

        return text

    except Exception as e:
        return f"⚠️ 例外エラー: {str(e)}"

def summarize_text(text: str) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "あなたは日本語に堪能な要約アシスタントです。"},
                {"role": "user", "content": f"以下の文章を読みやすく要約してください：\n{text}"}
            ],
            temperature=0.5,
            max_tokens=600
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ 要約エラー: {str(e)}"

def save_to_azure_blob_csv(ocr_text: str, summary_text: str, container_name="ocr-results") -> str:
    try:
        # Blobサービスに接続
        blob_service_client = BlobServiceClient.from_connection_string(
            AZURE_STORAGE_CONNECTION_STRING
        )
        container_client = blob_service_client.get_container_client(container_name)
        if not container_client.exists():
            container_client.create_container()

        # CSV内容を作成
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["timestamp", "ocr_text", "summary_text"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ocr_text.replace("\n", " "),
            summary_text.replace("\n", " ")
        ])
        csv_data = output.getvalue().encode("utf-8")

        # Blobに保存
        filename = f"ocr_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        blob_client = container_client.get_blob_client(filename)
        blob_client.upload_blob(csv_data, overwrite=True)

        return f"✅ CSVで保存されました: {filename}"

    except Exception as e:
        return f"⚠️ 保存エラー: {str(e)}"
