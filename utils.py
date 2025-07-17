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

# シークレットから設定値を取得
AZURE_ENDPOINT = st.secrets["AZURE_ENDPOINT"]
AZURE_KEY = st.secrets["AZURE_KEY"]
AZURE_STORAGE_CONNECTION_STRING = st.secrets["AZURE_CONNECTION_STRING"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

# OpenAIクライアント初期化
client = OpenAI(api_key=OPENAI_API_KEY)

# 画像前処理（白黒化・コントラスト強調）
def preprocess_image(image: Image.Image) -> Image.Image:
    image = image.convert("L")
    image = image.filter(ImageFilter.MedianFilter(size=3))
    image = ImageOps.autocontrast(image)
    return image

# OCR実行（Azure Read APIに対応）
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

        # デバッグ出力（Streamlit上でレスポンスを可視化）
        st.subheader("🔍 Azureレスポンス（デバッグ用）")
        st.json(result)

        read_result = result.get("readResult", {})

        # contentフィールド（簡易テキスト）があればそれを返す
        if "content" in read_result:
            return read_result["content"].strip()

        # pagesフィールド対応（従来構造）
        pages = read_result.get("pages", [])
        if pages:
            lines = pages[0].get("lines", [])
            return "\n".join([line.get("content", "") for line in lines])

        # blocks対応（より詳細な構造）
        blocks = read_result.get("blocks", [])
        if blocks:
            return "\n".join([block.get("content", "") for block in blocks])

        st.warning("⚠️ OCR結果が取得できませんでした。")
        return ""

    except Exception as e:
        st.error(f"❌ OCRエラー: {e}")
        return ""


# GPTによる要約生成
def summarize_text(text: str) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "以下のOCRテキストを読みやすく日本語で要約してください。"},
                {"role": "user", "content": text}
            ],
            temperature=0.5,
            max_tokens=600
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"❌ 要約エラー: {e}")
        return "要約に失敗しました"

# Azure Blob に追記形式でCSV保存
def save_to_azure_blob_csv_append(ocr_text: str, summary_text: str, file_name: str,
                                   container_name="ocr-results", blob_name="ocr_result.csv") -> str:
    try:
        # 接続
        blob_service = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
        container_client = blob_service.get_container_client(container_name)
        if not container_client.exists():
            container_client.create_container()

        blob_client = container_client.get_blob_client(blob_name)

        # 追記対象の新しい行を作成
        new_row = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_name": file_name,
            "ocr_text": ocr_text.replace("\n", " "),
            "summary_text": summary_text.replace("\n", " ")
        }])

        # 既存のCSV読み込み（なければ新規）
        try:
            existing_data = blob_client.download_blob().readall().decode("utf-8")
            existing_df = pd.read_csv(StringIO(existing_data))
            combined_df = pd.concat([existing_df, new_row], ignore_index=True)
        except Exception:
            combined_df = new_row

        # 上書きで保存
        output = StringIO()
        combined_df.to_csv(output, index=False)
        blob_client.upload_blob(output.getvalue(), overwrite=True)

        return "✅ Azure BlobにCSVを追記保存しました"

    except Exception as e:
        return f"❌ 保存エラー: {e}"
