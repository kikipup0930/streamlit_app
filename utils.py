# utils.py

import io
from PIL import Image, ImageOps, ImageFilter
import requests
import streamlit as st
from openai import OpenAI

# Secrets
AZURE_ENDPOINT = st.secrets["AZURE_ENDPOINT"]
AZURE_KEY = st.secrets["AZURE_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

# OpenAI クライアント（v1.x以降対応）
client = OpenAI(api_key=OPENAI_API_KEY)

def preprocess_image(image: Image.Image) -> Image.Image:
    # グレースケール変換 + ノイズ除去 + コントラスト補正
    image = image.convert("L")
    image = image.filter(ImageFilter.MedianFilter(size=3))
    image = ImageOps.autocontrast(image)
    return image

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
            params={
                "language": "ja",
                "model-version": "latest"
            },
            data=img_bytes
        )

        if response.status_code != 200:
            return f"⚠️ APIエラー: {response.status_code}\n{response.text}"

        result = response.json()
        text = ""
        for block in result.get("readResult", {}).get("blocks", []):
            for line in block.get("lines", []):
                text += line.get("text", "") + "\n"

        return text

    except Exception as e:
        return f"⚠️ 例外エラー: {str(e)}"

def summarize_text(text: str) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "あなたは日本語に堪能な要約アシスタントです。"},
                {"role": "user", "content": f"以下の文章を読みやすく要約してください：\n{text}"}
            ],
            temperature=0.5,
            max_tokens=600
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ 要約エラー: {str(e)}"
