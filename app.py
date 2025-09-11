# 手書きノートOCR＋要約による自動復習生成システム
# -------------------------------------------------
# - OCR: Azure Computer Vision
# - 要約: Azure OpenAI
# - 保存: Azure Blob Storage 上の単一CSVに追記
# - UI: 履歴カードにコピー/全文モーダル対応
# - 新機能: 日別学習進捗をグラフで可視化
# -------------------------------------------------

import os
import io
import uuid
import base64
import datetime as dt
import time
import requests
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import List, Dict, Any
from azure.storage.blob import BlobServiceClient, ContentSettings

# =====================
# 設定 (Streamlit Secretsから取得)
# =====================
APP_TITLE = "Study Record"

AZURE_CV_ENDPOINT = st.secrets.get("AZURE_ENDPOINT", "")
AZURE_CV_KEY = st.secrets.get("AZURE_KEY", "")
AZURE_STORAGE_CONNECTION_STRING = st.secrets.get("AZURE_CONNECTION_STRING", "")
AZURE_BLOB_CONTAINER = st.secrets.get("AZURE_CONTAINER", "")

AZURE_OPENAI_ENDPOINT = st.secrets.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_KEY = st.secrets.get("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_DEPLOYMENT = st.secrets.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-35-turbo")
AZURE_OPENAI_API_VERSION = st.secrets.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

# =====================
# データモデル
# =====================
@dataclass
class OcrRecord:
    id: str
    created_at: str
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
# Azure 関数
# =====================
def run_azure_ocr(image_bytes: bytes) -> str:
    """Azure Computer Vision Read API v3.2 を使って OCR"""
    if not AZURE_CV_ENDPOINT or not AZURE_CV_KEY:
        return "(Azure CV 未設定)"
    analyze_url = AZURE_CV_ENDPOINT.rstrip("/") + "/vision/v3.2/read/analyze?language=ja"
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_CV_KEY,
        "Content-Type": "application/octet-stream",
    }
    resp = requests.post(analyze_url, headers=headers, data=image_bytes, timeout=30)
    resp.raise_for_status()
    op_location = resp.headers.get("Operation-Location")
    if not op_location:
        raise RuntimeError("Operation-Location ヘッダがありません。")

    for _ in range(40):
        time.sleep(0.5)
        poll = requests.get(op_location, headers={"Ocp-Apim-Subscription-Key": AZURE_CV_KEY}, timeout=30)
        poll.raise_for_status()
        data = poll.json()
        status = data.get("status")
        if status == "succeeded":
            lines = []
            try:
                for readres in data["analyzeResult"]["readResults"]:
                    for line in readres.get("lines", []):
                        lines.append(line.get("text", ""))
            except Exception:
                pass
            return "\n".join(lines).strip()
        if status == "failed":
            raise RuntimeError(f"OCR が失敗しました: {data}")
    raise TimeoutError("OCR のポーリングがタイムアウトしました。")

