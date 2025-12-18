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
from ui import inject_global_css, render_header, metric_card
from collections import Counter, defaultdict
from utils import save_to_azure_blob_csv_append
from utils import (
    run_ocr,
    summarize_text,
    save_to_azure_blob_csv_append,
    load_csv_from_blob,
)
from utils import load_csv_from_blob

def load_records_from_blob(blob_name: str = "studyrecord_history.csv") -> list:
    """Azure Blob 上の CSV を読み込み、OcrRecord のリストにして返す"""

    try:
        df = load_csv_from_blob(blob_name)
    except Exception as e:
        print("[load_records_from_blob] load error:", e)
        return []

    if df is None or df.empty:
        return []

    records = []
    for _, row in df.iterrows():
        try:
            rec = OcrRecord(
                id=row.get("id", ""),
                created_at=row.get("created_at", ""),
                filename=row.get("filename", ""),
                text=row.get("text", ""),
                summary=row.get("summary", ""),
                subject=row.get("subject", "未分類"),
                meta={},  # CSVに保存していないので空dictでOK
            )
            records.append(rec)
        except Exception as e:
            print("[load_records_from_blob] row convert error:", e)

    return records




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

# ===== utils.py が参照する環境変数にも同じ値を渡す =====
import os

os.environ["AZURE_CONNECTION_STRING"] = AZURE_STORAGE_CONNECTION_STRING or ""
os.environ["AZURE_CONTAINER"] = AZURE_BLOB_CONTAINER or ""

os.environ["AZURE_ENDPOINT"] = AZURE_CV_ENDPOINT or ""
os.environ["AZURE_KEY"] = AZURE_CV_KEY or ""

os.environ["AZURE_OPENAI_ENDPOINT"] = st.secrets.get("AZURE_OPENAI_ENDPOINT", "")
os.environ["AZURE_OPENAI_API_KEY"] = st.secrets.get("AZURE_OPENAI_API_KEY", "")
os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"] = st.secrets.get("AZURE_OPENAI_DEPLOYMENT_NAME", "")
os.environ["AZURE_OPENAI_API_VERSION"] = st.secrets.get("AZURE_OPENAI_API_VERSION", "")


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
    
