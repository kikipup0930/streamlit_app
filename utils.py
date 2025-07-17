import os
import io
import cv2
import base64
import numpy as np
import streamlit as st
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from PIL import Image
import openai
import json
import requests

# ------------------- Azure設定 -------------------
AZURE_STORAGE_CONNECTION_STRING = st.secrets["AZURE_CONNECTION_STRING"]
AZURE_CONTAINER_NAME = "ocr-results"
AZURE_COMPUTER_VISION_ENDPOINT = st.secrets["AZURE_COMPUTER_VISION_ENDPOINT"]
AZURE_COMPUTER_VISION_KEY = st.secrets["AZURE_COMPUTER_VISION_KEY"]

# ------------------- OCR処理 -------------------
def run_ocr(image: Image.Image) -> str:
    try:
        # PIL → OpenCV（前処理用）
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        img_gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        img_eq = cv2.equalizeHist(img_gray)
        _, img_thresh = cv2.threshold(img_eq, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        _, buffer = cv2.imencode(".png", img_thresh)
        img_bytes = io.BytesIO(buffer.tobytes())

        # Azure OCR API呼び出し
        ocr_url = f"{AZURE_COMPUTER_VISION_ENDPOINT}/computervision/imageanalysis:analyze?api-version=2023-10-01&features=read"
        headers = {
            "Ocp-Apim-Subscription-Key": AZURE_COMPUTER_VISION_KEY,
            "Content-Type": "application/octet-stream"
        }
        response = requests.post(ocr_url, headers=headers, data=img_bytes.getvalue())
        result = response.json()

        st.subheader("🔍 Azure OCR レスポンス")
        st.json(result)

        # ---------- 構造別にテキスト抽出 ----------
        if "readResult" in result:
            rr = result["readResult"]
            if "content" in rr:
                return rr["content"]
            elif "blocks" in rr:
                texts = []
                for block in rr["blocks"]:
                    for line in block.get("lines", []):
                        texts.append(line.get("text", ""))
                return "\n".join(texts)
        return "⚠️ OCR結果が取得できませんでした。"
    except Exception as e:
        st.error(f"OCRエラー: {e}")
        return "⚠️ OCRエラーが発生しました。"

# ------------------- GPT要約 -------------------
def summarize_text(text: str) -> str:
    try:
        openai.api_key = st.secrets["OPENAI_API_KEY"]
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "以下のOCRテキストを日本語で簡潔に要約してください。"},
                {"role": "user", "content": text}
            ],
            temperature=0.5,
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        st.error(f"要約エラー: {e}")
        return "⚠️ 要約に失敗しました。"

# ------------------- CSV追記保存 -------------------
def save_to_azure_blob_csv_append(data: dict):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)
        if not container_client.exists():
            container_client.create_container()

        blob_name = "ocr_result.csv"
        blob_client = container_client.get_blob_client(blob_name)

        # 既存CSV取得
        if blob_client.exists():
            existing_data = blob_client.download_blob().readall().decode("utf-8")
        else:
            existing_data = ""

        # 新しい行を追加
        import csv
        import pandas as pd
        from io import StringIO

        # 既存 + 新行をDataFrame化
        df_existing = pd.read_csv(StringIO(existing_data)) if existing_data else pd.DataFrame()
        df_new = pd.DataFrame([data])
        df_merged = pd.concat([df_existing, df_new], ignore_index=True)

        # 上書き保存
        csv_buffer = StringIO()
        df_merged.to_csv(csv_buffer, index=False)
        blob_client.upload_blob(csv_buffer.getvalue(), overwrite=True)
    except Exception as e:
        st.error(f"保存エラー: {e}")
