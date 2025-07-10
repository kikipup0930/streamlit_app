import os
import requests
import numpy as np
from azure.storage.blob import BlobServiceClient
import openai
import streamlit as st

# 🔐 OpenAI APIキーを環境変数または secrets から読み込む
openai.api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")

def run_ocr(image):
    """
    Azure Computer Vision API を使ってOCRを実行（日本語対応）
    """
    endpoint = st.secrets["AZURE_CV_ENDPOINT"]
    key = st.secrets["AZURE_CV_KEY"]
    ocr_url = f"{endpoint.rstrip('/')}/vision/v3.2/ocr?language=ja&detectOrientation=true"

    image_bytes = image.getvalue()

    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/octet-stream"
    }

    response = requests.post(ocr_url, headers=headers, data=image_bytes)

    # 🔍 エラーがある場合、詳細ログを表示
    if response.status_code != 200:
        print("🛑 Azure OCR ERROR:", response.text)
        response.raise_for_status()

    analysis = response.json()

    lines = []
    for region in analysis.get("regions", []):
        for line in region.get("lines", []):
            text = "".join([word["text"] for word in line.get("words", [])])
            lines.append(text)

    return "\n".join(lines)

def run_summary(text):
    """
    GPT APIを使用して日本語の文章を要約
    """
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": f"以下の文章を要約してください：\n{text}"}
        ]
    )
    return response.choices[0].message.content.strip()

def save_to_blob(filename, content):
    """
    Azure Blob Storage にテキストを保存
    """
    connect_str = st.secrets["AZURE_STORAGE_CONNECTION_STRING"]
    container_name = "results"

    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    container_client = blob_service_client.get_container_client(container_name)
    blob_client = container_client.get_blob_client(blob=filename)

    blob_client.upload_blob(content.encode("utf-8"), overwrite=True)
