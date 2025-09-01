import os
import requests
import streamlit as st

def run_ocr(uploaded_file):
    # Secretsから環境変数を取得
    endpoint = os.getenv("AZURE_COMPUTER_VISION_ENDPOINT")
    key = os.getenv("AZURE_COMPUTER_VISION_KEY")

    # 入力チェック
    if not endpoint or not key:
        st.error("Azureのエンドポイントまたはキーが設定されていません。secrets.tomlを確認してください。")
        return ""

    # 正しいURLを構築
    endpoint_url = endpoint.rstrip("/") + "/vision/v3.2/ocr"

    headers = {
        'Ocp-Apim-Subscription-Key': key,
        'Content-Type': 'application/octet-stream'
    }

    # アップロード画像読み込み
    image_data = uploaded_file.read()

    try:
        response = requests.post(endpoint_url, headers=headers, data=image_data)
        response.raise_for_status()  # HTTPエラーを検出
    except requests.exceptions.HTTPError as http_err:
        st.error("🔴 HTTPエラーが発生しました。下記の詳細を確認してください。")
        try:
            st.json(response.json())  # Azureからの詳細エラー
        except Exception:
            st.text(response.text)
        raise http_err
    except Exception as e:
        st.error(f"⚠️ その他のエラーが発生しました: {e}")
        raise

    result = response.json()

    # JSONからテキストを抽出
    return result_to_text(result)


def result_to_text(result_json):
    """
    Azure OCR APIのJSON結果をテキストに整形して返す関数
    """
    output_text = ""
    try:
        for region in result_json.get("regions", []):
            for line in region.get("lines", []):
                line_text = " ".join([word["text"] for word in line.get("words", [])])
                output_text += line_text + "\n"
    except Exception as e:
        st.error(f"OCR結果の解析中にエラーが発生しました: {e}")
        return ""

    return output_text.strip()
