import os
import io
import requests
import streamlit as st
import pandas as pd
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI


# ========== OCR ==========
def run_ocr(uploaded_file):
    endpoint = os.getenv("AZURE_ENDPOINT")
    key = os.getenv("AZURE_KEY")

    if not endpoint or not key:
        st.error("❌ Azureのエンドポイントまたはキーが設定されていません。")
        return ""

    endpoint_url = endpoint.rstrip("/") + "/vision/v3.2/ocr"
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/octet-stream",
    }

    image_data = uploaded_file.read()

    try:
        response = requests.post(endpoint_url, headers=headers, data=image_data)
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        st.error("❌ OCRのHTTPエラーが発生しました。")
        # 必要なら詳細表示（本番で隠す場合は削除してOK）
        try:
            st.json(response.json())
        except Exception:
            st.text(response.text)
        raise http_err
    except Exception as e:
        st.error(f"⚠️ 予期しないエラー: {e}")
        raise

    result = response.json()
    return result_to_text(result)


def result_to_text(result_json):
    output_text = ""
    try:
        for region in result_json.get("regions", []):
            for line in region.get("lines", []):
                line_text = " ".join([word["text"] for word in line.get("words", [])])
                output_text += line_text + "\n"
    except Exception as e:
        st.error(f"🔴 OCR結果の解析エラー: {e}")
        return ""
    return output_text.strip()


# ========== 要約 ==========
def summarize_text(text):
    try:
        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        )

        res = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            messages=[
                {"role": "system", "content": "以下のテキストを日本語で簡潔に要約してください。"},
                {"role": "user", "content": text},
            ],
            temperature=0.3,
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"要約中にエラーが発生しました: {e}")
        return "要約できませんでした。"


# ========== 追記保存 (CSV) ==========
def save_to_azure_blob_csv_append(filename, data_dict):
    """
    Azure Blob Storage に CSV 追記保存（pandas 既定の UTF-8 で保存）
    """
    try:
        cs = os.getenv("AZURE_CONNECTION_STRING")
        container = os.getenv("AZURE_CONTAINER")

        bsc = BlobServiceClient.from_connection_string(cs)
        bc = bsc.get_blob_client(container=container, blob=filename)

        new_row = pd.DataFrame([data_dict])

        # 既存CSVを読み込み（あれば）
        try:
            buf = io.BytesIO()
            bc.download_blob().readinto(buf)
            buf.seek(0)
            existing = pd.read_csv(buf)  # 既定: UTF-8
            df = pd.concat([existing, new_row], ignore_index=True)
        except Exception:
            # 初回 or まだCSVがない
            df = new_row

        out = io.BytesIO()
        df.to_csv(out, index=False)  # 既定: UTF-8
        out.seek(0)
        bc.upload_blob(out, overwrite=True)
    except Exception as e:
        st.error(f"CSV保存中にエラーが発生しました: {e}")


# ========== 履歴読み込み ==========
def load_csv_from_blob(filename: str, encoding: str = "utf-8") -> pd.DataFrame:
    """
    Azure Blob Storage 上の CSV を DataFrame で読み込む。
    まず UTF-8 で試し、失敗したら CP932（Shift_JIS）で救済。
    """
    cs = os.getenv("AZURE_CONNECTION_STRING")
    container = os.getenv("AZURE_CONTAINER")

    bsc = BlobServiceClient.from_connection_string(cs)
    bc = bsc.get_blob_client(container=container, blob=filename)

    buf = io.BytesIO()
    bc.download_blob().readinto(buf)
    buf.seek(0)
    try:
        return pd.read_csv(buf, encoding=encoding)
    except Exception:
        buf.seek(0)
        return pd.read_csv(buf, encoding="cp932", errors="replace")
