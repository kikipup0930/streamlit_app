import streamlit as st

def inject_global_css():
    st.markdown("""
    <style>
    /* --- ベースを透明に --- */
    html, body {
        background: transparent !important;
    }
    [data-testid="stAppViewContainer"] {
        background: transparent !important;
        position: relative;
        z-index: 0;
    }

    /* --- ノート紙 背景を before で固定描画 --- */
    [data-testid="stAppViewContainer"]::before {
        content: "";
        position: fixed;
        inset: 0;
        z-index: -1;
        pointer-events: none;

        /* ノート紙：横罫線＋左マージン線 */
        background-color: #fcfcf7;
        background-image:
          linear-gradient(#e0e0e0 1px, transparent 1px),      /* 横罫線 */
          linear-gradient(90deg, #ffb6b6 2px, transparent 2px); /* 左マージン線 */
        background-size: 100% 32px, 120px 100%;  /* 横線間隔とマージン位置 */
        background-position: 0 16px, 80px 0;     /* 少し下から開始＋左赤線 */
    }

    /* --- サイドバー --- */
    [data-testid="stSidebar"] {
        background-color: #faf9f6 !important;
        border-right: 1px solid #ddd !important;
    }

    /* --- ヘッダー（表紙風） --- */
    .sr-header {
        background: linear-gradient(90deg, #fdfcf8, #f6f5ef);
        padding: 1.3rem 1.6rem;
        border-radius: 14px;
        box-shadow: 0 3px 7px rgba(0,0,0,0.08);
        border-left: 6px solid #4CAF50;
        margin-bottom: 1.2rem;
    }
    .sr-header h1 {
        margin: 0;
        font-size: 2rem;
        font-weight: 700;
        color: #2d2d2d;
        letter-spacing: .02em;
    }
    .sr-header p {
        margin: .35rem 0 0;
        color: #666;
        font-size: 1rem;
    }

    /* --- ノートカード --- */
    .sr-card {
        background-color: #fffefb;
        border: 1px solid #e8e6dc;
        border-radius: 12px;
        padding: 1.1rem 1.4rem;
        box-shadow: 0 4px 7px rgba(0,0,0,0.08);
        margin-bottom: 1rem;
        transition: transform .15s ease, box-shadow .3s;
        background-image: linear-gradient(#f3f3f1 1px, transparent 1px);
        background-size: 100% 30px;
    }
    .sr-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
    }

    /* --- 進捗メトリックカード --- */
    .sr-metric {
        background-color: #fff;
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .sr-metric h3 { margin: 0; color: #444; font-size: 1.05rem; font-weight: 600; }
    .sr-metric p  { margin: .45rem 0 0; font-size: 1.35rem; font-weight: 800; color: #2E7D32; }

    /* --- ボタンや入力の角丸 --- */
    .stTextInput > div > div > input,
    .stSelectbox > div > div,
    .stFileUploader,
    .stButton > button {
        border-radius: 8px !important;
    }

    /* --- タブの選択スタイル --- */
    div[data-baseweb="tab-list"] button {
        font-weight: 600;
        padding: 6px 14px;
    }
    div[data-baseweb="tab-list"] button[data-selected="true"] {
        border-bottom: 3px solid #4CAF50;
        color: #2E7D32;
    }
    </style>
    """, unsafe_allow_html=True)

def render_header(title="StudyRecord", subtitle="手書きノートOCR＋要約による自動復習生成"):
    st.markdown(f"""
        <div class="sr-header">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
    """, unsafe_allow_html=True)

def metric_card(label: str, value: str):
    st.markdown(
        f"""
        <div class="sr-metric">
            <h3>{label}</h3>
            <p>{value}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
