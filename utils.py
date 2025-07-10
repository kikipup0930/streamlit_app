# utils.py

import io
from PIL import Image, ImageOps, ImageFilter
import requests
import streamlit as st

AZURE_ENDPOINT = st.secrets["AZURE_ENDPOINT"]
AZURE_KEY = st.secrets["AZURE_KEY"]

def preprocess_image(image: Image.Image) -> Image.Image:
    # 画像の前処理（グレースケール、ノイズ除去、コントラスト補正）
    image = image.convert("L")
    image = image.filter(ImageFilter.MedianFilter(size=3))
    image = ImageOps.autocontrast(image)
    return image

def run_ocr(image: Image.Image) -> str:
    # 画像を前処理してバイナリに変換
    image = preprocess_image(image)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    img_bytes = buffer.getvalue()

    try:
        # Azure OCR (Image Analysis API v4.0) にリクエスト送信
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

        # エラーハンドリング
        if response.status_code != 200:
            return f"⚠️ APIエラー: {response.status_code}\n{response.text}"

        result = response.json()

        # 読み取り結果の抽出
        text = ""
        for block in result.get("readResult", {}).get("blocks", []):
            for line in block.get("lines", []):
                text += line.get("text", "") + "\n"

        return text

    except Exception as e:
        return f"⚠️ 例外エラー: {str(e)}"
