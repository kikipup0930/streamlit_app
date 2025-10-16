import streamlit as st

# ==============================
# 💄 グローバルCSS（教育アプリ風）
# ==============================
def inject_global_css():
    st.markdown("""
    <style>
    html, body, [class*="block-container"] {
        font-family: "Noto Sans JP", sans-serif;
        background-color: #F6F7F9;
    }

    /* ---- ヘッダー ---- */
    .main-header {
        background: linear-gradient(90deg, #3B82F6, #60A5FA);
        color: white;
        padding: 20px 32px;
        border-radius: 12px;
        margin-bottom: 25px;
        box-shadow: 0 4px 12px rgba(59,130,246,0.3);
    }
    .main-header h1 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
    }
    .main-header p {
        margin: 4px 0 0 0;
        font-size: 0.95rem;
        opacity: 0.9;
    }

    /* ---- カード ---- */
    .card {
        border-radius: 14px;
        padding: 16px 18px;
        background: #fff;
        border: 1px solid #e5e7eb;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 12px;
    }

    /* ---- メトリックカード ---- */
    .metric-card {
        border-radius: 16px;
        padding: 14px 18px;
        background: linear-gradient(180deg, #ffffff, #f9fafb);
        border: 1px solid #e5e7eb;
        box-shadow: 0 6px 18px rgba(17,24,39,0.05);
        text-align: center;
    }
    .metric-title {
        color: #3B82F6;
        font-size: 0.9rem;
        font-weight: 600;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 1.4rem;
        font-weight: 700;
        color: #111827;
    }

    /* ---- Divider ---- */
    hr {
        border: none;
        border-top: 1px solid #E5E7EB;
        margin: 20px 0;
    }
    </style>
    """, unsafe_allow_html=True)

# ==============================
# 🧭 ヘッダー部分
# ==============================
def render_header(title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="main-header">
            <h1>📝 {title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

# ==============================
# 📊 メトリックカード
# ==============================
def metric_card(title: str, value: str):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-title">{title}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
