import streamlit as st
from PIL import Image
from utils import run_ocr, summarize_text, save_to_azure_blob_csv_append, load_csv_from_azure_blob
from datetime import datetime
st.set_page_config(page_title="OCR × GPT要約アプリ", layout="centered")
st.title("📷 OCR × GPT要約アプリ")
uploaded_file = st.file_uploader("画像をアップロードしてください", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="アップロード画像", use_column_width=True)

    if st.button("🔍 OCR実行"):
        ocr_text = run_ocr(uploaded_file)
        st.subheader("📄 OCR結果")
        st.write(ocr_text if ocr_text else "（テキストが検出されませんでした）")

        if ocr_text:
            if st.button("🧠 GPT要約"):
                with st.spinner("要約中..."):
                    try:
                        summary = summarize_text(ocr_text)
                        st.subheader("📝 要約")
                        st.write(summary)

                        # CSV保存
                        if st.button("💾 保存"):
                            save_to_azure_blob_csv_append({
                                "日付": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "ファイル名": uploaded_file.name,
                                "OCR結果": ocr_text,
                                "要約": summary
                            })
                            st.success("✅ 保存しました")
                    except Exception as e:
                        st.error(f"❌ 要約エラー: {e}")
        else:
            st.warning("⚠️ OCR結果が空です")

# 履歴表示セクション
st.markdown("---")
st.subheader("📜 OCR履歴一覧")

if st.button("📂 履歴を読み込む"):
    df = load_csv_from_azure_blob()
    if df.empty:
        st.info("履歴が存在しません。")
    else:
        st.dataframe(df, use_container_width=True)