def run_ocr(image: Image.Image) -> str:
    import io
    import requests
    import streamlit as st

    # 画像を JPEG に変換
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    img_bytes = buffer.getvalue()

    try:
        # Azure OCR API 呼び出し
        response = requests.post(
            url=f"{AZURE_ENDPOINT}/computervision/imageanalysis:analyze?api-version=2023-10-01&features=read",
            headers={
                "Ocp-Apim-Subscription-Key": AZURE_KEY,
                "Content-Type": "application/octet-stream"
            },
            params={"language": "ja", "model-version": "latest"},
            data=img_bytes
        )
        response.raise_for_status()
        result = response.json()

        # 📦 デバッグ用：APIレスポンス構造をそのまま表示（Streamlitに出力）
        st.subheader("🧪 Azure OCR API レスポンス（開発用）")
        st.json(result)

        # 🔍 結果からテキストを抽出（安全に取得）
        text = result.get("readResult", {}).get("content", "")
        if not text:
            st.warning("⚠️ OCR結果が空です。画像に文字が含まれていない可能性があります。")
        return text

    except Exception as e:
        st.error(f"❌ OCR実行中にエラーが発生しました: {e}")
        return ""
