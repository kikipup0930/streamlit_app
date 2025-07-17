import io
import csv
import streamlit as st
from PIL import Image
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
import openai

# 環境変数（secrets.tomlから読み込み）
AZURE_ENDPOINT = st.secrets["AZURE_ENDPOINT"]
AZURE_KEY = st.secrets["AZURE_KEY"]
AZURE_CONTAINER = st.secrets["AZURE_CONTAINER"]
AZURE_CONNECTION_STRING = st.secrets["AZURE_CONNECTION_STRING"]

AZURE_OPENAI_ENDPOINT = st.secrets["AZURE_OPENAI_ENDPOINT"]
AZURE_OPENAI_API_KEY = st.secrets["AZURE_OPENAI_API_KEY"]
AZURE_OPENAI_DEPLOYMENT_NAME = st.secrets["AZURE_OPENAI_DEPLOYMENT_NAME"]
AZURE_OPENAI_API_VERSION = st.secrets["AZURE_OPENAI_API_VERSION"]

# OCR実行（Computer Vision v3.2）
def run_ocr(image: Image.Image) -> str:
    client = ComputerVisionClient(AZURE_ENDPOINT, CognitiveServicesCredentials(AZURE_KEY))
    
    image_stream = io.BytesIO()
    image.save(image_stream, format="PNG")
    image_stream.seek(0)

    read_response = client.read_in_stream(image_stream, raw=True)
    operation_location = read_response.headers["Operation-Location"]
    operation_id = operation_location.split("/")[-1]

    import time
    while True:
        result = client.get_read_result(operation_id)
        if result.status not in ['notStarted', 'running']:
            break
        time.sleep(1)

    if result.status == OperationStatusCodes.succeeded:
        lines = [line.text for page in result.analyze_result.read_results for line in page.lines]
        return "\n".join(lines)
    else:
        return ""

# 要約（Azure OpenAI GPT-3.5）
def summarize_text(text: str) -> str:
    openai.api_type = "azure"
    openai.api_base = AZURE_OPENAI_ENDPOINT
    openai.api_key = AZURE_OPENAI_API_KEY
    openai.api_version = AZURE_OPENAI_API_VERSION

    try:
        response = openai.ChatCompletion.create(
            engine=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "以下の文章を日本語で要約してください。"},
                {"role": "user", "content": text}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"❌ 要約エラー: {str(e)}"

# CSV保存（追記型）
def save_to_azure_blob_csv_append(data: dict, blob_name: str = "ocr_result.csv") -> tuple:
    try:
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(AZURE_CONTAINER)

        try:
            container_client.create_container()
        except ResourceExistsError:
            pass

        blob_client = container_client.get_blob_client(blob_name)

        # 既存CSV取得
        existing_data = []
        if blob_client.exists():
            content = blob_client.download_blob().content_as_text()
            existing_data = list(csv.reader(io.StringIO(content)))

        # 追記
        new_row = [data.get("日付"), data.get("ファイル名"), data.get("OCR結果"), data.get("要約")]
        existing_data.append(new_row)

        # 再アップロード
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(existing_data)
        blob_client.upload_blob(output.getvalue(), overwrite=True)

        return True, "✅ CSVに追記保存しました。"
    except Exception as e:
        return False, f"❌ 保存エラー: {str(e)}"
