import os
import io
import requests
import streamlit as st
import pandas as pd
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI


def run_ocr(uploaded_file):
    """
    Azure Computer Vision OCR v3.2 API を使って画像からテキストを抽出する。
    """
    endpoint = os.getenv("AZURE_COMPUTER_VISION_ENDPOINT")
    key = os.getenv("AZURE_COMPUTER_VISION_KEY")

    if not endpoint or not key:
        st.error("❌ Azureのエンドポイントまたはキーが設定されていません。")
        return ""

    endpoint_url = endpoint.rstrip("/") + "/vision/v3.2/ocr"
    headers = {
        'Ocp-Apim-Subscription-Key': key,
        'Content-Type': 'application/octet-stream'
    }

    image_data = uploaded_file.read()

    try:
        response = requests.post(endpoint_url, headers=headers, data=image_data)
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        st.error("❌ HTTPエラーが発生しました。以下に詳細を表示します。")
        try:
            error_json = response.json()
            st.json(error_json)
        except Exception:
            st.text(response.text)
        raise http_err
    except Exception as e:
        st.error(f"⚠️ その他のエラー: {e}")
        raise

    result = response.json()
    return result_to_text(result)


def result_to_text(result_json):
    """
    OCRのJSONレスポンスからテキストを抽出して結合。
    """
    output_text = ""
    try:
        for region in result_json.get("regions", []):
            for line in region.get("lines", []):
                line_text = " ".join([word["text"] for word in line.get("words", [])])
                output_text += line_text + "\n"
    except Exception as e:
        st.error(f"🔴 OCR結果の解析中にエラーが発生しました: {e}")
        return ""
    return output_text.strip()


def summarize_text(text):
    """
    OpenAI API (Azure経由) を使ってテキストを要約。
    """
    try:
        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version="2023-12-01-preview",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )

        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            messages=[
                {"role": "system", "content": "以下のテキストを簡潔に要約してください。"},
                {"role": "user", "content": text}
            ],
            temperature=0.5
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        st.error(f"要約中にエラーが発生しました: {e}")
        return "要約できませんでした。"


def save_to_azure_blob_csv_append(filename, data_dict):
    """
    Azure Blob Storage 上のCSVファイルに1行データを追記保存する。
    """
    try:
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        container_name = "your-container-name"  # あなたのコンテナ名に合わせて変更

        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)

        new_row = pd.DataFrame([data_dict])

        try:
            stream = io.BytesIO()
            blob_client.download_blob().readinto(stream)
            stream.seek(0)
            existing_df = pd.read_csv(stream)
            updated_df = pd.concat([existing_df, new_row], ignore_index=True)
        except Exception:
            updated_df = new_row

        output_stream = io.BytesIO()
        updated_df.to_csv(output_stream, index=False)
        output_stream.seek(0)
        blob_client.upload_blob(output_stream, overwrite=True)

    except Exception as e:
        st.error(f"CSV保存中にエラーが発生しました: {e}")
