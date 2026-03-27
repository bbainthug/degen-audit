# 💀 Degen Audit | On-chain AI Profiler 

[🇺🇸 English Version](#-english-version) | [🇨🇳 中文版阅读](#-中文版)

---

## 🇺🇸 English Version

**An AI-powered ruthless roasting machine for Solana degenerates.**

Stop pretending to be a whale. `Degen Audit` pulls your real on-chain trading behavior via Helius RPC, bypasses LLM hallucinations, and exposes your true trading psychology with zero sugar-coating.

### 🔗 Live Demo
[👉 Try it here on Streamlit] (https://degenaudit.streamlit.app/)

### 🩸 Why I Built This?
In the current Web3 landscape, most wallet trackers only show boring PnL (Profit and Loss). They fail to capture the **"Vibe"** and the actual psychological state of a trader. Furthermore, direct LLM analysis on blockchain data often leads to severe hallucinations (e.g., faking transaction counts).

**My Solution:**
1. **Data Dimensionality Reduction:** Instead of a flawed 24-hour snapshot, the engine strictly fetches the **Last 100 Transactions**.
2. **Context Override:** Python backend handles the core logic (Win rate, Tx density, Holding time). The AI (Llama 3.3) is stripped of its reasoning power and forced to act purely as a "Crypto Twitter Slang Translator", ensuring 100% data accuracy while maximizing the roasting impact.

### 🛠️ Tech Stack
- **Backend & UI:** Python, Streamlit
- **On-chain Data:** Helius RPC API (Solana)
- **AI Engine:** Llama-3.3-70B-Instruct (via Nvidia NIM API)
- **Prompt Engineering:** Strict Persona Injection & Logic Separation

### 🔪 Core Features
- **Wallet X-Ray:** Rapidly scans a Solana address.
- **Vibe Classification:** Automatically categorizes addresses into distinct archetypes (e.g., "Diamond Hands", "Cyber Beggar", "Insider Rat").
- **Ruthless Roasting:** Generates brutally honest, highly contextualized CT (Crypto Twitter) style critiques. 

### ⚠️ Disclaimer
This is an MVP. Not financial advice. Strictly for entertainment and behavioral analysis. Your API keys are NOT stored.

---

## 🇨🇳 中文版

**一台专为 Solana 赌狗量身定制的 AI 无情嘲讽机。**

别装巨鲸了。`Degen Audit` 通过 Helius RPC 强行扒下你的链上底裤，绕过大模型幻觉，用最极客的方式暴击你的真实交易心理。

### 🔗 在线体验
[👉 点击此处在 Streamlit 体验] (https://degenaudit.streamlit.app/)

### 🩸 为什么做这个破玩意儿？
当下的 Web3 追踪工具全在盯着干瘪的 PnL 数据，根本抓不住交易者真实的“情绪 Vibe”和心理状态。更致命的是，让大模型直接读链上脏数据，会导致极其严重的 AI 幻觉（比如凭空捏造交易次数）。

**我的降维打击方案:**
1. **数据降维:** 抛弃虚假的 24 小时快照，强行锁定**最近 100 笔交易**提取特征。
2. **上下文接管:** Python 后端强行接管胜率、频率等核心逻辑算力，剥夺 AI 的推理权，将其降级为“推特黑话翻译器”，彻底斩断幻觉。

### 🛠️ 硬核技术栈
- **后端 & UI:** Python, Streamlit
- **链上节点:** Helius RPC API (Solana)
- **大模型算力:** Llama-3.3-70B-Instruct (基于 Nvidia NIM API)
- **提示词工程:** 强人设注入与逻辑剥离

### 🔪 核心杀器
- **钱包透视:** 光速解析 Solana 脏数据。
- **属性开盒:** 精准打上“钻石手”、“赛博乞丐”、“内幕老鼠”等标签。
- **破防暴击:** 生成极具 CT (Crypto Twitter) 攻击性的专属嘲讽报告。

### ⚠️ 免责声明
极客玩具，非投资建议。你的任何 API 凭证均不会被保留或上传。
