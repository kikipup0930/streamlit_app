import streamlit as st

def inject_global_css():
    st.markdown(
        """
        <style>
        /* --- 共通 --- */
        .sr-card { 
          position: relative; 
          margin: 12px 0 24px; 
          padding: 18px 20px; 
        }
        .sr-title { 
          margin: 0 0 6px 0; 
          font-weight: 700; 
          font-size: 1.25rem; 
          letter-spacing: .3px;
        }
        .sr-meta  { 
          color: #667085; 
          font-size: .85rem; 
          margin-bottom: 12px; 
        }
        .sr-sec   { margin-top: 10px; }
        .sr-sec h4 { 
          margin: 0 0 6px 0; 
          font-size: .95rem; 
          font-weight: 700; 
        }
        .sr-sec .box { 
          background:#ffffffcc; 
          border-radius: 8px; 
          padding: 10px 12px; 
        }

        /* =========================
           付箋風 (sticky-note)
           ========================= */
        .sticky-note {
          background: #fff4a8;
          border-radius: 10px;
          box-shadow: 0 10px 18px rgba(0,0,0,.10), 0 2px 5px rgba(0,0,0,.06);
          transform: rotate(-0.6deg);
        }

        /* マスキングテープ */
        .sticky-note:before{
          content:"";
          position:absolute;
          top:-16px; left: 50%;
          transform: translateX(-50%) rotate(-2deg);
          width: 120px; height: 26px;
          background: linear-gradient(#efe6bf,#e6dbb2);
          box-shadow: 0 2px 6px rgba(0,0,0,.1);
          border-radius: 4px;
          opacity:.95;
        }

        /* コピー用ボタンの見た目を軽く */
        .sr-copy-btn {
          display:inline-block; border:1px solid #d0d5dd; background:#fff;
          border-radius:8px; padding:6px 10px; font-size:.9rem; cursor:pointer;
        }
        .sr-copy-btn:hover { background:#f2f4f7; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_header(title: str, subtitle: str = "手書きノートOCR＋要約による自動復習生成"):
    st.markdown(
        f"""
        <div style="padding:22px 22px; border-radius:18px; background:linear-gradient(180deg,#f9f8f2,#f4f1e6);
                    border:1px solid #ece8da; box-shadow:0 12px 20px rgba(0,0,0,.05); margin-bottom:16px;">
          <div style="font-size:32px; font-weight:800; letter-spacing:.3px;">{title}</div>
          <div style="color:#667085; margin-top:6px;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def metric_card(label: str, value: str, accent: str = "#16a34a"):
    st.markdown(
        f"""
        <div style="border:1px solid #e5e7eb; border-radius:14px; padding:16px 18px; background:#fff;">
          <div style="color:#6b7280; font-size:.92rem; margin-bottom:6px;">{label}</div>
          <div style="font-size:26px; font-weight:800; color:{accent};">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_history_card(*, title: str, meta: str, summary: str, fulltext: str):
    """履歴を付箋風カードで描画"""
    st.markdown(
        f"""
        <div class="sr-card sticky-note">
          <div class="sr-title">{title}</div>
          <div class="sr-meta">{meta}</div>

          <div class="sr-sec">
            <h4>要約</h4>
            <div class="box">{summary or "-"}</div>
          </div>

          <div class="sr-sec" style="margin-top:12px;">
            <details>
              <summary style="cursor:pointer;">OCR全文を表示</summary>
              <div class="box" style="margin-top:10px; white-space:pre-wrap;">{fulltext or "-"}</div>
            </details>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
