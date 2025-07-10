import streamlit as st
from PIL import Image
from utils import run_ocr, run_summary, save_to_blob

st.set_page_config(page_title="手書きOCR + GPT要約", layout="centered")
st.title("📝 手書きOCR + GPT要約アプリ")

uploaded_file = st.file_uploader("画像をアップロードしてください", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="アップロードされた画像", use_container_width=True)

    if st.button("OCR実行"):
        st.write("🟡 OCRモデル初期化中...")
        try:
            ocr_result = run_ocr(image)
            st.write("🟢 OCR完了！")
            st.subheader("OCR結果")
            st.text(ocr_result)
        except Exception as e:
            st.error(f"❌ OCR中にエラーが発生しました: {e}")

    if st.button("OCRと要約を実行"):
        try:
            with st.spinner("🔍 OCRで文字を認識中..."):
                st.write("🟡 run_ocr 実行開始")
                ocr_text = run_ocr(image)
                st.write("🟢 run_ocr 完了")
                st.text_area("📄 OCR結果", ocr_text, height=200)

            with st.spinner("✍️ 要約生成中..."):
                st.write("🟡 run_summary 実行開始")
                summary = run_summary(ocr_text)
                st.write("🟢 run_summary 完了")
                st.text_area("📝 要約結果", summary, height=150)

            with st.spinner("☁️ Azureに保存中..."):
                st.write("🟡 save_to_blob 実行中...")
                save_to_blob("ocr_result.txt", ocr_text)
                save_to_blob("summary_result.txt", summary)
                st.success("✅ Azure Blob Storage に保存しました！")

        except Exception as e:
            st.error(f"❌ 処理中にエラーが発生しました: {e}")
