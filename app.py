import streamlit as st
from datetime import datetime, date
import pandas as pd

from utils import (
    run_ocr,
    summarize_text,
    save_to_azure_blob_csv_append,
    load_csv_from_blob,  # ← 追加
)

st.set_page_config(page_title="OCR履歴アプリ", layout="wide")

st.title("StudyRecord")

tab_ocr, tab_hist = st.tabs(["OCR", "履歴"])

# ======== タブ1: OCR =========
with tab_ocr:
    st.write("画像をアップロードして、OCRと要約を実行します。")
    uploaded_file = st.file_uploader("画像ファイルを選択してください", type=["png", "jpg", "jpeg"])

    if uploaded_file is not None:
        st.image(uploaded_file, caption="アップロード画像", use_column_width=True)

        with st.spinner("OCRを実行中..."):
            ocr_text = run_ocr(uploaded_file)
        st.success("OCR完了！")
        st.subheader("OCR結果")
        st.text(ocr_text)

        with st.spinner("要約を生成中..."):
            summary = summarize_text(ocr_text)
        st.success("要約完了")
        st.subheader("要約結果")
        st.text(summary)

        if st.button("結果保存"):
            data = {
                "日時": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ファイル名": uploaded_file.name,
                "OCR結果": ocr_text,
                "要約": summary,
            }
            save_to_azure_blob_csv_append("ocr_result.csv", data)
            st.success("保存しました（ocr_result.csv）。")

# ======== タブ2: 履歴一覧 =========
with tab_hist:
    st.subheader("履歴一覧（ocr_result.csv）")

    try:
        df = load_csv_from_blob("ocr_result.csv")  # 既定UTF-8で読んで、だめならCP932救済
    except Exception as e:
        st.info("履歴がまだないか、ファイルを読み込めませんでした。")
        st.caption(f"詳細: {e}")
        st.stop()

    # 日付列の正規化
    if "日時" in df.columns:
        df["_dt"] = pd.to_datetime(df["日時"], errors="coerce")
    else:
        df["_dt"] = pd.NaT

    # フィルタUI
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        keyword = st.text_input("キーワード検索（ファイル名 / OCR結果 / 要約）", "")
    with col2:
        min_date = df["_dt"].dropna().min().date() if df["_dt"].notna().any() else date.today()
        start_date = st.date_input("開始日", value=min_date)
    with col3:
        max_date = df["_dt"].dropna().max().date() if df["_dt"].notna().any() else date.today()
        end_date = st.date_input("終了日", value=max_date)

    # フィルタ適用
    filtered = df.copy()

    # 日付範囲
    if filtered["_dt"].notna().any():
        mask_date = (filtered["_dt"].dt.date >= start_date) & (filtered["_dt"].dt.date <= end_date)
        filtered = filtered[mask_date]

    # キーワード（複数列対象）
    if keyword.strip():
        kw = keyword.strip()
        cols = [c for c in ["ファイル名", "OCR結果", "要約"] if c in filtered.columns]
        if cols:
            mask_kw = pd.Series(False, index=filtered.index)
            for c in cols:
                mask_kw = mask_kw | filtered[c].astype(str).str.contains(kw, case=False, na=False)
            filtered = filtered[mask_kw]

    # 表示
    show_cols = [c for c in ["日時", "ファイル名", "OCR結果", "要約"] if c in filtered.columns]
    st.dataframe(filtered[show_cols] if show_cols else filtered, use_container_width=True, height=480)

    # ダウンロード（画面上のフィルタ結果をDL）
    csv_bytes = filtered[show_cols].to_csv(index=False).encode("utf-8") if show_cols else filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        "↓ この一覧をCSVでダウンロード",
        data=csv_bytes,
        file_name="ocr_result_filtered.csv",
        mime="text/csv",
    )
