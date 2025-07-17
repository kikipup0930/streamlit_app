import os
import io
import csv
import openai
import requests
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from PIL import Image
import streamlit as st

# 環境変数の読み込み
AZURE_ENDPOINT = st.secrets["AZURE_ENDPOINT"]
AZURE_KEY = st.secrets["AZURE_KEY"]
AZURE_CONTAINER = st.secrets["AZURE_CONTAINER"]
AZURE_CONNECTION_STRING = st.secrets["AZURE_CONNECTION_STRING"]

AZURE_OPENAI_ENDPOINT = st.secrets["AZURE_OPENAI_ENDPOINT"]
AZURE_OPENAI_API_KEY = st.secrets["AZURE_OPENAI_API_KEY"]
AZURE_OPENAI_DEPLOYMENT_NAME = st.secrets["AZURE_OPENAI_DEPLOYMENT_NAME"]
AZURE_OPENAI_API_VERSION = st.secrets["AZURE_OPENAI_API_VERSION"]

# Azure Computer Vision OCR
def run_ocr(image_file):
    image_data = image_file.read()
    ocr_url = AZURE_ENDPOINT + "computervision/imageanalysis:analyze?api-version=2023-10-01&features=read"
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_KEY,
        "Content-Type": "application/octet-stream"
    }
    response = requests.post(ocr_url, headers=headers, data=image_data)
    response.raise_for_status()
    result = response.json()

    # 読み取り結果を取得
    text = ""
    if "readResult" in result and "blocks" in result["readResult"]:
        for block in result["readResult"]["blocks"]:
            for line in block["lines"]:
                text += line["text"] + "\n"
    elif "readResult" in result and "content" in result["readResult"]:
        text = result["readResult"]["content"]
    else:
        return ""

    return text.strip()

# Azure OpenAIによる要約
def summarize_text(text):
    from openai import AzureOpenAI
    client = AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT
    )

    response = client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT_NAME,
        messages=[
            {"role": "system", "content": "以下の文章を簡潔に日本語で要約してください。"},
            {"role": "user", "content": text}
        ],
        temperature=0.7,
        max_tokens=500
    )

    return response.choices[0].message.content.strip()

# Azure Blob StorageにCSV追記保存
def save_to_azure_blob_csv_append(data_dict):
    csv_filename = "ocr_result.csv"
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(AZURE_CONTAINER)
    if not container_client.exists():
        container_client.create_container()

    # 既存のCSV読み込み
    existing_data = []
    try:
        blob_client = container_client.get_blob_client(csv_filename)
        download_stream = blob_client.download_blob()
        existing_data = list(csv.reader(io.StringIO(download_stream.content_as_text())))
    except Exception:
        pass

    # 新規データを追記
    output = io.StringIO()
    writer = csv.writer(output)
    if not existing_data:
        writer.writerow(data_dict.keys())
    else:
        writer.writerows(existing_data[1:])
    writer.writerow(data_dict.values())

    # 書き戻し
    blob_client = container_client.get_blob_client(csv_filename)
    blob_client.upload_blob(output.getvalue(), overwrite=True)

