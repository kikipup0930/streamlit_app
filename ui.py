# ui.py
import streamlit as st
from contextlib import contextmanager

# ==============================
# グローバルCSS（教育アプリ風）
# ==============================
def inject_global_css():
    st.markdown("""
    <style>
      /* ベース */
      html, body, [class*="block-container"]{
        font-family: "Noto Sans JP", system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
        background: #F6F7F9;
      }
      /* 見出しの行間を少し詰める */
      h1, h2, h3 { line-height: 1.2; }

      /* ヘッダー */
      .sr-header{
        background: linear-gradient(90deg,#3B82F6,#60A5FA);
        color:#fff;
        padding:18px 24px;
        border-radius:14px;
        box-shadow:0 6px 18px rgba(59,130,246,.25);
        margin-bottom:18px;
      }
      .sr-header h1{ margin:0; font-size:1.7rem; font-weight:800; }
      .sr-header p{ margin:.25rem 0 0; opacity:.95; }

      /* カード共通 */
      .sr-card{
        background:#fff;
        border:1px solid #e5e7eb;
        border-radius:16px;
        padding:16px 18px;
        box-shadow:0 6px 18px rgba(17,24,39,.06);
        margin-bottom:14px;
      }
      .sr-card h3{ margin:.2rem 0 0.6rem; font-weight:700; }

      /* メトリック（サマリー） */
      .sr-metric{
        text-align:center;
        border-radius:16px;
        padding:14px 16px;
        background:linear-gradient(180deg,#fff,#f9fafb);
        border:1px solid #e5e7eb;
        box-shadow:0 8px 22px rgba(17,24,39,.06);
      }
      .sr-metric .t{ color:#3B82F6; font-weight:700; font-size:.9rem; }
      .sr-metric .v{ color:#0f172a; font-weight:800; font-size:1.4rem; margin-top:2px; }

      /* ボタン（全体） */
      .stButton>button{
        background:#2563EB!important;
        border:1px solid #1e40af!important;
        color:#fff!important;
        font-weight:700!important;
        border-radius:12px!important;
        padding:.55rem 1rem!important;
        box-shadow:0 4px 12px rgba(37,99,235,.25)!important;
      }
      .stButton>button:hover{ filter:brightness(1.03); }

      /* アップローダ枠すっきり */
      .uploadedFile, .st-emotion-cache-1c7y2kd, .stFileUploader{
        border-radius:12px!important;
      }

      /* タブの下線を細く */
      .stTabs [data-baseweb="tab-list"]{
        gap: 6px;
        border-bottom: 1px solid #e5e7eb;
      }
      .stTabs [data-baseweb="tab"]{
        padding-top: 10px; padding-bottom: 10px;
      }

      /* エクスパンダのタイトル行を強調 */
      details>summary{
        font-weight:700;
      }

      /* コピー用ボタン */
      .sr-copy{
        background:#EEF2FF; color:#3730A3; border:1px solid #c7d2fe;
        padding:.3rem .6rem; border-radius:10px; font-weight:700;
      }
    </style>
    """, unsafe_allow_html=True)

# ==============================
# ヘッダー
# ==============================
def render_header(title: str, subtitle: str = ""):
    st.markdown(f"""
    <div class="sr-header">
      <h1>📝 {title}</h1>
      <p>{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)

# ==============================
# カード（コンテナ）
# ==============================
@contextmanager
def card(title: str | None = None, icon: str = ""):
    c = st.container()
    with c:
        st.markdown('<div class="sr-card">', unsafe_allow_html=True)
        if title:
            t = f"{icon} {title}" if icon else title
            st.markdown(f"<h3>{t}</h3>", unsafe_allow_html=True)
        yield
        st.markdown("</div>", unsafe_allow_html=True)

# ==============================
# メトリックカード
# ==============================
def metric_card(title: str, value: str):
    st.markdown(f"""
    <div class="sr-metric">
      <div class="t">{title}</div>
      <div class="v">{value}</div>
    </div>
    """, unsafe_allow_html=True)
