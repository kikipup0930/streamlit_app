# utils.py

import io
from PIL import Image, ImageOps, ImageFilter
import requests
import streamlit as st

AZURE_ENDPOINT = st.secrets["AZURE_ENDPOINT"]
AZURE_KEY = st.secrets["AZURE_KEY"]

def preprocess_image(image: Image.Image) -> Image.Image:
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
            params={"language": "ja", "model-version": "latest"},
            data=img_bytes
        )
        result = response.json()

        # 新しい形式に対応（全文content形式）
        read_result = result.get("readResult", {})
        if "content" in read_result:
            return read_result["content"].strip()

        # 旧形式（pages形式）も対応
        pages = read_result.get("pages", [])
        if pages:
            lines = pages[0].get("lines", [])
            return "\n".join([line.get("content", "") for line in lines])

        return ""
    except Exception as e:
        st.error(f"OCRエラー: {e}")
        return ""
