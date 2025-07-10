import os
import numpy as np
from azure.storage.blob import BlobServiceClient
import openai
import streamlit as st

# 🔐 OpenAIのAPIキーを環境変数から読み込み
openai.api_key = os.getenv("OPENAI_API_KEY")

def run_ocr(image):
    """
    easyocrで画像からテキストを抽出
    """
    import easyocr  # 遅延インポート（初回のみ重いため）
    reader = easyocr.Reader(['ja', 'en'], gpu=False)
    result = reader.readtext(np.array(image), detail=0)
    return "\n".join(result)

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


