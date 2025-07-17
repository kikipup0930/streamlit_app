import streamlit as st
import openai
import pandas as pd
from datetime import datetime
from azure.storage.blob import BlobServiceClient, ContainerClient
from io import StringIO
import requests
import base64

# Azure OCRの設定
AZURE_ENDPOINT = st.secrets["AZURE_ENDPOINT"]
AZURE_KEY = st.secrets["AZURE_KEY"]

# Azure Blobの設定
AZURE_CONTAINER = st.secrets["AZURE_CONTAINER"]
AZURE_CONNECTION_STRING = st.secrets["AZURE_CONNECTION_STRING"]

# Azure OpenAIの設定
AZURE_OPENAI_API_KEY = st.secrets["AZURE_OPENAI_API_KEY"]
AZURE_OPENAI_ENDPOINT = st.secrets["AZURE_OPENAI_ENDPOINT"]
AZURE_OPENAI_DEPLOYMENT_NAME = st.secrets["AZURE_OPENAI_DEPLOYMENT_NAME"]
AZURE_OPENAI_API_VERSION = st.secrets["AZURE_OPENAI_API_VERSION"]

# OCR処理
def run_ocr(image) -> str:
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_KEY,
        "Content-Type": "application/octet-stream"
    }
    params = {"language": "ja", "model-version": "latest"}
    ocr_url = f"{AZURE_ENDPOINT}/computervision/imageanalysis:analyze?api-version=2023-10-01&features=read"

    image_bytes = image.read()

    response = requests.post(ocr_url, headers=headers, params=params, data=image_bytes)
    response.raise_for_status()

    result = response.json()

    try:
        if "readResult" in result:
            pages = result["readResult"].get("pages")
            if pages:
                lines = []
                for page in pages:
                    for line in page.get("lines", []):
                        lines.append(line.get("text", ""))
                return "\n".join(lines).strip()
            return result["readResult"].get("content", "").strip()
        return "OCR結果なし"
    except Exception as e:
        st.error(f"OCR解析エラー: {e}")
        return ""

# 要約処理（Azure OpenAI）
def summarize_text(text: str) -> str:
    url = f"{AZURE_OPENAI_ENDPOINT}openai/deployments/{AZURE_OPENAI_DEPLOYMENT_NAME}/chat/completions?api-version={AZURE_OPENAI_API_VERSION}"
    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_OPENAI_API_KEY
    }
    data = {
        "messages": [
            {"role": "system", "content": "以下の日本語文章を簡潔に要約してください。"},
            {"role": "user", "content": text}
        ],
        "temperature": 0.5
    }

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()

    result = response.json()
    return result["choices"][0]["message"]["content"].strip()

# CSVをAzure Blobに追記保存
def save_to_azure_blob_csv_append(data: dict):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        container_client: ContainerClient = blob_service_client.get_container_client(AZURE_CONTAINER)
        blob_name = "ocr_result.csv"

        if not container_client.exists():
            container_client.create_container()

        blob_client = container_client.get_blob_client(blob=blob_name)

        csv_line = ",".join([f'"{str(data[k]).replace("\"", "\"\"")}"' for k in data]) + "\n"

        # 既存データを取得して追記
        existing_data = ""
        if blob_client.exists():
            existing_data = blob_client.download_blob().readall().decode("utf-8")

        new_data = existing_data + csv_line
        blob_client.upload_blob(new_data, overwrite=True)
    except Exception as e:
        st.error(f"❌ 保存エラー: {e}")

# 履歴一覧の読み込み
def load_csv_from_azure_blob():
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        blob_client = blob_service_client.get_blob_client(container=AZURE_CONTAINER, blob="ocr_result.csv")

        blob_data = blob_client.download_blob().readall().decode("utf-8")
        df = pd.read_csv(StringIO(blob_data))
        return df
    except Exception as e:
        st.error(f"❌ 履歴読み込みエラー: {e}")
        return pd.DataFrame()
