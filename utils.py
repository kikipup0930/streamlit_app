import os
import requests
import streamlit as st


def run_ocr(uploaded_file):
    # 環境変数（secrets.toml から）を取得
    endpoint = os.getenv("AZURE_COMPUTER_VISION_ENDPOINT")
    key = os.getenv("AZURE_COMPUTER_VISION_KEY")

    # エンドポイント・キー未設定のエラー
    if not endpoint or not key:
        st.error("❌ Azureのエンドポイントまたはキーが設定されていません。")
        return ""

    # APIエンドポイントURLを構築（末尾のスラッシュに注意）
    endpoint_url = endpoint.rstrip("/") + "/vision/v3.2/ocr"

    headers = {
        'Ocp-Apim-Subscription-Key': key,
        'Content-Type': 'application/octet-stream'
    }

    image_data = uploaded_file.read()

    # OCR API呼び出し
    try:
        response = requests.post(endpoint_url, headers=headers, data=image_data)
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        st.error("❌ OCR処理中にHTTPエラーが発生しました。設定や画像形式を確認してください。")
        return ""
    except Exception:
        st.error("⚠️ 予期しないエラーが発生しました。")
        return ""

    result = response.json()
    return result_to_text(result)


def result_to_text(result_json):
    """
    Azure OCR API の JSON 結果からテキストを抽出する関数。
    """
    output_text = ""

    try:
        for region in result_json.get("regions", []):
            for line in region.get("lines", []):
                line_text = " ".join([word["text"] for word in line.get("words", [])])
                output_text += line_text + "\n"
    except Exception:
        st.error("🔴 OCR結果の解析中にエラーが発生しました。")
        return ""

    return output_text.strip()
