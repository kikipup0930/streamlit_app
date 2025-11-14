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
import math  # 復習間隔の計算で使用
import re    # トピック抽出で使用（既にあれば重複OK）
from dataclasses import dataclass
from typing import List, Dict, Any
from azure.storage.blob import BlobServiceClient, ContentSettings
from ui import inject_global_css, render_header, metric_card
from collections import Counter, defaultdict


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

    def _clean_html(text: str | None) -> str:
        if not text: return ""
        t = re.sub(r"<details.*?</details>", "", text, flags=re.S)
        t = re.sub(r"<div.*?</div>", "", t, flags=re.S)
        t = re.sub(r"```.*?```", "", t, flags=re.S)
        t = re.sub(r"<[^>]+>", "", t)
        return t.strip()

    def _to_html(text: str) -> str:
        if not text: return ""
        esc = html.escape(text)
        lines = [ln.strip() for ln in esc.splitlines() if ln.strip()]
        if any(ln[:1] in ("・","-","•","*") for ln in lines):
            items = []
            for ln in lines:
                items.append(f"<li>{(ln[1:] if ln[:1] in ('・','-','•','*') else ln).strip()}</li>")
            return "<ul>" + "".join(items) + "</ul>"
        return "<p>" + "<br>".join(lines) + "</p>"

    # 引数取り出し
    title    = kwargs.get("title") or "Record"
    meta     = kwargs.get("meta") or ""
    summary  = _clean_html(kwargs.get("summary") or "")
    fulltext = _clean_html(kwargs.get("fulltext") or "")

    # f文字列で使う値はここで生成（←重要）
    title_html   = html.escape(title)
    meta_html    = html.escape(meta)
    summary_html = _to_html(summary)
    full_html    = _to_html(fulltext)

    # 付箋カード（インラインCSS・関数“内側”）
    html_block = f"""
    <div style="background:#FFF7C2;border:1px solid #F3E19A;border-radius:12px;
                padding:16px 18px;box-shadow:0 6px 20px rgba(0,0,0,.08);
                position:relative;margin:8px 0 14px;">
      <div style="position:absolute;top:-12px;left:50%;transform:translateX(-50%) rotate(-2deg);
                  width:120px;height:18px;background:rgba(255,235,130,.95);
                  box-shadow:0 2px 6px rgba(0,0,0,.15);border-radius:2px;"></div>

      <div style="font-weight:700;font-size:1rem;margin:0 0 2px;">{title_html}</div>
      {f'<div style="font-size:.825rem;color:#6b7280;margin:0 0 10px;">{meta_html}</div>' if meta_html else ''}
      {f'<div>{summary_html}</div>' if summary_html else ''}
      {f'<details style="margin-top:10px;"><summary>全文を表示</summary><div style="margin-top:8px;white-space:pre-wrap;">{full_html}</div></details>' if full_html else ''}
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

# =====================
# 復習用ユーティリティ（科目ベース）
# =====================

def get_subject(rec) -> str:
    # OcrRecord(subject: str) なので属性で取得
    try:
        v = getattr(rec, "subject", None)
        if not v and isinstance(rec, dict):
            v = rec.get("subject")
        return (v or "未分類").strip()
    except Exception:
        return "未分類"

# 簡易弱点度（0〜1）
_WEAK_HINT_WORDS = ("わから","不明","注意","課題","難し","苦手")
def _weakness_score(text: str) -> float:
    if not text:
        return 0.3
    score = 0.3 + min(0.3, sum(text.count(k) for k in _WEAK_HINT_WORDS)*0.07)
    if len(text) > 2000:
        score += 0.1
    return float(max(0.0, min(1.0, score)))

# ざっくり日本語トークン（既存のものがあればそれでもOK）
_JA_TOKEN = re.compile(r"[ぁ-んァ-ヶ一-龥A-Za-z0-9]+")
_STOP = set("これ それ あれ ここ そこ 私 僕 あなた です ます する した して いる ある ない こと もの また しかし 一方 に より へ を の と が は で も から まで など ため 例 方 的 そして さらに".split())
def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    toks = [t for t in _JA_TOKEN.findall(text)]
    return [t for t in toks if len(t) > 1 and t not in _STOP]

# 科目内の頻出トピック（弱点度で重み付け）
def collect_topics_for_subject(records: list) -> list[tuple[str, float]]:
    bag = Counter()
    for rec in records:
        summary = getattr(rec, "summary", "") or (rec.get("summary") if isinstance(rec, dict) else "") or ""
        text    = getattr(rec, "text", "")    or (rec.get("text")    if isinstance(rec, dict) else "") or ""
        weak    = _weakness_score(summary + "\n" + text)
        for t in _tokenize(summary + "\n" + text):
            bag[t] += 1.0 + weak
    return bag.most_common(50)

# 学習状態（SM-2簡易）
def _learn_state(rid: str) -> dict:
    st.session_state.setdefault("_learn_state", {})
    return st.session_state["_learn_state"].setdefault(
        rid, {"streak": 0, "ef": 2.5, "interval": 1, "next_due": None, "last": None}
    )

def _update_review(rid: str, quality: int, today: dt.date):
    s = _learn_state(rid)
    ef = s["ef"] + (0.1 - (5-quality)*(0.08+(5-quality)*0.02))
    s["ef"] = max(1.3, min(2.8, ef))
    s["streak"] = 0 if quality < 3 else s["streak"] + 1
    if s["streak"] <= 1: interval = 1
    elif s["streak"] == 2: interval = 2
    else: interval = math.ceil(s["interval"] * s["ef"])
    s["interval"] = interval
    s["next_due"] = today + dt.timedelta(days=interval)
    s["last"] = quality

# かんたん問題生成（○×／穴埋め／短答）
def _make_tf_question(topic: str) -> dict:
    stmt_true  = f"{topic}は今回の学習内容と関連がある。"
    stmt_false = f"{topic}は今回の学習内容と無関係である。"
    is_true = (hash(topic) % 2 == 0)
    return {"type":"TF","q": (stmt_true if is_true else stmt_false), "answer": ("○" if is_true else "×"), "ex": f"本文中で『{topic}』の扱い有無で判断。"}

def _pick_sentence(text: str, topic: str) -> str:
    for ln in text.splitlines():
        if topic in ln and 5 <= len(ln) <= 120:
            return ln.strip()
    return (text[:120] + "…") if text else f"{topic} に関する説明文"

def _make_cloze_question(sentence: str, topic: str) -> dict:
    hint = topic[:1] + ("_" * max(2, len(topic)-1))
    return {"type":"CLOZE","q": f"空欄を埋めよ: {sentence.replace(topic,'____')}",
            "answer": topic, "ex": f"ヒント: {hint}"}

def generate_questions_for_topic(rec, topic: str) -> list[dict]:
    text = (getattr(rec,"summary","") or "") + "\n" + (getattr(rec,"text","") or "")
    qs = []
    qs.append(_make_tf_question(topic))
    sent = _pick_sentence(text, topic)
    if topic in sent:
        qs.append(_make_cloze_question(sent, topic))
    qs.append({"type":"SHORT","q": f"『{topic}』の要点を20〜40文字で説明せよ。","answer": f"{topic}の定義や特徴を本文から要約","ex":"自分の言葉で簡潔に"})
    return qs[:3]

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

        # =============================
        # ① プレビュー画像の位置調整（画像専用カラム）
        # =============================
        img_left, img_center, img_right = st.columns([1.125, 2, 1])

        with img_center:
            st.image(uploaded, caption=uploaded.name, width=350)

        # 余白
        st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)

        # =============================
        # ② 実行ボタンの位置調整（ボタン専用カラム）
        # =============================
        btn_left, btn_center, btn_right = st.columns([2.5, 1, 3])

        with btn_center:
            st.markdown("""
                <style>
                div.stButton > button {
                    font-size: 24px !important;
                    padding: 18px 48px !important;
                    border-radius: 999px !important;
                    background-color: #2563EB !important;
                    color: white !important;
                    border: none !important;
                    box-shadow: 0px 4px 12px rgba(0,0,0,0.25);
                }
                div.stButton > button:hover {
                    background-color: #1D4ED8 !important;
                    transform: scale(1.05);
                }
                </style>
            """, unsafe_allow_html=True)

            if st.button("実行", key="round_big_run"):
                uploaded.seek(0)
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
                    meta={"size": len(image_bytes)},
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
    # セッション初期化
    if "records" not in st.session_state:
        st.session_state.records: List[OcrRecord] = []

    st.set_page_config(page_title=APP_TITLE, layout="wide")
    inject_global_css()
    st.markdown("""