def run_azure_summary(text: str) -> str:
    """Azure OpenAI (Chat Completions) で要約"""
    if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_KEY or not AZURE_OPENAI_DEPLOYMENT:
        return "(Azure OpenAI 未設定)"
    url = (AZURE_OPENAI_ENDPOINT.rstrip("/") +
           f"/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions?api-version={AZURE_OPENAI_API_VERSION}")
    headers = {
        "api-key": AZURE_OPENAI_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "messages": [
            {"role": "system", "content": "あなたは有能な日本語アシスタントです。OCR結果を箇条書きで簡潔に要約してください。"},
            {"role": "user", "content": f"次のOCRテキストを要約:\n{text}"}
        ],
        "temperature": 0.2,
        "max_tokens": 400,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return ""

def save_to_blob_csv(record: OcrRecord, blob_name: str = "studyrecord_history.csv") -> None:
    """Azure Blob Storage 上の CSV に追記保存する"""
    if not AZURE_STORAGE_CONNECTION_STRING or not AZURE_BLOB_CONTAINER:
        return

    bsc = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    container = bsc.get_container_client(AZURE_BLOB_CONTAINER)
    try:
        container.create_container()
    except Exception:
        pass

    # 1. 既存CSVをダウンロード
    try:
        blob_client = container.get_blob_client(blob_name)
        stream = blob_client.download_blob()
        existing = pd.read_csv(io.BytesIO(stream.readall()))
    except Exception:
        existing = pd.DataFrame(columns=["id", "created_at", "filename", "text", "summary"])

    # 2. 新しい行を追加
    new_row = {
        "id": record.id,
        "created_at": record.created_at,
        "filename": record.filename,
        "text": record.text,
        "summary": record.summary,
    }
    updated = pd.concat([existing, pd.DataFrame([new_row])], ignore_index=True)

    # 3. 丸ごとアップロード（上書き）
    payload = updated.to_csv(index=False).encode("utf-8-sig")
    content_settings = ContentSettings(content_type="text/csv; charset=utf-8")
    container.upload_blob(
        name=blob_name,
        data=payload,
        overwrite=True,
        content_settings=content_settings,
    )

# =====================
# UI ヘルパ
# =====================
def render_header():
    st.markdown(
        f"<h1 style='margin:0;'>{APP_TITLE}</h1>",
        unsafe_allow_html=True,
    )
    st.divider()

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
    b64 = base64.b64encode(text.encode()).decode()
    copy_js = f"navigator.clipboard.writeText(atob('{b64}'));"
    st.markdown(
        f"<button id='copy-btn-{key}' onclick=\"{copy_js}\">{label}</button>",
        unsafe_allow_html=True,
    )

def render_history(filters: Dict[str, Any]):
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

    if st.session_state.get("_modal"):
        title, content = st.session_state["_modal"]
        st.text_area("内容", content, height=400)
        if st.button("閉じる"):
            st.session_state["_modal"] = None

def render_ocr_tab():
    uploaded = st.file_uploader("画像をアップロード", type=["png", "jpg", "jpeg", "webp"])
    if uploaded is not None:
        st.image(uploaded, caption=uploaded.name, use_column_width=True)
        if st.button("OCR を実行", use_container_width=True):
            image_bytes = uploaded.read()
            text = run_azure_ocr(image_bytes)
            summary = run_azure_summary(text)
            rec = OcrRecord(
                id=str(uuid.uuid4()),
                created_at=_now_iso(),
                filename=uploaded.name,
                text=text,
                summary=summary,
                meta={"size": len(image_bytes)}
            )
            st.session_state.records.insert(0, rec)
            save_to_blob_csv(rec)
    else:
        st.info("まず画像をアップロードしてください。")

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

    return {"view_mode": view_mode, "q": q, "date_from": date_from, "date_to": date_to}

# =====================
# 学習進捗の可視化
# =====================
def render_progress_chart():
    records: List[OcrRecord] = st.session_state.records
    if not records:
        st.info("まだデータがありません。OCRを実行すると進捗が表示されます。")
        return
    
    df = df_from_records(records)
    df["date"] = pd.to_datetime(df["created_at"]).dt.date
    df["summary_len"] = df["summary"].apply(lambda x: len(x) if isinstance(x, str) else 0)

    daily_counts = df.groupby("date").size()
    daily_summary_len = df.groupby("date")["summary_len"].sum()

    fig1, ax1 = plt.subplots()
    daily_counts.plot(kind="bar", ax=ax1, title="日別OCR件数", rot=45)
    st.pyplot(fig1)

    fig2, ax2 = plt.subplots()
    daily_summary_len.plot(kind="bar", ax=ax2, title="日別要約文字数", rot=45)
    st.pyplot(fig2)

# =====================
# メイン
# =====================
def main():
    if "records" not in st.session_state:
        st.session_state.records: List[OcrRecord] = []
    st.set_page_config(page_title=APP_TITLE, page_icon="📝", layout="wide")
    render_header()
    filters = render_sidebar()
    tab_ocr, tab_hist, tab_progress = st.tabs(["OCR", "履歴", "進捗"])
    with tab_ocr:
        render_ocr_tab()
    with tab_hist:
        render_history(filters)
    with tab_progress:
        render_progress_chart()

if __name__ == "__main__":
    main()
