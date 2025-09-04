import os
import requests
import streamlit as st


def run_ocr(uploaded_file):
    """
    Azure Computer Vision API (v3.2 OCR) を使って画像からテキストを抽出。
    エラーが起きた場合は詳細を表示。
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
            st.json(error_json)  # ← ここが重要：エラー内容を可視化
        except Exception:
            st.text(response.text)
        raise http_err
    except Exception as e:
        st.error(f"⚠️ その他のエラーが発生しました: {e}")
        raise

    result = response.json()
    return result_to_text(result)


def result_to_text(result_json):
    """
    OCRのJSONレスポンスからテキストを抽出して1つの文字列にまとめる。
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
