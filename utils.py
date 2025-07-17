import streamlit as st
import openai
import pandas as pd
from datetime import datetime
from azure.storage.blob import BlobServiceClient, ContentSettings
from PIL import Image
import requests
import io

# OCR処理（Azure Computer Vision）
def run_ocr(image: Image.Image) -> str:
    endpoint = st.secrets["AZURE_ENDPOINT"]
    key = st.secrets["AZURE_KEY"]
    ocr_url = f"{endpoint}/computervision/imageanalysis:analyze?api-version=2023-10-01&features=read"

    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/octet-stream"
    }

    image_bytes = io.BytesIO()
    image.save(image_bytes, format="PNG")
    image_bytes.seek(0)

    response = requests.post(ocr_url, headers=headers, data=image_bytes.read())
    result = response.json()

    try:
        if "readResult" in result:
            if "content" in result["readResult"]:
                return result["readResult"]["content"].strip()
            elif "blocks" in result["readResult"]:
                lines = []
                for block in result["readResult"]["blocks"]:
                    for line in block.get("lines", []):
                        lines.append(line["text"])
                return "\n".join(lines).strip()
        return ""
    except Exception:
        return ""

# 要約処理（Azure OpenAI）
def summarize_text(text: str) -> str:
    try:
        openai.api_type = "azure"
        openai.api_base = st.secrets["AZURE_OPENAI_ENDPOINT"]
        openai.api_key = st.secrets["AZURE_OPENAI_API_KEY"]
        openai.api_version = st.secrets["AZURE_OPENAI_API_VERSION"]

        deployment_name = st.secrets["AZURE_OPENAI_DEPLOYMENT_NAME"]

        response = openai.ChatCompletion.create(
            engine=deployment_name,
            messages=[
                {"role": "system", "content": "以下の日本語テキストを簡潔に要約してください。"},
                {"role": "user", "content": text}
            ],
            temperature=0.3,
            max_tokens=500
        )

        return response.choices[0].message["content"].strip()

    except Exception as e:
        return f"❌ 要約エラー: {e}"

# CSV保存（Azure Blob Storageに追記形式で保存）
def save_to_azure_blob_csv_append(data: dict):
    try:
        connection_string = st.secrets["AZURE_CONNECTION_STRING"]
        container_name = st.secrets["AZURE_CONTAINER"]
        blob_name = "ocr_result.csv"

        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)

        try:
            blob_client = container_client.get_blob_client(blob_name)
            download_stream = blob_client.download_blob()
            existing_data = pd.read_csv(io.StringIO(download_stream.readall().decode("utf-8")))
        except:
            existing_data = pd.DataFrame()

        new_data = pd.DataFrame([data])
        combined_data = pd.concat([existing_data, new_data], ignore_index=True)

        csv_buffer = io.StringIO()
        combined_data.to_csv(csv_buffer, index=False)

        blob_client.upload_blob(csv_buffer.getvalue(), overwrite=True, content_settings=ContentSettings(content_type='text/csv'))

        return True, "✅ 保存に成功しました"

    except Exception as e:
        return False, f"❌ 保存エラー: {e}"

