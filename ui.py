import streamlit as st

# ==========================================
# グローバルCSSとUIコンポーネント
# ==========================================

def inject_global_css():
    st.markdown("""
    <style>
    /* 全体リセット */
    html, body {
        margin: 0;
        padding: 0;
        height: 100%;
        overflow-x: hidden;
    }
    [data-testid="stAppViewContainer"] {
        position: relative;
        z-index: 0;
    }

    /* ------------------------------
       📘 背景ノート罫線（全面固定）
    ------------------------------ */
    #note-background {
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        z-index: -1;
        background-color: #fcfcf7;
        background-image:
            linear-gradient(#d4d4d4 1px, transparent 1px),      /* 横罫線 */
            linear-gradient(90deg, #ff8e8e 1px, transparent 1px); /* 赤マージン線 */
        background-size: 100% 28px, 120px 100%;
        background-position: 0 0, 0 0;
    }

    /* ------------------------------
       📂 サイドバー
    ------------------------------ */
    [data-testid="stSidebar"] {
        background-color: #faf9f6 !important;
        border-right: 1px solid #ddd !important;
    }

    /* ------------------------------
       🪶 ヘッダー（タイトルカード風）
    ------------------------------ */
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

    /* ------------------------------
       🗒️ ノートカード（履歴など）
    ------------------------------ */
    .sr-card {
        background-color: #fffefb;
        border: 1px solid #e8e6dc;
        border-radius: 12px;
        padding: 1.1rem 1.4rem;
        box-shadow: 0 4px 7px rgba(0,0,0,0.08);
        margin-bottom: 1rem;
        background-image: linear-gradient(#f3f3f1 1px, transparent 1px);
        background-size: 100% 30px;
        transition: transform .15s ease, box-shadow .3s;
    }
    .sr-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
    }

    /* ------------------------------
       📊 メトリックカード（進捗）
    ------------------------------ */
    .sr-metric {
        background-color: #fff;
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .sr-metric h3 {
        margin: 0;
        color: #444;
        font-size: 1.05rem;
        font-weight: 600;
    }
    .sr-metric p {
        margin: .45rem 0 0;
        font-size: 1.35rem;
        font-weight: 800;
        color: #2E7D32;
    }

    /* ------------------------------
       🎛️ タブ選択のスタイル
    ------------------------------ */
    div[data-baseweb="tab-list"] button {
        font-weight: 600;
        padding: 6px 14px;
    }
    div[data-baseweb="tab-list"] button[data-selected="true"] {
        border-bottom: 3px solid #4CAF50;
        color: #2E7D32;
    }

    /* ------------------------------
       💬 入力・ボタン角丸調整
    ------------------------------ */
    .stTextInput > div > div > input,
    .stSelectbox > div > div,
    .stFileUploader,
    .stButton > button {
        border-radius: 8px !important;
    }

    /* ------------------------------
       📋 コピー用ボタンの装飾
    ------------------------------ */
    button[id^="copy-btn-"] {
        background: #f5f5f5;
        border: 1px solid #ddd;
        border-radius: 6px;
        padding: 0.4rem 0.8rem;
        cursor: pointer;
        transition: 0.2s;
    }
    button[id^="copy-btn-"]:hover {
        background: #e0e0e0;
    }

    </style>

    <!-- ✅ 背景ノートをHTMLで直接描画 -->
    <div id="note-background"></div>
    """, unsafe_allow_html=True)


# ==========================================
# ヘッダー
# ==========================================
def render_header(title="StudyRecord", subtitle="手書きノートOCR＋要約による自動復習生成"):
    st.markdown(f"""
        <div class="sr-header">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
    """, unsafe_allow_html=True)


# ==========================================
# メトリックカード（進捗用）
# ==========================================
def metric_card(label: str, value: str):
    st.markdown(f"""
        <div class="sr-metric">
            <h3>{label}</h3>
            <p>{value}</p>
        </div>
    """, unsafe_allow_html=True)