<style>
/* タブのタイトル（未選択） */
div[data-testid="stTabs"] button {
    font-size: 1.15rem !important;     /* 文字サイズUP */
    font-weight: 600 !important;       /* 太字 */
    padding: 10px 18px !important;     /* 余白UP */
    color: #4b5563 !important;         /* 少し濃いグレー */
}

/* タブのタイトル（選択中） */
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #1E3A8A !important;         /* 濃い青 */
    font-size: 1.25rem !important;     /* 選択時さらに大きい */
    font-weight: 700 !important;       /* さらに太字 */
    border-bottom: 3px solid #1E3A8A !important;  /* 強いライン */
}

/* ホバー時に色が少し濃くなる */
div[data-testid="stTabs"] button:hover {
    color: #1d4ed8 !important;
}
/* タブ下の各ページタイトル（OCR / 履歴 / 進捗 / 復習） */
h3 {
    display: inline-block;
    font-size: 1.9rem !important;
    font-weight: 900 !important;
    background: #DBEAFE;      /* 薄い青 */
    color: #1E3A8A;           /* 濃い青 */
    border-radius: 6px;
    margin-top: 8px !important;
    margin-bottom: 18px !important;
}
</style>
""", unsafe_allow_html=True)


    render_header(APP_TITLE)

    # 左サイドバー
    filters = render_sidebar()

    # タブ
    tab_ocr, tab_hist, tab_progress, tab_review = st.tabs(["OCR", "履歴", "進捗", "復習"])

    # --- OCRタブ ---
    with tab_ocr:
        render_ocr_tab()

    # --- 履歴タブ ---
    with tab_hist:
        render_history(filters)

    # --- 進捗タブ ---
    with tab_progress:
        render_progress_chart()

    # --- 復習タブ ---
    with tab_review:
        st.subheader("復習（科目別）")

        records = st.session_state.records
        if not records:
            st.info("まだ履歴がありません。OCRしてからお試しください。")
        else:
            # 1) 科目でグルーピング
            subject_to_records = {}
            for rec in records:
                subj = get_subject(rec)
                subject_to_records.setdefault(subj, []).append(rec)

            subjects = sorted(subject_to_records.keys())
            sel = st.selectbox("科目を選ぶ", subjects, index=0)

            target_recs = subject_to_records.get(sel, [])
            st.caption(f"{sel}：{len(target_recs)}件")

            # 2) 弱点トピック
            topic_list = collect_topics_for_subject(target_recs)
            if not topic_list:
                st.info("この科目のトピックが見つかりません。")
            else:
                st.markdown("### 弱点候補トピック")
                chips = []
                for tok, score in topic_list[:12]:
                    alpha = 0.35 + min(0.65, score/6)
                    chips.append(
                        f'<span style="background:rgba(255,215,0,{alpha});padding:4px 8px;border-radius:999px;margin:4px;display:inline-block;">{tok}</span>'
                    )
                st.markdown("<div>" + "".join(chips) + "</div>", unsafe_allow_html=True)

                # 3) 自動復習問題
                st.markdown("### 復習問題（自動生成）")
                def _created(rec):
                    c = getattr(rec, "created_at", None)
                    try:
                        return dt.datetime.fromisoformat(str(c).replace("Z", ""))
                    except Exception:
                        return dt.datetime.min

                for rec in sorted(target_recs, key=_created, reverse=True)[:3]:
                    title = getattr(rec, "filename", "") or "Record"
                    st.markdown(f"####  {title}")

                    text_all = (getattr(rec, "summary", "") or "") + "\n" + (getattr(rec, "text", "") or "")
                    toks_ranked = [(tok, sc) for tok, sc in topic_list if tok in text_all][:2] or topic_list[:1]

                    for i, (tok, _) in enumerate(toks_ranked):
                        st.markdown(f"**トピック:** {tok}")
                        qs = generate_questions_for_topic(rec, tok)
                        for j, q in enumerate(qs):
                            with st.container(border=True):
                                st.write(f"Q{j+1}（{q['type']}）: {q['q']}")
                                with st.expander("模範解答 / ヒント"):
                                    st.write(q["answer"])
                                    st.caption(q["ex"])

                                rid = (getattr(rec, "id", None) or title)
                                rid = f"{rid}::{tok}"
                                today = dt.datetime.now().date()
                                ca, cb, cc = st.columns(3)
                                with ca:
                                    if st.button("✅ やった", key=f"q_done_{rid}_{i}_{j}"):
                                        _update_review(rid, 4, today); st.experimental_rerun()
                                with cb:
                                    if st.button("👍 易しい", key=f"q_easy_{rid}_{i}_{j}"):
                                        _update_review(rid, 5, today); st.experimental_rerun()
                                with cc:
                                    if st.button("🤔 難しい", key=f"q_hard_{rid}_{i}_{j}"):
                                        _update_review(rid, 2, today); st.experimental_rerun()

if __name__ == "__main__":
    main()


