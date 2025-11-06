# 手書きノートOCR＋要約による自動復習生成システム
# -------------------------------------------------
# - OCR: Azure Computer Vision
# - 要約: Azure OpenAI
# - 保存: Azure Blob Storage 上の単一CSVに追記
# - UI: 要約は常に表示、OCR全文は折りたたみで展開
# - 学習進捗をグラフで可視化
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
from ui import inject_global_css, render_header, metric_card

import re

def _clean_for_card(text: str | None) -> str:
    if not isinstance(text, str) or not text.strip():
        return ""
    t = text

    # よく混ざってくる HTML 断片を丸ごと除去
    t = re.sub(r"<details.*?</details>", "", t, flags=re.S | re.I)
    t = re.sub(r'<div\s+class="sr-sec".*?</div>', "", t, flags=re.S | re.I)
    t = re.sub(r'<div\s+class="box".*?</div>', "", t, flags=re.S | re.I)

    # ``` ～ ``` のコードブロックも消す
    t = re.sub(r"```.*?```", "", t, flags=re.S)

    # もし残りのタグも全部いらないならコメントアウト解除
    # t = re.sub(r"<[^>]+>", "", t)

    # 余分な空白を整理
    lines = [ln.strip() for ln in t.splitlines()]
    t = "\n".join([ln for ln in lines if ln])  # 空行削除
    return t.strip()



# --- fallback for render_history_card (safe & signature-agnostic) ---
try:
    # ui.py 等に本実装がある場合はそちらを優先
    from ui import render_history_card  # 無ければ except に落ちる
except Exception:
    import streamlit as st

import re  # ← ファイルの先頭付近で1回だけでOK（まだなければ追加）

def render_history_card(*args, **kwargs):
    import re, html, streamlit as st

    # --- HTMLタグ削除 ---
    def _clean_html(text: str | None) -> str:
        if not text:
            return ""
        t = re.sub(r"<details.*?</details>", "", text, flags=re.S)
        t = re.sub(r"<div.*?</div>", "", t, flags=re.S)
        t = re.sub(r"```.*?```", "", t, flags=re.S)
        t = re.sub(r"<[^>]+>", "", t)
        return t.strip()

    # --- 付箋カード用CSSを一度だけ注入 ---
    def _inject_note_css_once():
        if st.session_state.get("_note_css_once"):
            return
        st.markdown("""
        <style>
        .note-card {
            background:#FFF7C2;
            border:1px solid #F3E19A;
            border-radius:12px;
            padding:16px 18px;
            box-shadow:0 6px 20px rgba(0,0,0,.08);
            position:relative;
            margin: 8px 0 14px;
        }
        .note-card .note-tape {
            position:absolute;top:-12px;left:50%;
            transform:translateX(-50%) rotate(-2deg);
            width:120px;height:18px;
            background:rgba(255,235,130,.95);
            box-shadow:0 2px 6px rgba(0,0,0,.15);
            border-radius:2px;
        }
        .note-card .note-title{font-weight:700;font-size:1rem;margin:0 0 2px;}
        .note-card .note-meta{font-size:.825rem;color:#6b7280;margin:0 0 10px;}
        .note-card .note-summary ul{margin:0 0 6px 1.2rem;}
        .note-card details{margin-top:10px;}
        .note-card .note-full{margin-top:8px;white-space:pre-wrap;}
        </style>
        """, unsafe_allow_html=True)
        st.session_state["_note_css_once"] = True

    def _to_html(text: str) -> str:
        """テキストをHTMLに整形（箇条書き自動対応）"""
        if not text:
            return ""
        esc = html.escape(text)
        lines = [ln.strip() for ln in esc.splitlines() if ln.strip()]
        if any(ln[:1] in ("・","-","•","*") for ln in lines):
            items = []
            for ln in lines:
                if ln[:1] in ("・","-","•","*"):
                    items.append(f"<li>{ln[1:].strip()}</li>")
                else:
                    items.append(f"<li>{ln}</li>")
            return "<ul>" + "".join(items) + "</ul>"
        return "<p>" + "<br>".join(lines) + "</p>"

    # --- 引数からデータ取得 ---
    title = kwargs.get("title") or "Record"
    meta = kwargs.get("meta") or ""
    summary = _clean_html(kwargs.get("summary") or "")
    fulltext = _clean_html(kwargs.get("fulltext") or "")

    # --- CSS適用 + HTML描画 ---
    _inject_note_css_once()
    title_html   = html.escape(title)
    meta_html    = html.escape(meta)
    summary_html = _to_html(summary)
    full_html    = _to_html(fulltext)

