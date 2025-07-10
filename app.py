import streamlit as st
from PIL import Image
from utils import run_ocr, run_summary, save_to_blob
import io

st.set_page_config(page_title="手書きOCR + GPT要約", layout="centered")
st.title("📝 手書きOCR + GPT要約アプリ")

uploaded_file = st.file_uploader("画像をアップロードしてください", type=["png", "jpg", "jpeg"])

if uploaded_file:
    # ✅ BytesIOにコピーして画像表示にもAPI送信にも使えるようにする
    image_bytes = uploaded_file.read()
    image_stream = io.BytesIO(image_bytes)

    try:
        image = Image.open(image_stream)
        st.image(image, caption="アップロードされた画像", use_container_width=True)
    except Exception as e:
        st.error(f"❌ 画像の読み込みに失敗しました: {e}")

    if st.button("OCRと要約を実行"):
        try:
            with st.spinner("🔍 OCRで文字を認識中..."):
                # OCR実行には再びBytesIOで渡す
                ocr_text = run_ocr(io.BytesIO(image_bytes))
                st.text_area("📄 OCR結果", ocr_text, height=200)

            with st.spinner("✍️ 要約生成中..."):
                summary = run_summary(ocr_text)
                st.text_area("📝 要約結果", summary, height=150)

            with st.spinner("☁️ Azureに保存中..."):
                save_to_blob("ocr_result.txt", ocr_text)
                save_to_blob("summary_result.txt", summary)
                st.success("✅ Azure Blob Storage に保存しました！")

        except Exception as e:
            st.error(f"❌ 処理中にエラーが発生しました: {e}")
