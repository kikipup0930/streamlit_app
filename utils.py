import os
import io
import csv
import base64
import streamlit as st
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError
from azure.ai.vision import VisionClient
from azure.ai.vision.models import VisionSource, VisionServiceOptions, ImageAnalysisOptions, ImageAnalysisFeature
import openai
import requests

# Secrets 取得
AZURE_ENDPOINT = st.secrets["AZURE_ENDPOINT"]
AZURE_KEY = st.secrets["AZURE_KEY"]
AZURE_CONTAINER = st.secrets["AZURE_CONTAINER"]
AZURE_CONNECTION_STRING = st.secrets["AZURE_CONNECTION_STRING"]

AZURE_OPENAI_ENDPOINT = st.secrets["AZURE_OPENAI_ENDPOINT"]
AZURE_OPENAI_API_KEY = st.secrets["AZURE_OPENAI_API_KEY"]
AZURE_OPENAI_DEPLOYMENT_NAME = st.secrets["AZURE_OPENAI_DEPLOYMENT_NAME"]
AZURE_OPENAI_API_VERSION = st.secrets["AZURE_OPENAI_API_VERSION"]

# OCR処理（Computer Vision 4.0）
def run_ocr(image_bytes: bytes) -> str:
    service_options = VisionServiceOptions(endpoint=AZURE_ENDPOINT, key=AZURE_KEY)
    vision_source = VisionSource(image_data=image_bytes)
    analysis_options = ImageAnalysisOptions(features=[ImageAnalysisFeature.READ])
    vision_client = VisionClient(service_options)
    result = vision_client.analyze(vision_source, analysis_options)

    result_text = ""

    if result.reason == "Analyzed" and result.read_result:
        # ページ構造優先で処理
        pages = getattr(result.read_result, "pages", None)
        if pages:
            for page in pages:
                for line in page.lines:
                    result_text += line.content + "\n"
        elif result.read_result.content:
            result_text = result.read_result.content
    else:
        raise ValueError("OCR結果が取得できませんでした。")

    return result_text.strip()


# 要約処理（Azure OpenAI GPT-3.5対応）
def summarize_text(text: str) -> str:
    openai.api_type = "azure"
    openai.api_base = AZURE_OPENAI_ENDPOINT
    openai.api_key = AZURE_OPENAI_API_KEY
    openai.api_version = AZURE_OPENAI_API_VERSION

    try:
        response = openai.ChatCompletion.create(
            engine=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "以下の文章を日本語で簡潔に要約してください。"},
                {"role": "user", "content": text}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response["choices"][0]["message"]["content"].strip()
    except openai.error.OpenAIError as e:
        raise RuntimeError(f"要約エラー: {e}")


# CSVをAzure Blob Storageに追記保存
def save_to_azure_blob_csv_append(data: dict, blob_name: str = "ocr_result.csv") -> None:
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(AZURE_CONTAINER)

    # コンテナが無ければ作成
    try:
        container_client.create_container()
    except ResourceExistsError:
        pass

    # Blobが存在するかチェック
    blob_client = container_client.get_blob_client(blob_name)
    existing_data = []

    if blob_client.exists():
        stream = blob_client.download_blob()
        existing_data = list(csv.reader(io.StringIO(stream.content_as_text())))

    # 新しい行を追加
    new_row = [data.get("日付"), data.get("ファイル名"), data.get("OCR結果"), data.get("要約")]
    existing_data.append(new_row)

    # CSVを再構築してアップロード
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(existing_data)
    output.seek(0)

    blob_client.upload_blob(output.getvalue(), overwrite=True)