html_block = f"""
<div class="note-card"
     style="background:#FFF7C2;border:1px solid #F3E19A;border-radius:12px;
            padding:16px 18px;box-shadow:0 6px 20px rgba(0,0,0,.08);
            position:relative;margin:8px 0 14px;">
  <div class="note-tape"
       style="position:absolute;top:-12px;left:50%;transform:translateX(-50%) rotate(-2deg);
              width:120px;height:18px;background:rgba(255,235,130,.95);
              box-shadow:0 2px 6px rgba(0,0,0,.15);border-radius:2px;"></div>

  <div class="note-title" style="font-weight:700;font-size:1rem;margin:0 0 2px;">{title_html}</div>
  {f'<div class="note-meta" style="font-size:.825rem;color:#6b7280;margin:0 0 10px;">{meta_html}</div>' if meta_html else ''}
  {f'<div class="note-summary">{summary_html}</div>' if summary_html else ''}
  {f'<details style="margin-top:10px;"><summary>全文を表示</summary><div class="note-full" style="margin-top:8px;white-space:pre-wrap;">{full_html}</div></details>' if full_html else ''}
</div>
"""

    st.markdown(html_block, unsafe_allow_html=True)





# =====================
# 設定 (Streamlit Secretsから取得)
# =====================
APP_TITLE = "StudyRecord"

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
    subject: str
    meta: Dict[str, Any]

# =====================
# ユーティリティ
# =====================
def _now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")

