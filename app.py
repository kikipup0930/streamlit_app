# StudyRecord-UI2025 — Streamlit UI 強化版（全文モーダル＋コピー対応）
# -------------------------------------------------
# 履歴カードに以下を追加：
# - 「全文を表示」ボタンでモーダルに展開
# - 「コピー」ボタンで内容をクリップボードへ
# -------------------------------------------------

import io
import os
import uuid
import json
import base64
import datetime as dt
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

import pandas as pd
import streamlit as st

# =====================
# 設定
# =====================
APP_TITLE = "StudyRecord-UI2025"
APP_SUBTITLE = "OCR結果の記録・要約をスマートに可視化"

# Azure設定（Secretsから取得）
AZURE_CV_ENDPOINT = os.getenv("AZURE_CV_ENDPOINT", "")
AZURE_CV_KEY = os.getenv("AZURE_CV_KEY", "")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-35-turbo")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "ocr-results")

# =====================
# データモデル
# =====================
@dataclass
class OcrRecord:
    id: str
    created_at: str  # ISO8601
    filename: str
    text: str
    summary: str
    meta: Dict[str, Any]

# =====================
# ユーティリティ
# =====================
def _now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")

def df_from_records(records: List[OcrRecord]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=["id", "created_at", "filename", "text", "summary"]) 
    return pd.DataFrame([{
        "id": r.id,
        "created_at": r.created_at,
        "filename": r.filename,
        "text": r.text,
        "summary": r.summary,
    } for r in records])

# =====================
# Azure 関数（プレースホルダ）
# =====================
def run_azure_ocr(image_bytes: bytes) -> str:
    return "(OCR実処理省略)"

def run_azure_summary(text: str) -> str:
    return "(要約実処理省略)"

def save_to_blob(record: OcrRecord) -> None:
    pass

def export_csv(records: List[OcrRecord]) -> bytes:
    df = df_from_records(records)
    return df.to_csv(index=False).encode("utf-8-sig")

# =====================
# UI ヘルパ
# =====================
def render_header():
    st.markdown(
        f"""
        <div style="display:flex; align-items:baseline; gap:0.75rem;">
            <h1 style="margin:0;">{APP_TITLE}</h1>
            <span style="opacity:.7;">{APP_SUBTITLE}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

def render_sidebar():
    with st.sidebar:
        st.subheader("設定 / Filters")
        view_mode = st.radio("履歴の表示形式", ["テーブル", "カード"], index=0, horizontal=True)
        q = st.text_input("キーワード検索（ファイル名/本文/要約）")
        col1, col2 = st.columns(2)
        with col1:
            date_from = st.date_input("開始日", value=None)
        with col2:
            date_to = st.date_input("終了日", value=None)
        st.caption("ヒント：空欄なら全期間が対象")

        st.subheader("エクスポート")
        if st.session_state.records:
            csv_bytes = export_csv(st.session_state.records)
            st.download_button(
                label="CSV をダウンロード",
                data=csv_bytes,
                file_name="studyrecord_history.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.write("履歴がありません。OCR 実行後にダウンロードできます。")

    return {"view_mode": view_mode, "q": q, "date_from": date_from, "date_to": date_to}

def matches_filters(rec: OcrRecord, q: str, dfrom, dto) -> bool:
    if q:
        q_lower = q.lower()
        target = f"{rec.filename} {rec.text} {rec.summary}".lower()
        if q_lower not in target:
            return False
    if dfrom and rec.created_at[:10] < dfrom.isoformat():
        return False
    if dto and rec.created_at[:10] > dto.isoformat():
        return False
    return True

def copy_to_clipboard_button(label, text, key):
    # base64 エンコードしたテキストをクリップボードコピー
    b64 = base64.b64encode(text.encode()).decode()
    button_id = f"copy-btn-{key}"
    copy_js = f"navigator.clipboard.writeText(atob('{b64}'));"
    st.markdown(
        f"<button id='{button_id}' onclick=\"{copy_js}\">{label}</button>",
        unsafe_allow_html=True,
    )

def render_history(filters: Dict[str, Any]):
    st.markdown("### 履歴")
    records: List[OcrRecord] = st.session_state.records
    filtered = [r for r in records if matches_filters(r, filters["q"], filters["date_from"], filters["date_to"])]

    if not filtered:
        st.info("条件に合致する履歴はありません。")
        return

    if filters["view_mode"] == "テーブル":
        df = df_from_records(filtered)
        st.dataframe(df, use_container_width=True)
    else:
        for rec in filtered:
            with st.container(border=True):
                st.markdown(f"**{rec.filename}**  ")
                st.caption(f"ID: `{rec.id}` / 作成日: {rec.created_at}")
                col1, col2 = st.columns([1,1])
                with col1:
                    st.markdown("**OCR テキスト**")
                    st.write(rec.text if rec.text else "-")
                    copy_to_clipboard_button("コピー", rec.text, f"text-{rec.id}")
                    if st.button("全文を表示", key=f"expand-text-{rec.id}"):
                        st.session_state["_modal"] = ("OCR テキスト", rec.text)
                with col2:
                    st.markdown("**要約**")
                    st.write(rec.summary if rec.summary else "-")
                    copy_to_clipboard_button("コピー", rec.summary, f"summary-{rec.id}")
                    if st.button("全文を表示", key=f"expand-summary-{rec.id}"):
                        st.session_state["_modal"] = ("要約", rec.summary)

    # モーダル風表示
    if st.session_state.get("_modal"):
        title, content = st.session_state["_modal"]
        st.markdown(f"### {title} 全文")
        st.text_area("内容", content, height=400)
        if st.button("閉じる"):
            st.session_state["_modal"] = None

def render_ocr_tab():
    st.markdown("### OCR 実行")
    uploaded = st.file_uploader("画像をアップロード", type=["png", "jpg", "jpeg", "webp"])
    if uploaded is not None:
        st.image(uploaded, caption=uploaded.name, use_column_width=True)
        if st.button("OCR を実行", use_container_width=True):
            text = run_azure_ocr(uploaded.read())
            summary = run_azure_summary(text)
            rec = OcrRecord(
                id=str(uuid.uuid4()),
                created_at=_now_iso(),
                filename=uploaded.name,
                text=text,
                summary=summary,
                meta={}
            )
            st.session_state.records.insert(0, rec)
    else:
        st.info("まず画像をアップロードしてください。")

# =====================
# メイン
# =====================
def main():
    if "records" not in st.session_state:
        st.session_state.records: List[OcrRecord] = []
    st.set_page_config(page_title=APP_TITLE, page_icon="📝", layout="wide")
    render_header()
    filters = render_sidebar()
    tab_ocr, tab_hist = st.tabs(["🖼️ OCR 実行", "📚 履歴"])
    with tab_ocr:
        render_ocr_tab()
    with tab_hist:
        render_history(filters)

if __name__ == "__main__":
    main()
