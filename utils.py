# utils.py

import io
from PIL import Image
import requests
from azure.storage.blob import BlobServiceClient
from openai import OpenAI
import streamlit as st

# シークレットから設定を読み込む
AZURE_ENDPOINT = st.secrets["AZURE_ENDPOINT"]
AZURE_KEY = st.secrets["AZURE_KEY"]
AZURE_CONTAINER = st.secrets["AZURE_CONTAINER"]
AZURE_CONNECTION_STRING = st.secrets["AZURE_CONNECTION_STRING"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

# Azure OCR 実行関数
def run_ocr(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    img_bytes = buffer.getvalue()

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
    return result["readResult"]["content"]

# OpenAI GPT 要約関数
def summarize(text: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "以下の日本語の手書き文書を簡潔に要約してください。"},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content.strip()

# Azure Blob に保存する関数
def save_to_blob(filename: str, content: str):
    blob_service = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    container_client = blob_service.get_container_client(AZURE_CONTAINER)
    blob_client = container_client.get_blob_client(filename)
    blob_client.upload_blob(content.encode("utf-8"), overwrite=True)
