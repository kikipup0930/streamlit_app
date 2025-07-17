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

# 🔐 Secrets
AZURE_ENDPOINT = st.secrets["AZURE_ENDPOINT"]
AZURE_KEY = st.secrets["AZURE_KEY"]
AZURE_CONTAINER = st.secrets["AZURE_CONTAINER"]
AZURE_CONNECTION_STRING = st.secrets["AZURE_CONNECTION_STRING"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

client = OpenAI(api_key=OPENAI_API_KEY)

# 🔧 OCR前処理
def preprocess_image(image: Image.Image) -> Image.Image:
    image = image.convert("L")
    image = image.filter(ImageFilter.MedianFilter(size=3))
    image = ImageOps.autocontrast(image)
    return image

# 📷 OCR実行（blocks > lines > text 対応）
def run_ocr(image: Image.Image) -> str:
    image = preprocess_image(image)
    buf = io.BytesIO()
    image.save(buf, format="PNG")

    try:
        response = requests.post(
            url=f"{AZURE_ENDPOINT}/computervision/imageanalysis:analyze?api-version=2023-10-01&features=read",
            headers={
                "Ocp-Apim-Subscription-Key": AZURE_KEY,
                "Content-Type": "application/octet-stream"
            },
            params={"language": "ja", "model-version": "latest"},
            data=buf.getvalue()
        )
        result = response.json()

        st.subheader("🔍 OCRレスポンス")
        st.json(result)

        if "readResult" in result:
            rr = result["readResult"]
            # 最も一般的：readResult["blocks"][].lines[].text
            lines = []
            for block in rr.get("blocks", []):
                for line in block.get("lines", []):
                    line_text = line.get("text")
                    if line_text:
                        lines.append(line_text.strip())
            if lines:
                return "\n".join(lines)

            # fallback: content
            if "content" in rr and rr["content"].strip():
                return rr["content"].strip()

        return "⚠️ OCR結果が取得できませんでした。"

    except Exception as e:
        st.error(f"OCRエラー: {e}")
        return ""

# ✍️ GPTによる要約
def summarize_text(text: str) -> str:
    try:
        res = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "以下のOCRテキストを日本語で簡潔に要約してください。"},
                {"role": "user", "content": text}
            ]
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"要約エラー: {e}")
        return "⚠️ 要約に失敗しました。"

# 💾 CSV追記保存（Azure Blob）
import re

def sanitize_filename(name: str) -> str:
    # ファイル名をBlobに適した形式に変換（英数・アンダースコア以外を削除）
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', name)

def save_to_azure_blob_csv_append(ocr_text: str, summary_text: str, file_name: str,
                                   container_name=AZURE_CONTAINER, blob_name="ocr_result.csv") -> str:
    try:
        # ⛑️ セーフなファイル名に変換
        safe_file_name = sanitize_filename(file_name) if file_name else "no_filename"

        blob_service = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        container = blob_service.get_container_client(container_name)
        if not container.exists():
            container.create_container()

        blob = container.get_blob_client(blob_name)

        new_row = pd.DataFrame([{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_name": safe_file_name,
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