def df_from_records(records: List[OcrRecord]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=["id", "created_at", "filename", "text", "summary", "subject"])
    return pd.DataFrame([{
        "id": r.id,
        "created_at": r.created_at,
        "filename": r.filename,
        "text": r.text,
        "summary": r.summary,
        "subject": r.subject,
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
        existing = pd.DataFrame(columns=["id", "created_at", "filename", "text", "summary", "subject"])

    # 2. 新しい行を追加
    new_row = {
        "id": record.id,
        "created_at": record.created_at,
        "filename": record.filename,
        "text": record.text,
        "summary": record.summary,
        "subject": record.subject,
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

def matches_filters(rec: OcrRecord, q: str, period: str, subject_filter: str) -> bool:
    if q:
        q_lower = q.lower()
        target = f"{rec.filename} {rec.text} {rec.summary}".lower()
        if q_lower not in target:
            return False

    # ★ 日付フィルタ
    if period != "すべて":
        rec_date = dt.date.fromisoformat(rec.created_at[:10])
        today = dt.date.today()
        if period == "直近7日" and rec_date < today - dt.timedelta(days=7):
            return False
        elif period == "直近30日" and rec_date < today - dt.timedelta(days=30):
            return False
        elif period == "今月" and rec_date < today.replace(day=1):
            return False

    # 科目フィルタ
    if subject_filter != "すべて" and rec.subject != subject_filter:
        return False

    return True


def copy_to_clipboard_button(label, text, key):
    b64 = base64.b64encode((text or "").encode()).decode()
    copy_js = f"navigator.clipboard.writeText(atob('{b64}'));"
    st.markdown(f"<button id='copy-btn-{key}' onclick=\"{copy_js}\">{label}</button>", unsafe_allow_html=True)

def render_history(filters: Dict[str, Any]):
    st.markdown("### 履歴")
    records: List[OcrRecord] = st.session_state.records
    filtered = [r for r in records if matches_filters(
        r, filters["q"], filters["period"], filters["subject_filter"]
    )]

    if not filtered:
        st.info("条件に合致する履歴はありません。")
        return

    if filters["view_mode"] == "テーブル":
        df = df_from_records(filtered)
        st.dataframe(df, use_container_width=True)
        return

    # --- カード描画（付箋風固定） ---
    for rec in filtered:
        meta = f"作成日: {rec.created_at} ｜ ID: {rec.id}"
        render_history_card(
            title=rec.filename,
            meta=meta,
            summary=rec.summary,
            fulltext=rec.text,
        )


def render_ocr_tab():
    st.markdown("### OCR")

    # 科目リストの初期化（空配列でselectboxが落ちないようガード）
    if "subjects" not in st.session_state or not st.session_state["subjects"]:
        st.session_state["subjects"] = ["未分類"]

    new_subject = st.text_input("科目を入力（新しい科目も追加可能）")
    if new_subject and new_subject not in st.session_state["subjects"]:
        st.session_state["subjects"].append(new_subject)

    subject = st.selectbox("科目を選択", st.session_state["subjects"], index=0)

    uploaded = st.file_uploader("画像をアップロード", type=["png", "jpg", "jpeg", "webp"])
    if uploaded is not None:
        st.image(uploaded, caption=uploaded.name, use_container_width=True)
        if st.button("実行", use_container_width=True):
            image_bytes = uploaded.read()
            text = run_azure_ocr(image_bytes)
            summary = run_azure_summary(text)
            rec = OcrRecord(
                id=str(uuid.uuid4()),
                created_at=_now_iso(),
                filename=uploaded.name,
                text=text,
                summary=summary,
                subject=subject,
                meta={"size": len(image_bytes)}
            )
            st.session_state.records.insert(0, rec)
            save_to_blob_csv(rec)

def render_sidebar():
    with st.sidebar:
        st.subheader("設定 / Filters")
        view_mode = st.radio("履歴の表示形式", ["テーブル", "カード"], index=0, horizontal=True)
        q = st.text_input("キーワード検索（ファイル名/本文/要約）")

        # ★ 期間プリセット（忘れずに定義！）
        period = st.selectbox("期間フィルタ", ["すべて", "直近7日", "直近30日", "今月"])

        subject_filter = st.selectbox(
            "科目フィルタ",
            ["すべて"] + (st.session_state.get("subjects") or ["未分類"])
        )

    return {
        "view_mode": view_mode,
        "q": q,
        "period": period,            # ← これでエラー消える
        "subject_filter": subject_filter,
    }

# =====================
# 学習進捗の可視化
# =====================
def render_progress_chart():
    records: List[OcrRecord] = st.session_state.records
    if not records:
        st.info("まだデータがありません。OCRを実行すると進捗が表示されます。")
        return

    # ========= 日本語フォント設定 =========
    import matplotlib.font_manager as fm
    font_path = os.path.join(os.path.dirname(__file__), "fonts", "NotoSansJP-Regular.ttf")
    prop = fm.FontProperties(fname=font_path) if os.path.exists(font_path) else None

    def apply_jp_font(ax):
        if not prop:
            return
        # タイトル・軸ラベル
        t = ax.get_title()
        if t:
            ax.set_title(t, fontproperties=prop, fontsize=16)
        xl = ax.get_xlabel()
        if xl:
            ax.set_xlabel(xl, fontproperties=prop, fontsize=12)
        yl = ax.get_ylabel()
        if yl:
            ax.set_ylabel(yl, fontproperties=prop, fontsize=12)
        # 目盛りラベル
        for lab in ax.get_xticklabels() + ax.get_yticklabels():
            lab.set_fontproperties(prop)
            lab.set_fontsize(10)

    # ========= データ準備 =========
    df = df_from_records(records)
    df["date"] = pd.to_datetime(df["created_at"]).dt.date
    df["summary_len"] = df["summary"].apply(lambda x: len(x) if isinstance(x, str) else 0)

    # ========= サマリー（上段） =========
    total_ocr = len(df)
    last7 = df[df["date"] >= (dt.date.today() - dt.timedelta(days=7))]
    recent_ocr = len(last7)

    c1, c2 = st.columns(2)
    with c1: metric_card("総OCR件数", f"{total_ocr} 件")
    with c2: metric_card("直近7日間のOCR件数", f"{recent_ocr} 件")

    st.divider()

    # ========= グラフ描画 =========
    # 1段目：日別OCR件数（ワイド）
    daily_counts = df.groupby("date").size()
    fig1, ax1 = plt.subplots(figsize=(10, 3.8))
    daily_counts.plot(kind="bar", ax=ax1, rot=45, color="#2196F3")
    ax1.set_title("日別OCR件数")
    ax1.set_xlabel("日付")
    ax1.set_ylabel("件数")
    ax1.grid(axis="y", linestyle="--", alpha=0.7)
    apply_jp_font(ax1)
    fig1.tight_layout()
    st.pyplot(fig1, use_container_width=True)
    plt.close(fig1)

    # 2段目：科目別（棒＋円）を横並び
    if "subject" in df.columns and not df["subject"].isna().all():
        subject_counts = df.groupby("subject").size().sort_values(ascending=False)

        col_left, col_right = st.columns(2)

        # 左：科目別OCR件数（棒）
        with col_left:
            fig2, ax2 = plt.subplots(figsize=(6, 4))
            subject_counts.plot(
                kind="bar", ax=ax2, rot=45,
                color=["#FF9800", "#2196F3", "#4CAF50", "#9C27B0", "#E91E63"][: len(subject_counts)]
            )
            ax2.set_title("科目別OCR件数")
            ax2.set_xlabel("科目")
            ax2.set_ylabel("件数")
            ax2.grid(axis="y", linestyle="--", alpha=0.7)
            apply_jp_font(ax2)
            fig2.tight_layout()
            st.pyplot(fig2, use_container_width=True)
            plt.close(fig2)

        # 右：科目別割合（円）
        with col_right:
            fig3, ax3 = plt.subplots(figsize=(6, 4))
            subject_counts.plot(
                kind="pie", ax=ax3, autopct="%1.1f%%", startangle=90,
                colors=["#FF9800", "#2196F3", "#4CAF50", "#9C27B0", "#E91E63"][: len(subject_counts)]
            )
            ax3.set_title("科目別OCR件数（割合）")
            ax3.set_ylabel("")  # yラベルは不要
            # 円グラフのテキスト（科目名・割合）にも日本語フォントを適用
            if prop:
                for t in ax3.texts:
                    t.set_fontproperties(prop)
            apply_jp_font(ax3)  # タイトルも適用
            fig3.tight_layout()
            st.pyplot(fig3, use_container_width=True)
            plt.close(fig3)
    else:
        st.info("科目情報が未設定のため、科目別グラフは表示できません。")





# =====================
# メイン
# =====================
def main():
    if "records" not in st.session_state:
        st.session_state.records: List[OcrRecord] = []
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    inject_global_css() 
    render_header(APP_TITLE)
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
