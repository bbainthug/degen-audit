from dotenv import load_dotenv
load_dotenv()  # 必须在所有自定义 import 之前执行，确保环境变量最优先注入

import streamlit as st
import data_engine
import ai_profiler

# ─────────────────────────────────────────────
# 全局配置
# ─────────────────────────────────────────────
st.set_page_config(
    page_title='DegenScan | 链上人格体检',
    page_icon='🧬',
    layout='wide'
)

# ─────────────────────────────────────────────
# 全局暗黑极客 CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@700&display=swap');

  html, body, [class*="css"] {
      background-color: #07090d !important;
      color: #b8e8c8 !important;
      font-family: 'Share Tech Mono', monospace !important;
  }

  /* 主标题 */
  .main-title {
      font-family: 'Orbitron', monospace;
      font-size: 2.8rem;
      font-weight: 700;
      color: #00ff88;
      text-shadow: 0 0 18px #00ff88, 0 0 40px #00cc66;
      letter-spacing: 2px;
      line-height: 1.2;
  }

  /* 副标题 */
  .sub-title {
      font-family: 'Share Tech Mono', monospace;
      font-size: 1rem;
      color: #556655;
      letter-spacing: 3px;
      margin-top: 4px;
  }

  /* 输入框 */
  .stTextInput > div > div > input {
      background-color: #0d1a0d !important;
      border: 1px solid #00ff88 !important;
      border-radius: 4px !important;
      color: #00ff88 !important;
      font-family: 'Share Tech Mono', monospace !important;
      font-size: 1rem !important;
      padding: 12px 16px !important;
      box-shadow: 0 0 10px #00ff4422 inset;
  }
  .stTextInput > div > div > input:focus {
      box-shadow: 0 0 20px #00ff8855 inset, 0 0 10px #00ff8844 !important;
  }

  /* 按钮 */
  .stButton > button {
      background: linear-gradient(135deg, #003322, #001a11) !important;
      border: 1px solid #00ff88 !important;
      color: #00ff88 !important;
      font-family: 'Orbitron', monospace !important;
      font-size: 1.1rem !important;
      font-weight: 700 !important;
      letter-spacing: 2px !important;
      padding: 14px 48px !important;
      border-radius: 4px !important;
      box-shadow: 0 0 20px #00ff4433;
      transition: all 0.2s ease;
      width: 100%;
  }
  .stButton > button:hover {
      background: linear-gradient(135deg, #00ff88, #00cc66) !important;
      color: #080b0f !important;
      box-shadow: 0 0 40px #00ff8899 !important;
  }

  /* 标签卡片 */
  .label-card {
      background: #0a1a0a;
      border: 1px solid #00ff88;
      border-radius: 6px;
      padding: 20px 24px;
      margin-bottom: 16px;
      box-shadow: 0 0 20px #00ff4422;
  }
  .label-title {
      font-family: 'Orbitron', monospace;
      font-size: 1.5rem;
      color: #00ff88;
      text-shadow: 0 0 10px #00ff88;
      word-break: break-all;
  }

  /* 证据行 */
  .evidence-row {
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      border-bottom: 1px solid #1a2e1a;
      font-size: 0.9rem;
  }
  .evidence-key   { color: #556655; }
  .evidence-value { color: #00ff88; font-weight: bold; }

  /* AI 评语框 - 讽刺 */
  .roast-box {
      background: #1a0505;
      border: 1px solid #ff3333;
      border-left: 4px solid #ff3333;
      border-radius: 6px;
      padding: 24px 28px;
      box-shadow: 0 0 30px #ff333322;
  }
  .roast-text {
      font-family: 'Share Tech Mono', monospace;
      font-size: 1.15rem;
      color: #ff6666;
      line-height: 1.8;
      text-shadow: 0 0 8px #ff333344;
  }

  /* AI 评语框 - 膜拜 */
  .praise-box {
      background: #00100a;
      border: 1px solid #00ff88;
      border-left: 4px solid #00ff88;
      border-radius: 6px;
      padding: 24px 28px;
      box-shadow: 0 0 30px #00ff8822;
  }
  .praise-text {
      font-family: 'Share Tech Mono', monospace;
      font-size: 1.15rem;
      color: #00ff88;
      line-height: 1.8;
      text-shadow: 0 0 8px #00ff8844;
  }

  /* metric 覆盖 */
  [data-testid="stMetricValue"] {
      color: #00ff88 !important;
      font-family: 'Share Tech Mono', monospace !important;
  }
  [data-testid="stMetricLabel"] {
      color: #556655 !important;
  }

  /* 分割线 */
  hr { border-color: #1a2e1a !important; }

  /* 隐藏 streamlit 默认品牌 */
  #MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 语言切换器（右上角按钮，用 session_state 保持状态）
# ─────────────────────────────────────────────
if 'lang' not in st.session_state:
    st.session_state['lang'] = 'zh'

# 右上角切换按钮（长方形 + 国旗）
_col_spacer, _col_btn = st.columns([10, 2])
with _col_btn:
    _is_zh = st.session_state['lang'] == 'zh'
    _btn_label = '🇺🇸  English' if _is_zh else '🇨🇳  中文'
    st.markdown('''
    <style>
    div[data-testid="column"]:last-child .stButton > button {
        background: linear-gradient(135deg, #0a1628, #0d2040) !important;
        border: 1.5px solid #4a9eff !important;
        color: #e8f4ff !important;
        font-family: "SF Pro Display", "Inter", sans-serif !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px !important;
        padding: 6px 18px !important;
        border-radius: 6px !important;
        box-shadow: 0 0 12px #4a9eff22 !important;
        width: auto !important;
        min-width: 110px !important;
    }
    div[data-testid="column"]:last-child .stButton > button:hover {
        background: linear-gradient(135deg, #1a2f50, #1a3060) !important;
        border-color: #74b9ff !important;
        box-shadow: 0 0 18px #4a9eff44 !important;
    }
    </style>
    ''', unsafe_allow_html=True)
    if st.button(_btn_label, key='lang_toggle'):
        st.session_state['lang'] = 'en' if _is_zh else 'zh'
        st.rerun()
lang = st.session_state['lang']

# 静态文案映射
_I18N = {
    'zh': {
        'page_title':   'AlphaClaw | 链上人格体检',
        'main_title':   '🧬 DEGEN AUDIT',
        'sub_heading':  'Degen 开盒机：一眼看穿你的辣鸡操作，准备迎接灵魂羞辱',
        'sub_tagline':  '[ 正在检索该地址的链上行为数据 ... ]',
        'placeholder':  '请输入 Solana 钱包地址  (e.g. 9U22D...BzPb)',
        'fire_btn':     '🔥  开启无情侧写',
        'spinner':      '🔌 正在检索该地址的链上行为数据 ...',
        'err_addr':     '⚠️  ERROR_404: 仅支持 Solana 地址，无法建立链上连接',
        'err_addr_sub': '请输入有效的 Solana 钱包地址',
        'err_crash':    '💥 SYSTEM_CRASH: 侧写引擎遭遇未知异常',
        'status_elite': 'ELITE ▲',
        'status_rekt':  'REKT ▼',
        'slice_title':  '⏱️ 采样切片：最近 100 笔链上交互 (Current Momentum)。',
        'slice_sub':    '只评价你最近的狗屎运，别在这儿装大佬。',
        'id_class':     'IDENTITY_CLASS',
        'evidence_hdr': 'CHAIN_EVIDENCE',
        'no_evidence':  '// 暂无可用链上证据',
        'verdict_elite':'🏆 AI_VERDICT :: ELITE_PROFILE_DETECTED',
        'verdict_rekt': '💀 AI_VERDICT :: REKT_PATTERN_CONFIRMED',
        'raw_data':     '🗂️  RAW_DATA :: 查看完整链上切片',
        'disclaimer':   '⚠️ NFA: 仅供娱乐，非投资建议。数据来源：Helius 实时解析 | 审计逻辑：Llama 3.3 驱动 | Degen Audit © 2026',
    },
    'en': {
        'page_title':   'AlphaClaw | On-Chain Personality Scanner',
        'main_title':   '🧬 DEGEN AUDIT',
        'sub_heading':  'The Brutally Honest On-Chain Soul Audit',
        'sub_tagline':  '[ Retrieving on-chain behavior data ... ]',
        'placeholder':  'Enter a Solana wallet address  (e.g. 9U22D...BzPb)',
        'fire_btn':     '🔥  Run Brutal Profiling',
        'spinner':      '🔌 Hacking the chain node, extracting behavior slice...',
        'err_addr':     '⚠️  ERROR_404: Solana addresses only — connection failed',
        'err_addr_sub': 'Please enter a valid Solana wallet address (Base58, 32-44 chars)',
        'err_crash':    '💥 SYSTEM_CRASH: Profiler engine encountered an unknown error',
        'status_elite': 'ELITE ▲',
        'status_rekt':  'REKT ▼',
        'slice_title':  '⏱️ Sample Slice: Last 100 on-chain interactions (Current Momentum).',
        'slice_sub':    'Rating your recent degen moves only — stop larping as a whale.',
        'id_class':     'IDENTITY_CLASS',
        'evidence_hdr': 'CHAIN_EVIDENCE',
        'no_evidence':  '// No on-chain evidence available',
        'verdict_elite':'🏆 AI_VERDICT :: ELITE_PROFILE_DETECTED',
        'verdict_rekt': '💀 AI_VERDICT :: REKT_PATTERN_CONFIRMED',
        'raw_data':     '🗂️  RAW_DATA :: View Full On-Chain Slice',
        'disclaimer':   '⚠️ NFA: Entertainment only. Data: Helius real-time | Audit logic: Llama 3.3 | Degen Audit © 2026',
    },
}
T = _I18N[lang]
st.markdown(f"""
<div style="text-align:center; padding: 32px 0 8px 0;">
  <div class="main-title">{T['main_title']}</div>
  <div style="font-family:'Orbitron',monospace; font-size:1rem; color:#00ff88; letter-spacing:6px; margin:6px 0;">{T['sub_heading']}</div>
  <div class="sub-title">{T['sub_tagline']}</div>
</div>
""", unsafe_allow_html=True)

st.markdown("---")


# ─────────────────────────────────────────────
# 交互区
# ─────────────────────────────────────────────
_, center, _ = st.columns([1, 3, 1])

with center:
    address = st.text_input(
        label='wallet_input',
        placeholder=T['placeholder'],
        label_visibility='collapsed'
    )
    fire = st.button(T['fire_btn'], use_container_width=True)

st.markdown("---")


# ─────────────────────────────────────────────
# 核心逻辑
# ─────────────────────────────────────────────
if fire:
    if not address or len(address.strip()) < 10:
        st.markdown("""
        <div style="text-align:center; color:#ff4444; font-family:'Share Tech Mono',monospace; padding:24px;">
          ⚠️  ERROR_404: 地址格式异常，无法建立链上连接<br/>
          <small style="color:#553333;">请输入有效的 Solana 钱包地址</small>
        </div>
        """, unsafe_allow_html=True)
    else:
        with st.spinner(T['spinner']):
            try:
                # 数据层
                stats   = data_engine.get_wallet_stats(address.strip())
                profile = data_engine.generate_profile(stats)

                # AI 层
                ai_comment = ai_profiler.get_ai_roast(profile, lang=lang)

            except ValueError as e:
                err_msg = str(e)
                if '空白钱包' in err_msg or '交易记录为空' in err_msg:
                    title = '📭 WALLET_EMPTY: 空钱包或无交易记录'
                    color = '#ff9900'
                    hint_color = '#664400'
                elif '不支持的地址格式' in err_msg:
                    title = '⚠️ ADDRESS_INVALID: 地址格式不合法，无法建立链上连接'
                    color = '#ff9900'
                    hint_color = '#664400'
                else:
                    title = '⚠️ DATA_ERROR: 数据获取失败（可能是网络/API问题）'
                    color = '#ff9900'
                    hint_color = '#664400'
                st.markdown(f"""
                <div style="text-align:center; color:{color}; font-family:'Share Tech Mono',monospace; padding:24px;">
                  {title}<br/>
                  <small style="color:{hint_color};">{e}</small>
                </div>
                """, unsafe_allow_html=True)
                st.stop()
            except Exception as e:
                st.markdown(f"""
                <div style="text-align:center; color:#ff4444; font-family:'Share Tech Mono',monospace; padding:24px;">
                  💥 SYSTEM_CRASH: 侧写引擎遭遇未知异常<br/>
                  <small style="color:#553333;">{e}</small>
                </div>
                """, unsafe_allow_html=True)
                st.stop()

        # ─────────────────────────────────────────
        # 结果展示区
        # ─────────────────────────────────────────
        tone     = profile.get('tone', 'roast')
        label    = profile.get('label_en' if lang == 'en' else 'label', '未知实体')
        strategy = profile.get('strategy_en' if lang == 'en' else 'strategy', '')
        evidence = profile.get('evidence', {})
        is_bot   = profile.get('is_bot', False)

        # ── Bot 拦截页面 ──────────────────────────────
        if is_bot:
            tx_24h  = evidence.get('transactions_last_24h', '?')
            hold_s  = evidence.get('avg_hold_time_seconds', '?')
            addr_short = f"{address[:8]}...{address[-6:]}"
            st.markdown(f"""
            <div style="text-align:center; padding:48px 0;">
              <div style="font-family:'Orbitron',monospace; font-size:2rem; font-weight:900;
                          color:#ff9900; text-shadow:0 0 24px #ff990088; letter-spacing:4px;">
                🤖 NON-HUMAN DETECTED
              </div>
              <div style="font-family:'Share Tech Mono',monospace; font-size:0.9rem;
                          color:#664400; margin-top:16px; letter-spacing:2px;">
                TARGET :: <span style="color:#ff9900;">{addr_short}</span>
              </div>
              <div style="margin-top:32px; display:inline-block;
                          border:2px solid #ff9900; border-radius:8px;
                          padding:24px 40px; background:#1a0e00;
                          box-shadow:0 0 40px #ff990033;">
                <div style="font-family:'Orbitron',monospace; font-size:1.1rem;
                            color:#ff9900; letter-spacing:3px; margin-bottom:16px;">
                  ⚠ AUDIT_REFUSED
                </div>
                <div style="font-family:'Share Tech Mono',monospace; font-size:0.95rem;
                            color:#cc7700; line-height:2;">
                  检测到非人类操作频率<br/>
                  24h 交易次数：<span style="color:#ff9900;">{tx_24h} 次</span>
                  &nbsp;|&nbsp; 平均持仓：<span style="color:#ff9900;">{hold_s} 秒</span><br/>
                  <span style="color:#664400; font-size:0.8rem;">本系统仅对人类交易者进行心理审计。</span>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)
            st.stop()
        # ─────────────────────────────────────────────

        # 地址概览
        addr_short = f"{address[:8]}...{address[-6:]}"
        st.markdown(f"""
        <div style="text-align:center; font-family:'Share Tech Mono',monospace;
                    color:#334433; font-size:0.85rem; padding: 8px 0 16px 0;">
          TARGET_LOCKED :: <span style="color:#00aa55;">{addr_short}</span>
          &nbsp;|&nbsp; STATUS :: <span style="color:#{'00ff88' if tone=='praise' else 'ff4444'};">{'ELITE ▲' if tone=='praise' else 'REKT ▼'}</span>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns([1, 2])

        # ── 左侧：硬核情报 ──────────────────────────
        with col1:
            st.markdown(
                f"""
                <div style="
                    background:#121417;
                    border:1px solid #3a3f46;
                    border-left:5px solid #8b929c;
                    border-radius:6px;
                    padding:10px 12px;
                    margin-bottom:12px;
                    box-shadow:0 0 18px #00000055;
                ">
                  <div style="color:#9aa1ab; font-size:0.86rem; font-weight:700; letter-spacing:0.5px;">
                    {T['slice_title']}
                  </div>
                  <div style="color:#6e7681; font-size:0.74rem; margin-top:4px;">
                    {T['slice_sub']}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown(f"""
            <div class="label-card">
              <div style="color:#334433; font-size:0.7rem; letter-spacing:3px; margin-bottom:8px;">IDENTITY_CLASS</div>
              <div class="label-title">{label}</div>
              <div style="color:#334433; font-size:0.8rem; margin-top:10px;">{strategy}</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div style="color:#334433; font-size:0.7rem; letter-spacing:3px; margin-bottom:8px;">CHAIN_EVIDENCE</div>
            """, unsafe_allow_html=True)

            if evidence:
                rows_html = ''
                for k, v in evidence.items():
                    if k == '备注':
                        continue
                    rows_html += f"""
                    <div class="evidence-row">
                      <span class="evidence-key">{k}</span>
                      <span class="evidence-value">{v}</span>
                    </div>
                    """
                # 备注单独放最后
                if '备注' in evidence:
                    remark = evidence['备注']
                    rows_html += f"""
                    <div style="margin-top:12px; padding:10px; background:#0d150d;
                                border-left:2px solid #334433; font-size:0.8rem; color:#556655;">
                      // {remark}
                    </div>
                    """
                st.markdown(f"""
                <div style="background:#0a140a; border:1px solid #1a2e1a;
                            border-radius:6px; padding:16px 20px;">
                  {rows_html}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("<span style='color:#334433;'>// 暂无可用链上证据</span>", unsafe_allow_html=True)

        # ── 右侧：AI 审判 ────────────────────────────
        with col2:
            if tone == 'praise':
                stamp_html = """
                <div style="position:relative; display:inline-block; margin-bottom:10px;">
                  <span style="font-family:'Orbitron',monospace; font-size:1.5rem; font-weight:900;
                              color:#00e07a; border:3px solid #00e07a; border-radius:4px;
                              padding:2px 14px; letter-spacing:4px; opacity:0.85;
                              text-shadow:0 0 12px #00e07a88;">
                    ✅ APPROVED
                  </span>
                </div>"""
                header_html = f"""
                {stamp_html}
                <div style="font-family:'Orbitron',monospace; font-size:0.75rem;
                            color:#00e07a; letter-spacing:3px; margin-bottom:16px; margin-top:8px;">
                  🏆 DEGEN_AUDIT :: ELITE_PROFILE_DETECTED
                </div>
                """
                box_class  = 'praise-box'
                text_class = 'praise-text'
            else:
                stamp_html = """
                <div style="position:relative; display:inline-block; margin-bottom:10px;">
                  <span style="font-family:'Orbitron',monospace; font-size:1.5rem; font-weight:900;
                              color:#ff3333; border:3px solid #ff3333; border-radius:4px;
                              padding:2px 14px; letter-spacing:4px; opacity:0.85;
                              text-shadow:0 0 12px #ff333388;">
                    ✗ REJECTED
                  </span>
                </div>"""
                header_html = f"""
                {stamp_html}
                <div style="font-family:'Orbitron',monospace; font-size:0.75rem;
                            color:#ff4444; letter-spacing:3px; margin-bottom:16px; margin-top:8px;">
                  💀 DEGEN_AUDIT :: REKT_PATTERN_CONFIRMED
                </div>
                """
                box_class  = 'roast-box'
                text_class = 'roast-text'

            st.markdown(f"""
            {header_html}
            <div class="{box_class}">
              <div class="{text_class}">{ai_comment}</div>
            </div>
            """, unsafe_allow_html=True)

            # 原始数据折叠展示
            with st.expander("🗂️  RAW_DATA :: 查看完整链上切片"):
                display_fields = {
                    '24h 交易次数':    stats.get('transactions_last_24h', 'N/A'),
                    '平均持仓时长':    f"{stats.get('avg_hold_time_seconds') or stats.get('avg_hold_minutes', 0)} {'秒' if stats.get('avg_hold_time_seconds') else '分钟'}",
                    '月交易次数':      stats.get('monthly_tx_count', 'N/A'),
                    '日均交易次数':    stats.get('daily_tx_count', 'N/A'),
                    '平台偏好':        stats.get('platform_preference', 'N/A'),
                    '土狗 Mint 多样性': stats.get('token_diversity_count', 'N/A'),
                    '最大单笔交易':    f"${(stats.get('max_single_tx_usd') or 0):,.0f}",
                    '单笔平均金额':    f"${(stats.get('avg_tx_amount_usd') or 0):.2f}",
                    '稳定币+主流币占比': f"{(stats.get('stable_major_ratio') or 0)*100:.0f}%",
                    '最大浮亏':        f"{stats.get('max_unrealized_loss_pct') or 0}%",
                    '遭遇貔貅次数':    stats.get('honeypot_count', 0),
                    '被MEV夹次数':     stats.get('mev_sandwich_count', 0),
                    'Gas费/总资产':     f"{(stats.get('gas_fee_ratio') or 0)*100:.1f}%",
                    '空投收益':        f"${(stats.get('airdrop_received_usd') or 0):,.0f}",
                    '跨链桥使用次数':  stats.get('cross_chain_count', 'N/A'),
                }
                rows = ''.join(
                    f"""
                    <div style='display:flex; justify-content:space-between;
                                padding:6px 0; border-bottom:1px solid #1a2e1a;
                                font-size:0.85rem;'>
                      <span style='color:#556655;'>{k}</span>
                      <span style='color:#00ff88;'>{v}</span>
                    </div>
                    """
                    for k, v in display_fields.items()
                )
                st.markdown(
                    f"<div style='font-family:Share Tech Mono,monospace; background:#0a140a;"
                    f"border:1px solid #1a2e1a; border-radius:6px; padding:16px 20px;'>{rows}</div>",
                    unsafe_allow_html=True
                )


# ─────────────────────────────────────────────
# 底部免责声明
# ─────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center; color:#2a3a2a; font-size:0.72rem; "
    "font-family:Share Tech Mono,monospace; padding:8px 0 24px 0;'>"
    + T["disclaimer"] +
    "</div>",
    unsafe_allow_html=True
)    