def run_azure_quiz(text: str, subject: str, num_questions: int = 3) -> list[dict]:
    """Azure OpenAI で4択クイズを生成する"""

    import json
    if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_KEY or not AZURE_OPENAI_DEPLOYMENT:
        return []


    if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_KEY or not AZURE_OPENAI_DEPLOYMENT:
        # 設定されてない場合は何も返さない
        return []

    # モデルのエンドポイント（要約と同じ形式）
    url = (
        AZURE_OPENAI_ENDPOINT.rstrip("/")
        + f"/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions"
        + f"?api-version={AZURE_OPENAI_API_VERSION}"
    )
    headers = {
        "api-key": AZURE_OPENAI_KEY,
        "Content-Type": "application/json",
    }

    system_msg = (
        "あなたは高校生向けの日本語の家庭教師です。"
        "与えられたテキストから、内容理解を確認するための4択クイズ問題を作成してください。"
        "すべての出力は必ず JSON 配列形式にしてください。"
        "各要素は {\"q\", \"correct\", \"choices\", \"ex\"} をキーに持ちます。"
        "q: 問題文, correct: 正解の選択肢文字列, choices: 正解を含む4つの選択肢リスト,"
        "ex: 正解の簡単な日本語解説です。"
        "choices の順番はランダムで構いません。"
        "マークダウンや説明文は一切書かず、純粋な JSON だけを返してください。"
    )

    # 長すぎるとき用に一応切っておく
    base_text = text[:4000]

    user_msg = (
        f"科目: {subject}\n"
        f"問題数: {num_questions}\n\n"
        "以下の内容から、高校生向けの4択クイズ問題を作ってください。\n\n"
        f"{base_text}"
    )

    payload = {
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.7,
        "max_tokens": 800,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except Exception as e:
        print("[run_azure_quiz] API error:", e)
        return []

    # コードブロックで返ってきた場合のガード
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        # 先頭の ``` or ```json を削る
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        # 末尾の ``` を削る
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    try:
        raw_questions = json.loads(content)
    except Exception as e:
        print("[run_azure_quiz] JSON parse error:", e)
        print("RAW:", content[:300])
        return []

    # 念のため形式を整える
    questions: list[dict] = []
    for q in raw_questions[:num_questions]:
        question = q.get("q") or q.get("question")
        correct = q.get("correct") or q.get("answer")
        choices = q.get("choices") or []
        ex = q.get("ex") or q.get("explanation") or ""

        if not question or not correct:
            continue

        # 正解が選択肢に含まれていなければ追加
        if correct not in choices:
            choices.append(correct)

        # 重複を削って4つまでにする
        seen = set()
        uniq_choices = []
        for c in choices:
            if c not in seen:
                seen.add(c)
                uniq_choices.append(c)
        uniq_choices = uniq_choices[:4]

        # 4つ未満ならスキップ（ゆるくしたいならここは通してもOK）
        if len(uniq_choices) < 2:
            continue

        questions.append(
            {
                "q": question,
                "correct": correct,
                "choices": uniq_choices,
                "ex": ex,
            }
        )

    return questions


from utils import save_to_azure_blob_csv_append  # ← ファイル先頭で必ず import しておく

def save_to_blob_csv(record: OcrRecord, blob_name: str = "studyrecord_history.csv") -> None:
    """utils.py の関数を使って Azure Blob Storage 上の CSV に追記保存する"""

    row = {
        "id": record.id,
        "created_at": record.created_at,
        "filename": record.filename,
        "text": record.text,
        "summary": record.summary,
        "subject": record.subject,
    }

    try:
        save_to_azure_blob_csv_append(blob_name, row)
    except Exception as e:
        print("[save_to_blob_csv] error:", e)
from utils import save_to_azure_blob_csv_append  # ← ファイル先頭で必ず import しておく

def save_to_blob_csv(record: OcrRecord, blob_name: str = "studyrecord_history.csv") -> None:
    """utils.py の関数を使って Azure Blob Storage 上の CSV に追記保存する"""

    row = {
        "id": record.id,
        "created_at": record.created_at,
        "filename": record.filename,
        "text": record.text,
        "summary": record.summary,
        "subject": record.subject,
    }

    try:
        save_to_azure_blob_csv_append(blob_name, row)
    except Exception as e:
        print("[save_to_blob_csv] error:", e)


# ==== ★ ここから復習クイズ履歴用の関数を追加 ★ ====

def save_quiz_log_to_blob(log: dict, blob_name: str = "studyrecord_quiz_history.csv") -> None:
    """復習クイズ履歴を Azure Blob Storage の CSV に追記保存"""
    row = {
        "created_at": log["created_at"],
        "subject": log["subject"],
        "total": log["total"],
        "answered": log["answered"],
        "correct_count": log["correct_count"],
        "rate": log["rate"],
        "comment": log["comment"],
    }

    try:
        save_to_azure_blob_csv_append(blob_name, row)
    except Exception as e:
        print("[save_quiz_log_to_blob] error:", e)


def load_quiz_history_from_blob(blob_name: str = "studyrecord_quiz_history.csv") -> list[dict]:
    """Azure Blob 上の復習クイズCSVを読み込んで list[dict] で返す"""
    try:
        df = load_csv_from_blob(blob_name)
    except Exception as e:
        print("[load_quiz_history_from_blob] load error:", e)
        return []

    if df is None or df.empty:
        return []

    logs: list[dict] = []
    for _, row in df.iterrows():
        logs.append(
            {
                "created_at": row.get("created_at", ""),
                "subject": row.get("subject", ""),
                "total": int(row.get("total", 0) or 0),
                "answered": int(row.get("answered", 0) or 0),
                "correct_count": int(row.get("correct_count", 0) or 0),
                "rate": float(row.get("rate", 0.0) or 0.0),
                "comment": row.get("comment", ""),
            }
        )
    return logs
# ==== ★ ここまで追加 ★ ====





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
    history_type = filters.get("history_type", "OCR")

    # =========================
    # ① OCRスキャン履歴（カード固定）
    # =========================
    if history_type == "OCR":
        st.markdown("### 履歴（OCR）")

        records: List[OcrRecord] = st.session_state.records
        if not records:
            st.info("まだ履歴がありません。")
            return

        # 新しい順にソート
        records = sorted(records, key=lambda r: r.created_at, reverse=True)

        # フィルタ適用
        filtered = [
            r for r in records
            if matches_filters(r, filters["q"], filters["period"], filters["subject_filter"])
        ]

        if not filtered:
            st.info("条件に合致する履歴はありません。")
            return

        # カードで表示
        for rec in filtered:
            meta = f"科目: {rec.subject} ｜ 作成日: {rec.created_at} ｜ ID: {rec.id}"
            render_history_card(
                title=rec.filename,
                meta=meta,
                summary=rec.summary,
                fulltext=rec.text,
            )
        return


    # =========================
    # ② 復習クイズ履歴
    # =========================
    st.markdown("### 復習クイズ履歴")

    quiz_history = st.session_state.get("quiz_history", [])
    if not quiz_history:
        st.info("復習クイズの履歴はまだありません。")
        return

    # 新しいものから順に表示
    for idx, log in enumerate(reversed(quiz_history)):
        # 1行を「カード本体」と「削除ボタン」の2カラムに分ける
        col_main, col_del = st.columns([10, 1])

        # 左：履歴カード本体
        with col_main:
            html_block = f"""
<div style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:12px;
           padding:16px 20px;margin-bottom:16px;
           box-shadow:0 2px 6px rgba(0,0,0,0.05);">
  <h4 style="margin:0 0 8px 0;">📘 {log['subject']}（復習クイズ）</h4>

  <div style="color:#6B7280;font-size:0.9rem;margin-bottom:6px;">
    実施日：{log['created_at']}
  </div>

  <div style="font-size:0.95rem;margin-bottom:4px;">
    出題数：{log['total']}問 ／ 回答済み：{log['answered']}問
  </div>

  <div style="font-size:0.95rem;margin-bottom:6px;">
    正解数：{log['correct_count']}問（正答率：<b>{log['rate']:.0f}%</b>）
  </div>

  <div style="background:#EEF2FF;padding:10px;border-radius:8px;font-size:0.9rem;">
    <b>コメント：</b> {log['comment']}
  </div>
</div>
"""
            st.markdown(html_block, unsafe_allow_html=True)

        # 右上：削除ボタン（カードの右上っぽい位置）
        with col_del:
            # created_at をキーとして削除対象を特定
            if st.button("✕", key=f"delete_quiz_{log['created_at']}"):
                target_ts = log["created_at"]
                # created_at が同じものを除外した新リストを作る
                st.session_state.quiz_history = [
                    h for h in st.session_state.quiz_history
                    if h["created_at"] != target_ts
                ]
                st.success("この復習履歴を削除しました。")
                st.rerun()




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


def render_review_tab():
    st.markdown("### 復習（科目別）")

    # --- セッション初期化 ---
    if "quiz_questions" not in st.session_state:
        st.session_state.quiz_questions = []
    if "quiz_results" not in st.session_state:
        st.session_state.quiz_results = {}
    if "quiz_history" not in st.session_state:
        st.session_state.quiz_history = []
    if "quiz_saved_flag" not in st.session_state:
        st.session_state.quiz_saved_flag = False

    records: List[OcrRecord] = st.session_state.records
    if not records:
        st.info("まだデータがありません。")
        return

    # 科目一覧
    subjects = sorted({get_subject(r) for r in records})
    subject = st.selectbox(
        "科目を選択",
        subjects,
        key="review_subject_select",
    )

    # 選んだ科目のレコード
    subject_records = [r for r in records if get_subject(r) == subject]
    if not subject_records:
        st.info("この科目の記録がありません。")
        return

    st.caption(f"{subject} の記録件数: {len(subject_records)}件")

    # 問題数
    num_questions = st.slider(
        "出題数",
        min_value=3,
        max_value=10,
        value=3,
        step=1,
        key="quiz_num_questions",
    )

    # --- クイズ生成ボタン ---
    if st.button("クイズ生成"):
        texts = []
        for rec in subject_records:
            s = getattr(rec, "summary", "") or (
                rec.meta.get("summary")
                if hasattr(rec, "meta") and isinstance(rec.meta, dict)
                else ""
            )
            t = getattr(rec, "text", "") or ""
            if s:
                texts.append(s)
            elif t:
                texts.append(t)

        if not texts:
            st.warning("この科目には要約やテキストがありません。")
        else:
            joined = "\n\n".join(texts)
            with st.spinner("問題を生成中..."):
                qs = run_azure_quiz(joined, subject, num_questions=num_questions)

            if not qs:
                st.warning("問題を生成できませんでした。")
            else:
                st.session_state.quiz_questions = qs
                st.session_state.quiz_results = {}
                st.session_state.quiz_saved_flag = False
                st.success("復習問題を生成しました！")

    questions = st.session_state.get("quiz_questions", [])
    if not questions:
        return

    st.write("---")

    # --- 各問題の表示 ---
    for i, q in enumerate(questions):
        st.markdown(f"#### Q{i+1}. {q['q']}")
        choice = st.radio(
            f"Q{i+1} の選択肢を選んでください",
            q["choices"],
            index=None,
            key=f"quiz_choice_{i}",
        )

        res = st.session_state.quiz_results.get(i)
        if res is not None:
            if res["correct"]:
                st.success("正解！")
            else:
                st.error("不正解…")
            if q.get("ex"):
                st.info(f"解説：{q['ex']}")

    # --- まとめて採点 ---
    if st.button("採点"):
        results = {}
        for i, q in enumerate(questions):
            choice = st.session_state.get(f"quiz_choice_{i}")
            if not choice:
                continue
            results[i] = {
                "user_choice": choice,
                "correct": (choice == q["correct"]),
            }
        st.session_state.quiz_results = results

    # --- スコアサマリー & 自動保存 ---
    results = st.session_state.quiz_results
    if results:
        st.write("---")
        total = len(questions)
        answered = len(results)
        correct_count = sum(1 for r in results.values() if r["correct"])
        rate = (correct_count / total) * 100 if total > 0 else 0

        st.markdown(
            f"### 結果まとめ\n"
            f"- 回答済み：**{answered} / {total}問**\n"
            f"- 正解数：**{correct_count}問**\n"
            f"- 正答率：**{rate:.0f}%**"
        )

        # 自動保存（1回だけ）
        if not st.session_state.quiz_saved_flag:
            if rate >= 80:
                comment = "とてもよくできています！理解が定着しています。"
            elif rate >= 60:
                comment = "よい調子です。もう少し復習するとさらに良くなります！"
            else:
                comment = "難しかったかもしれません。間違えた問題を中心に復習しましょう。"

            log = {
                "created_at": _now_iso(),
                "subject": subject,
                "total": total,
                "answered": answered,
                "correct_count": correct_count,
                "rate": rate,
                "comment": comment,
            }

            hist = st.session_state.get("quiz_history", [])
            hist.append(log)
            st.session_state.quiz_history = hist
            st.session_state.quiz_saved_flag = True

            # ★ 復習履歴CSVにも保存
            save_quiz_log_to_blob(log)

        if answered < total:
            st.caption("※ まだ解いていない問題があります。全部解くとより正確に実力がわかります。")
        else:
            if rate == 100:
                st.success("すごい！全問正解です👏 この単元はかなり仕上がっています。")
            elif rate >= 70:
                st.info("いい感じです！あと少し復習すれば完璧が狙えます💪")
            elif rate >= 40:
                st.warning("半分くらいは取れています。間違えた問題を中心にもう一度見直してみましょう。")
            else:
                st.error("今回はちょっと難しかったかも…。解説を読みながら、ゆっくり復習してみましょう。")







def render_ocr_tab():
    st.markdown("### OCR")

    # 科目リストの初期化（空配列でselectboxが落ちないようガード）
    if "subjects" not in st.session_state or not st.session_state["subjects"]:
        st.session_state["subjects"] = ["未分類"]

    # 新しい科目の追加
    new_subject = st.text_input("科目を入力（新しい科目も追加可能）")
    if new_subject and new_subject not in st.session_state["subjects"]:
        st.session_state["subjects"].append(new_subject)

    # ★ ここで科目を選択（selected_subject という名前に変更）
    subject = st.selectbox(
        "科目を選択",
        st.session_state["subjects"],
        index=0,
        key="ocr_subject_select",  # ← 追加
    )

    # 画像アップロード
    uploaded = st.file_uploader(
        "画像をアップロード",
        type=["png", "jpg", "jpeg", "webp"],
    )

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
            st.markdown(
                """
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
                """,
                unsafe_allow_html=True,
            )

            if st.button("実行", key="round_big_run"):
                # ファイルをバイト列として読み込み
                # uploaded.seek(0) はなくてもOKなので削っています
                image_bytes = uploaded.read()

                # OCR と 要約
                text = run_azure_ocr(image_bytes)
                summary = run_azure_summary(text)

                # OcrRecord の作成（★ 科目は selected_subject を使う）
                rec = OcrRecord(
                    id=str(uuid.uuid4()),
                    created_at=_now_iso(),
                    filename=uploaded.name,
                    text=text,
                    summary=summary,
                    subject=subject,  # ← ここを subject にする
                    meta={"size": len(image_bytes)},
                )

                # セッションの履歴に追加
                st.session_state.records.insert(0, rec)

                # Azure Blob Storage の CSV に追記保存
                save_to_blob_csv(rec)
                # 完了アニメーション（中央に丸＋チェックがポンっと出る）
                st.markdown(
                    """
                    <div class="ocr-done-wrapper">
                    <div class="ocr-done-circle">
                        <span class="ocr-done-check">✓</span>
                    </div>
                    <div class="ocr-done-text">保存完了！</div>
                    </div>

                    <style>
                    .ocr-done-wrapper {
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        margin-top: 24px;
                        animation: fadeInUp 0.6s ease-out;
                    }

                    .ocr-done-circle {
                        width: 80px;
                        height: 80px;
                        border-radius: 999px;
                        background: linear-gradient(135deg, #34D399, #22C55E);
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        box-shadow: 0 8px 20px rgba(16, 185, 129, 0.6);
                        animation: popIn 0.4s ease-out;
                    }

                    .ocr-done-check {
                        color: #ffffff;
                        font-size: 42px;
                        font-weight: 700;
                        transform: translateY(2px);
                        animation: bounce 0.6s ease-out 0.1s both;
                    }

                    .ocr-done-text {
                        margin-top: 12px;
                        font-size: 18px;
                        font-weight: 600;
                        color: #166534;
                    }

                    @keyframes popIn {
                        0% {
                            transform: scale(0.4);
                            opacity: 0;
                        }
                        70% {
                            transform: scale(1.08);
                            opacity: 1;
                        }
                        100% {
                            transform: scale(1.0);
                        }
                    }

                    @keyframes bounce {
                        0%   { transform: translateY(-8px); }
                        50%  { transform: translateY(2px);  }
                        100% { transform: translateY(0);    }
                    }

                    @keyframes fadeInUp {
                        0% {
                            opacity: 0;
                            transform: translateY(10px);
                        }
                        100% {
                            opacity: 1;
                            transform: translateY(0);
                        }
                    }
                    </style>
                    """,
                    unsafe_allow_html=True,
                )


    else:
        st.info("まず画像ファイルをアップロードしてください。")








def render_sidebar():
    with st.sidebar:
        st.subheader("設定 / Filters")

        # ★ ここで履歴の種類を選ぶ
        history_type = st.radio(
            "履歴の種類",
            ["OCR", "復習"],
            index=0,
        )

        q = st.text_input("キーワード検索（ファイル名/本文/要約）")

        period = st.selectbox(
            "期間フィルタ",
            ["すべて", "直近7日", "直近30日", "今月"],
        )

        subject_filter = st.selectbox(
            "科目フィルタ",
            ["すべて"] + (st.session_state.get("subjects") or ["未分類"])
        )

    return {
        "history_type": history_type,  # ← ここが重要！
        "q": q,
        "period": period,
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
            ax.set_title(t, fontproperties=prop, fontsize=13)
        xl = ax.get_xlabel()
        if xl:
            ax.set_xlabel(xl, fontproperties=prop, fontsize=10)
        yl = ax.get_ylabel()
        if yl:
            ax.set_ylabel(yl, fontproperties=prop, fontsize=10)
        # 目盛りラベル
        for lab in ax.get_xticklabels() + ax.get_yticklabels():
            lab.set_fontproperties(prop)
            lab.set_fontsize(8)

    # ========= データ準備 =========
    df = df_from_records(records)
    df["date"] = pd.to_datetime(df["created_at"]).dt.date

    # ========= サマリー（上段） =========
    total_ocr = len(df)
    last7 = df[df["date"] >= (dt.date.today() - dt.timedelta(days=7))]
    recent_ocr = len(last7)

    c1, c2 = st.columns(2)
    with c1:
        metric_card("総OCR件数", f"{total_ocr} 件")
    with c2:
        metric_card("直近7日間のOCR件数", f"{recent_ocr} 件")

    st.divider()

    # ====== レイアウト用：左右に少し余白を作る ======
    left_pad, main_col, right_pad = st.columns([0.04, 0.92, 0.04])

    with main_col:
        # ========= 横並びレイアウト =========
        col_left, col_right = st.columns(2)

        # ---- 左：日別OCR件数（直近30日） ----
        with col_left:
            st.markdown("#### 日別OCR件数（直近30日）")

            daily_counts = (
                df.groupby("date")
                  .size()
                  .rename("count")
                  .reset_index()
                  .sort_values("date")
            )

            today = dt.date.today()
            start = today - dt.timedelta(days=29)
            daily_counts = daily_counts[daily_counts["date"] >= start]

            if not daily_counts.empty:
                # 横並び用にコンパクトなサイズ
                fig1, ax1 = plt.subplots(figsize=(4.2, 2.6))
                x_labels = daily_counts["date"].astype(str)

                ax1.bar(x_labels, daily_counts["count"])
                ax1.set_xlabel("日付")
                ax1.set_ylabel("件数")
                ax1.grid(axis="y", linestyle="--", alpha=0.4)

                # 上に件数（整数）を表示
                for x, y in zip(range(len(x_labels)), daily_counts["count"]):
                    ax1.text(
                        x,
                        y + 0.05,
                        str(int(y)),
                        ha="center",
                        va="bottom",
                        fontsize=8,
                    )

                # Y軸を整数目盛りにする
                max_count = int(daily_counts["count"].max())
                ax1.set_ylim(0, max_count + 1)
                ax1.set_yticks(range(0, max_count + 2))

                plt.setp(ax1.get_xticklabels(), rotation=45, ha="right")

                apply_jp_font(ax1)
                fig1.tight_layout(pad=0.3)
                st.pyplot(fig1, use_container_width=True)
                plt.close(fig1)
            else:
                st.info("直近30日間のデータがありません。")

        # ---- 右：科目別OCR件数（累計） ----
        with col_right:
            st.markdown("#### 科目別OCR件数（累計）")

            if "subject" in df.columns and not df["subject"].isna().all():
                subject_counts = (
                    df.groupby("subject")
                      .size()
                      .sort_values(ascending=False)  # 件数が多い科目を左に
                )

                fig2, ax2 = plt.subplots(figsize=(4.2, 2.6))

                # ★ 縦棒グラフ：x=科目, y=件数
                x_labels = subject_counts.index.tolist()
                y_values = subject_counts.values

                ax2.bar(x_labels, y_values)
                ax2.set_xlabel("科目")
                ax2.set_ylabel("件数")
                ax2.grid(axis="y", linestyle="--", alpha=0.4)

                # 棒の上に件数ラベル（整数）
                for x, v in enumerate(y_values):
                    ax2.text(
                        x,
                        int(v) + 0.05,
                        str(int(v)),
                        ha="center",
                        va="bottom",
                        fontsize=8,
                    )

                # Y軸を整数目盛りにする
                max_v = int(y_values.max())
                ax2.set_ylim(0, max_v + 1)
                ax2.set_yticks(range(0, max_v + 2))

                # 科目名が重ならないように少し斜めに
                plt.setp(ax2.get_xticklabels(), rotation=30, ha="right")

                apply_jp_font(ax2)
                fig2.tight_layout(pad=0.4)
                st.pyplot(fig2, use_container_width=True)
                plt.close(fig2)
            else:
                st.info("科目情報が未設定のため、科目別グラフは表示できません。")











# =====================
# メイン
# =====================
def main():

        # 起動時に CSV 読み込み
    if "records" not in st.session_state or not st.session_state.records:
        blob_records = load_records_from_blob()
        if blob_records:
            st.session_state.records = blob_records

        # ★ 復習クイズ履歴CSVも読み込む
    if "quiz_history" not in st.session_state:
        quiz_logs = load_quiz_history_from_blob()
        st.session_state.quiz_history = quiz_logs


    # セッション初期化
    if "records" not in st.session_state:
        st.session_state.records: List[OcrRecord] = []

    st.set_page_config(page_title=APP_TITLE, layout="wide")
    inject_global_css()
    st.markdown("""
    <style>
    /* タブ全体のコンテナ：上下レイアウトにして、下にうっすら線 */
    div[data-testid="stTabs"] > div {
        border-bottom: 1px solid #e5e7eb;
        padding: 0 0 0.75rem 0;
    }

    /* タブボタンを横に並べるコンテナ（1個目の子だけ flex） */
    /* ★ 横幅をコンテンツいっぱいに広げる */
    div[data-testid="stTabs"] > div > div:first-child {
        display: flex;
        justify-content: flex-start;   /* 中央寄せにしたければ center */
        gap: 0.5rem;
        width: 100%;                   /* ← これを追加 */
    }

    /* タブのタイトル（共通・ピル型） */
    div[data-testid="stTabs"] button {
        font-size: 1.0rem !important;
        font-weight: 600 !important;
        padding: 6px 18px !important;
        border-radius: 999px !important;
        border: none !important;
        background: transparent !important;
        color: #6b7280 !important;
        box-shadow: none !important;
        flex: 1 1 0;
    }

    /* タブのタイトル（選択中） */
    div[data-testid="stTabs"] button[aria-selected="true"] {
        background: #1E3A8A !important;
        color: #ffffff !important;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.25) !important;
        transform: translateY(1px);
    }

    /* ホバー時 */
    div[data-testid="stTabs"] button:hover {
        background: rgba(37, 99, 235, 0.08) !important;
        color: #1d4ed8 !important;
    }

    /* タブ下の各ページタイトル（OCR / 履歴 / 進捗 / 復習） */
    [data-testid="stMarkdownContainer"] h3 {
        display: inline-block;
        font-size: 1.9rem !important;
        font-weight: 900 !important;
        color: #1E3A8A !important;
        border-radius: 6px;
        margin-top: 8px !important;
        margin-bottom: 18px !important;
    }

    /* メインコンテンツの上の余白をなくす */
    main .block-container {
        padding-top: 0rem;
        padding-bottom: 0rem;
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
        render_review_tab()

if __name__ == "__main__":
    main()


