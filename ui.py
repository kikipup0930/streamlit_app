import streamlit as st

# ========================================
# ノート風グローバルCSS注入
# ========================================
def inject_global_css():
    st.markdown("""
    <style>
    /* 背景：ノート紙風（青罫線＋赤マージン線） */
    body {
        background-color: #fcfcf7;
        background-image:
            linear-gradient(#e6e6e6 1px, transparent 1px),
            linear-gradient(90deg, #ffb6b6 1px, transparent 1px);
        background-size: 100% 28px, 120px 100%;
        font-family: "Noto Sans JP", sans-serif;
    }

    /* ヘッダー */
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
    }
    .sr-header p {
        margin: 0.3rem 0 0;
        color: #666;
        font-size: 1rem;
    }

    /* カード：ノート紙＋影 */
    .sr-card {
        background-color: #fffefb;
        border: 1px solid #e8e6dc;
        border-radius: 12px;
        padding: 1.1rem 1.4rem;
        box-shadow: 0 4px 7px rgba(0,0,0,0.08);
        margin-bottom: 1rem;
        transition: transform 0.15s ease, box-shadow 0.3s;
        background-image: linear-gradient(#f3f3f1 1px, transparent 1px);
        background-size: 100% 30px;
    }

    .sr-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
    }

    /* メトリックカード */
    .sr-metric {
        background-color: #fff;
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .sr-metric h3 { margin: 0; color: #444; font-size: 1.1rem; }
    .sr-metric p { margin: 0.4rem 0 0; font-size: 1.3rem; font-weight: bold; color: #2E7D32; }

    /* コピー用ボタン */
    .sr-copy {
        background-color: #66BB6A;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 5px 9px;
        cursor: pointer;
        font-size: 0.85rem;
    }
    .sr-copy:hover { background-color: #57A05D; }

    /* Streamlit背景透過 */
    [data-testid="stAppViewContainer"] { background: transparent !important; }

    /* サイドバー */
    [data-testid="stSidebar"] {
        background-color: #faf9f6 !important;
        border-right: 1px solid #ddd !important;
    }

    /* Streamlit標準要素 */
    .stTextInput > div > div > input,
    .stSelectbox > div > div,
    .stFileUploader,
    .stButton > button {
        border-radius: 8px !important;
    }

    /* タブ */
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


# ========================================
# ヘッダー
# ========================================
def render_header(title: str = "StudyRecord", subtitle: str = "手書きノートOCR＋要約による自動復習生成"):
    st.markdown(
        f"""
        <div class="sr-header">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ========================================
# ノートカード風コンテナ（任意の中身で使う）
# ========================================
def note_card(content_html: str):
    st.markdown(f"<div class='sr-card'>{content_html}</div>", unsafe_allow_html=True)

# ========================================
# メトリックカード（進捗画面で使用）
# ========================================
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
