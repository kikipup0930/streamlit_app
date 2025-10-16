import streamlit as st

# ========================================
# ノート風グローバルCSS注入
# ========================================
def inject_global_css():
    st.markdown("""
    <style>
    /* 全体背景：ノート風（淡い紙＋罫線） */
    body {
        background-color: #fafaf8;
        background-image: linear-gradient(#e5e5e5 1px, transparent 1px);
        background-size: 100% 28px;
        font-family: "Noto Sans JP", sans-serif;
    }

    /* タイトルヘッダー */
    .sr-header {
        background: linear-gradient(135deg, #fefefe, #f5f5f0);
        padding: 1.2rem 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        border-left: 6px solid #4CAF50;
        margin-bottom: 1rem;
    }

    .sr-header h1 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
        color: #333;
    }

    .sr-header p {
        margin: 0.3rem 0 0;
        color: #666;
        font-size: 0.95rem;
    }

    /* ノートカード風コンテナ */
    .sr-card {
        background-color: #fffdf9;
        border: 1px solid #ddd6c5;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
        transition: transform 0.1s ease-in-out, box-shadow 0.2s;
    }

    .sr-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 3px 8px rgba(0,0,0,0.12);
    }

    /* メトリックカード */
    .sr-metric {
        background-color: #ffffffcc;
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }

    .sr-metric h3 {
        margin: 0;
        color: #333;
        font-size: 1.1rem;
    }

    .sr-metric p {
        margin: 0.4rem 0 0;
        font-size: 1.3rem;
        font-weight: bold;
        color: #2E7D32;
    }

    /* コピー用ボタン */
    .sr-copy {
        background-color: #4CAF50;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 4px 8px;
        cursor: pointer;
        font-size: 0.85rem;
    }

    .sr-copy:hover {
        background-color: #43A047;
    }

    /* Streamlitのデフォルトコンテナ調整 */
    [data-testid="stAppViewContainer"] {
        background: transparent !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ========================================
# ヘッダー
# ========================================
def render_header(title: str, subtitle: str = ""):
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
# カード表示（汎用）
# ========================================
def card(title: str, icon: str = "📄"):
    return st.container()

# ========================================
# メトリックカード
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
