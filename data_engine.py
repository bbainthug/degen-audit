import json
import os
import random
import time
from collections import Counter
from statistics import mean
from typing import Dict, List

import requests

from dotenv import load_dotenv
load_dotenv()

# 🛡️ 兼容 Streamlit 云端 Secrets + 本地 .env
def _get_helius_key() -> str:
    try:
        import streamlit as st
        key = st.secrets.get("HELIUS_API_KEY") or os.getenv('HELIUS_API_KEY', '')
    except Exception:
        key = os.getenv('HELIUS_API_KEY', '')
    return (key or '').strip()

# 🌐 智能代理：本地有代理就用，云端直连
def _get_proxies() -> dict:
    proxy_url = "http://127.0.0.1:7891"
    try:
        import socket
        s = socket.create_connection(("127.0.0.1", 7891), timeout=0.3)
        s.close()
        return {"http": proxy_url, "https": proxy_url}
    except Exception:
        return {}

# ─────────────────────────────────────────────
# 代币池
# ─────────────────────────────────────────────
MEME_TOKENS   = ['BONK', 'WIF', 'POPCAT', 'MYRO', 'BOME', 'SLERF', 'MOODENG', 'PNUT']
MAJOR_TOKENS  = ['SOL', 'ETH', 'BTC', 'BNB', 'AVAX']
STABLE_TOKENS = ['USDC', 'USDT', 'DAI', 'BUSD']
DEFI_TOKENS   = ['RAY', 'ORCA', 'JTO', 'JUP', 'PYTH']
OLD_TOKENS    = ['EOS', 'ADA', 'LTC', 'XRP', 'TRX']
ALL_TOKENS    = MEME_TOKENS + MAJOR_TOKENS + STABLE_TOKENS + DEFI_TOKENS


def _call_helius(rpc_method: str, params: List):
    """Helius RPC 调用（requests + 固定本地代理）。"""
    api_key = _get_helius_key()
    if not api_key:
        return None

    url = f"https://mainnet.helius-rpc.com/?api-key={api_key}"
    payload = {
        'jsonrpc': '2.0',
        'id': 'alphaclaw',
        'method': rpc_method,
        'params': params,
    }

    proxies = _get_proxies()

    try:
        response = requests.post(
            url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            proxies=proxies,
            timeout=10,
        )
        response.raise_for_status()
        parsed = response.json()
        return parsed.get('result')
    except (requests.RequestException, ValueError):
        return None


def _get_helius_base_stats(wallet_address: str) -> Dict:
    """
    尝试从 Helius 拿最基础的真实数据：
    - 余额（lamports）
    - 最近签名数量（短窗口活跃度）
    """
    balance_result = _call_helius('getBalance', [wallet_address])
    sigs_result = _call_helius('getSignaturesForAddress', [wallet_address, {'limit': 100}])

    lamports = None
    if isinstance(balance_result, dict):
        lamports = balance_result.get('value')

    tx_count_100 = len(sigs_result) if isinstance(sigs_result, list) else None

    return {
        'helius_lamports': lamports,
        'helius_recent_tx_count_100': tx_count_100,
    }


def _fetch_helius_transactions(wallet_address: str, limit: int = 100) -> List[Dict]:
    """Helius Enhanced API: 拉取地址交易明细，支持翻页拉取多页。"""
    api_key = _get_helius_key()
    if not api_key:
        return []

    url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/transactions"
    proxies = _get_proxies()

    all_txs = []
    before = None
    per_page = min(100, limit)

    while len(all_txs) < limit:
        params = {"api-key": api_key, "limit": per_page}
        if before:
            params["before"] = before
        try:
            r = requests.get(url, params=params, proxies=proxies, timeout=12)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, list) or not data:
                break
            all_txs.extend(data)
            if len(data) < per_page:
                break  # 没有更多数据
            before = data[-1].get('signature')
            if not before:
                break
        except (requests.RequestException, ValueError):
            break

    return all_txs[:limit]


def _filter_trading_txs(txs: List[Dict]) -> List[Dict]:
    """
    从全量交易中过滤出「打狗/交易」相关的交易：
    1. type == SWAP
    2. type == TRANSFER 且有 tokenTransfers（SPL token转账，含买卖行为）
    3. 排除纯 SOL 系统转账（type==TRANSFER 且 tokenTransfers 为空）
    """
    result = []
    for tx in txs:
        tx_type = str(tx.get('type', '')).upper()
        has_token_transfers = bool(tx.get('tokenTransfers'))
        if tx_type == 'SWAP':
            result.append(tx)
        elif tx_type in ('TRANSFER', 'TOKEN_MINT', 'BURN') and has_token_transfers:
            result.append(tx)
    return result


def _count_24h_from_txs(txs: List[Dict]) -> tuple:
    """
    用已拉取的100笔交易判断24h交易量，不额外请求API。
    逻辑：
      - 100笔全在24h内 且 avg_gap < 3秒 → 机器人嫌疑，返回 (100, True)
      - 100笔全在24h内 但 avg_gap >= 3秒 → 人类高频，返回 (100, False)
      - 不全在24h内             → 数实际笔数，返回 (count, False)
    """
    cutoff = int(time.time()) - 86400
    count = 0
    times = []
    for tx in txs:
        ts = int(tx.get('timestamp') or tx.get('blockTime') or 0)
        if ts >= cutoff:
            count += 1
            if ts > 0:
                times.append(ts)
        else:
            # 遇到24h外的交易，说明100笔没有全覆盖在24h内
            return count, False

    # 100笔全在24h内，再看平均间隔判断是否为机器人
    # 用 span/count 而非 span/(len(times)-1)，避免timestamp缺失导致times过少
    if len(times) >= 2:
        times_sorted = sorted(times)
        span = times_sorted[-1] - times_sorted[0]
        # 用总笔数(count)做分母，而不是有效时间戳数
        avg_gap = span / max(1, count - 1)
    else:
        # 时间戳全部缺失，无法判断，保守处理为非Bot
        avg_gap = 999

    is_bot = avg_gap < 3  # 平均间隔<3秒才判定为机器人
    return count, is_bot


def _calc_pnl_from_txs(wallet_address: str, txs: List[Dict]) -> Dict:
    """
    按 mint 配对计算真实盈亏。
    方法：
      - 每个 mint 单独核算：买入时 SOL 流出为成本，卖出时 SOL 流入为收入
      - 通过 nativeTransfers 追踪 SOL 进出，tokenTransfers 确定是哪个 mint 在交易
      - 一个 mint 的所有买入卖出结算完后，正值=盈利，负值=亏损
    返回: { 'realized_pnl_sol', 'win_count', 'lose_count', 'win_rate',
             'avg_win_sol', 'avg_lose_sol', 'total_pnl_trades' }
    """
    wallet_lower = wallet_address.lower()

    # mint -> {'cost': lamports买入花费, 'revenue': lamports卖出收入, 'buy_ts': 首次买入时间, 'sell_ts': 最近卖出时间}
    mint_ledger: dict = {}

    # 按时间正序处理
    sorted_txs = sorted(txs, key=lambda t: int(t.get('timestamp') or t.get('blockTime') or 0))

    for tx in sorted_txs:
        ts = int(tx.get('timestamp') or tx.get('blockTime') or 0)
        fee = int(tx.get('fee') or 0)
        native_transfers = tx.get('nativeTransfers') or []
        token_transfers  = tx.get('tokenTransfers') or []

        # 找出本交易涉及的 mint（非主流币）
        core = set(MAJOR_TOKENS + STABLE_TOKENS + DEFI_TOKENS)
        involved_mints = set()
        for tt in token_transfers:
            mint = (tt.get('mint') or '').strip()
            if mint and mint not in core:
                involved_mints.add(mint)

        if not involved_mints:
            continue  # 纯 SOL 转账，跳过

        # 统计本 tx 中钱包的 SOL 净变化
        sol_net = 0
        for nt in native_transfers:
            amt = int(nt.get('amount') or 0)
            frm = str(nt.get('fromUserAccount') or '').lower()
            to  = str(nt.get('toUserAccount') or '').lower()
            if to == wallet_lower:
                sol_net += amt
            elif frm == wallet_lower:
                sol_net -= amt
        sol_net -= fee  # 扣手续费

        # 判断买入还是卖出：sol_net < 0 = 买入（花 SOL 买代币），sol_net > 0 = 卖出（卖代币收 SOL）
        for mint in involved_mints:
            if mint not in mint_ledger:
                mint_ledger[mint] = {'cost': 0, 'revenue': 0, 'buy_ts': 0, 'sell_ts': 0, 'buys': 0, 'sells': 0}
            entry = mint_ledger[mint]
            if sol_net < 0:  # 买入
                entry['cost'] += abs(sol_net)
                entry['buys'] += 1
                if entry['buy_ts'] == 0:
                    entry['buy_ts'] = ts
            elif sol_net > 0:  # 卖出
                entry['revenue'] += sol_net
                entry['sells'] += 1
                entry['sell_ts'] = ts

    # 结算每个 mint
    win_count = 0
    lose_count = 0
    win_pnl = 0
    lose_pnl = 0
    total_pnl = 0
    hold_durations = []

    for mint, entry in mint_ledger.items():
        if entry['cost'] == 0 and entry['revenue'] == 0:
            continue
        # 只统计有卖出记录的（已实现盈亏）
        if entry['sells'] == 0:
            continue
        pnl = entry['revenue'] - entry['cost']
        total_pnl += pnl
        if pnl > 100_000:  # > 0.0001 SOL 算盈利
            win_count += 1
            win_pnl += pnl
        elif pnl < -100_000:
            lose_count += 1
            lose_pnl += pnl
        # 持仓时间
        if entry['buy_ts'] > 0 and entry['sell_ts'] > entry['buy_ts']:
            hold_durations.append(entry['sell_ts'] - entry['buy_ts'])

    total_trades = win_count + lose_count
    win_rate = round(win_count / total_trades * 100, 1) if total_trades > 0 else 0.0
    realized_pnl_sol = round(total_pnl / 1e9, 4)
    avg_win_sol  = round(win_pnl  / max(1, win_count)  / 1e9, 4)
    avg_lose_sol = round(lose_pnl / max(1, lose_count) / 1e9, 4)
    avg_hold_sec = int(sum(hold_durations) / len(hold_durations)) if hold_durations else 0

    return {
        'realized_pnl_sol': realized_pnl_sol,
        'win_count': win_count,
        'lose_count': lose_count,
        'win_rate': win_rate,
        'avg_win_sol': avg_win_sol,
        'avg_lose_sol': avg_lose_sol,
        'total_pnl_trades': total_trades,
        'pnl_avg_hold_sec': avg_hold_sec,  # 从盈亏配对算出的持仓时间
    }


def _estimate_daily_tx_count(wallet_address: str, recent_tx_count_100: int) -> int:
    """
    通过最近100笔交易的时间跨度估算真实24h交易频率。
    如果100笔都在1小时内，说明是超高频Bot，按比例外推。
    """
    api_key = _get_helius_key()
    if not api_key or not recent_tx_count_100:
        return recent_tx_count_100 or 0

    url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/transactions"
    proxies = _get_proxies()
    try:
        r = requests.get(url, params={"api-key": api_key, "limit": 100},
                         proxies=proxies, timeout=12)
        r.raise_for_status()
        txs = r.json()
        if not isinstance(txs, list) or len(txs) < 2:
            return recent_tx_count_100
        times = sorted([int(tx.get('timestamp') or tx.get('blockTime') or 0)
                        for tx in txs if tx.get('timestamp') or tx.get('blockTime')],
                       reverse=True)
        if len(times) < 2:
            return recent_tx_count_100
        span_seconds = max(1, times[0] - times[-1])
        # 外推到24h
        estimated = int(len(times) / span_seconds * 86400)
        return estimated
    except Exception:
        return recent_tx_count_100


def _derive_real_metrics(wallet_address: str, txs: List[Dict], lamports: int | None) -> Dict:
    """从真实交易明细中提取行为指纹指标（不计算 Win Rate / PnL）。"""
    if not txs:
        return {}

    now = int(time.time())
    ts_24h = now - 24 * 3600

    def _tx_time(tx: Dict) -> int:
        return int(tx.get('timestamp') or tx.get('blockTime') or 0)

    recent_100 = txs[:100]  # 全量100笔
    trading_txs = _filter_trading_txs(recent_100)  # 过滤出代币交易

    # ── 时间密度（100笔脚印核心指标）──
    all_times = sorted([_tx_time(t) for t in recent_100 if _tx_time(t) > 0])
    if len(all_times) >= 2:
        span_seconds = all_times[-1] - all_times[0]   # 100笔跨越的总秒数
        avg_interval_seconds = span_seconds // max(1, len(all_times) - 1)  # 平均每笔间隔
    else:
        span_seconds = 0
        avg_interval_seconds = 3600

    span_hours = round(span_seconds / 3600, 1)  # 100笔花了多少小时

    # 1) 过去 24 小时交易次数：只数代币交易
    transactions_last_24h, is_likely_bot = _count_24h_from_txs(trading_txs if trading_txs else recent_100)
    if not recent_100:
        transactions_last_24h, is_likely_bot = 0, False

    # 2) 最近 100 笔平均持仓秒数
    # 正确做法：匹配同一 mint 的买入→卖出时间差，取平均（只用打狗交易）
    mint_buy_time: dict = {}   # mint -> 最近一次买入时间
    hold_durations = []
    for tx in sorted(trading_txs, key=_tx_time):  # 按时间正序
        ts = _tx_time(tx)
        if ts == 0:
            continue
        transfers = tx.get('tokenTransfers') or []
        for tt in transfers:
            mint = (tt.get('mint') or '').strip()
            if not mint:  # 跳过空mint，避免误匹配
                continue
            frm = str(tt.get('fromUserAccount') or '').lower()
            to  = str(tt.get('toUserAccount') or '').lower()
            wallet_l = wallet_address.lower()
            if to == wallet_l:   # 买入：记录买入时间
                mint_buy_time[mint] = ts
            elif frm == wallet_l and mint in mint_buy_time:  # 卖出：计算持仓
                duration = ts - mint_buy_time.pop(mint)
                if duration > 0:  # 排除同秒买卖
                    hold_durations.append(duration)
    if hold_durations:
        avg_hold_time_seconds = max(1, int(sum(hold_durations) / len(hold_durations)))
    else:
        # tokenTransfers为空（纯SOL转账地址）或无完整买卖对，使用保守默认值
        tx_times = sorted([_tx_time(t) for t in recent_100 if _tx_time(t) > 0])
        if len(tx_times) >= 2:
            span_total = tx_times[-1] - tx_times[0]
            avg_hold_time_seconds = max(300, span_total // max(1, len(tx_times) - 1))
        else:
            avg_hold_time_seconds = 3600

    # 3) 最近 100 笔土狗币多样性（Mint 去重）+ 交易逻辑维度
    core_tokens = set(MAJOR_TOKENS + STABLE_TOKENS + DEFI_TOKENS)
    dog_mints = set()
    token_tx_counter = Counter()   # 每个 mint 被交易多少次
    buy_count = 0
    sell_count = 0
    seen_mints_order = []          # 按出现顺序记录 mint，用于新币比例
    seen_set = set()

    for tx in trading_txs:
        transfers = tx.get('tokenTransfers') or []
        tx_type = str(tx.get('type', '')).lower()
        is_sell = 'sell' in tx_type or any(
            str(tt.get('fromUserAccount') or '').lower() == wallet_address.lower()
            for tt in transfers
        )
        for tt in transfers:
            mint = (tt.get('mint') or '').strip()
            symbol = (tt.get('symbol') or '').upper().strip()
            if not mint:
                continue
            if symbol and symbol in core_tokens:
                continue
            dog_mints.add(mint)
            token_tx_counter[mint] += 1
            if mint not in seen_set:
                seen_set.add(mint)
                seen_mints_order.append(mint)
        # 粗略统计买卖方向（swap = 买；sell/transfer out = 卖）
        if is_sell:
            sell_count += 1
        else:
            buy_count += 1

    token_diversity_count = len(dog_mints)

    # 重复交易比例：TOP1 代币交易次数 / 总交易笔数
    # 高 → 同一个盘子反复刷；低 → 每次换新盘
    top_token_repeat = 0
    repeat_token_ratio = 0.0
    if token_tx_counter and len(trading_txs) > 0:
        top_token_repeat = token_tx_counter.most_common(1)[0][1]
        # 用 token_diversity 去重后的总交互次数做分母，避免超过1
        total_token_interactions = sum(token_tx_counter.values())
        repeat_token_ratio = round(top_token_repeat / max(1, total_token_interactions), 3)

    # 买卖比例：buy_count / total（接近1=只买不卖；~0.5=正常差价）
    total_dir = buy_count + sell_count
    buy_sell_ratio = round(buy_count / total_dir, 3) if total_dir > 0 else 0.5

    # 新币比例：每次交易是否是从未见过的新 mint（首次出现比例）
    # 高 → 专冲新盘；低 → 老盘反复
    new_token_ratio = round(len(seen_mints_order) / max(1, token_diversity_count + 1), 3)

    # 4) 平台偏好（多平台识别）— 只看打狗交易
    platform_scores: dict = {}
    platform_keywords = {
        'Pump.fun':  ['pump'],
        'Raydium':   ['raydium'],
        'Meteora':   ['meteora'],
        'Jupiter':   ['jupiter'],
        'Orca':      ['orca', 'whirlpool'],
        'Moonshot':  ['moonshot'],
        'Drift':     ['drift'],
        'SPL':       ['solana_program_library', 'spl'],
    }
    for tx in trading_txs:
        source = str(tx.get('source', '')).lower()
        raw_str = str(tx.get('description', '') or '').lower()
        matched = False
        for pname, kws in platform_keywords.items():
            if any(kw in source or kw in raw_str for kw in kws):
                platform_scores[pname] = platform_scores.get(pname, 0) + 1
                matched = True
                break
        if not matched:
            platform_scores['Other'] = platform_scores.get('Other', 0) + 1

    if platform_scores:
        platform_preference = max(platform_scores, key=platform_scores.get)
        # 如果最高平台占比不到40%，标记为Mixed
        top_count = platform_scores[platform_preference]
        if top_count / max(1, len(trading_txs)) < 0.4:
            platform_preference = 'Mixed'
    else:
        platform_preference = 'Mixed'

    # 保留 TOP token，方便 evidence 文案引用（只看打狗交易）
    token_counter = Counter()
    for tx in trading_txs:
        for tt in tx.get('tokenTransfers') or []:
            symbol = (tt.get('symbol') or '').strip()
            mint = (tt.get('mint') or '').strip()
            token = symbol if symbol else mint
            if token:
                token_counter[token] += 1

    frequent_tokens = [t for t, _ in token_counter.most_common(3)]
    if len(frequent_tokens) < 3:
        for fb in ['SOL', 'USDC', 'USDT']:
            if fb not in frequent_tokens:
                frequent_tokens.append(fb)
            if len(frequent_tokens) == 3:
                break

    # 盈亏计算（用全量交易，按mint配对）
    pnl = _calc_pnl_from_txs(wallet_address, recent_100)
    # 如果 pnl 算出了持仓时间，用它覆盖之前的估算
    if pnl.get('pnl_avg_hold_sec') and pnl['pnl_avg_hold_sec'] > 0:
        avg_hold_time_seconds = pnl['pnl_avg_hold_sec']

    return {
        'data_source': 'helius-real',
        'helius_lamports': lamports,
        'helius_recent_tx_count_100': min(100, len(recent_100)),
        'transactions_last_24h': transactions_last_24h,
        'is_likely_bot': is_likely_bot,
        'avg_hold_time_seconds': avg_hold_time_seconds,
        'span_hours': span_hours,             # 100笔横跨多少小时
        'avg_interval_seconds': avg_interval_seconds,  # 平均每笔间隔秒数
        'token_diversity_count': token_diversity_count,
        'platform_preference': platform_preference,
        'frequent_tokens': frequent_tokens,
        # 交易逻辑维度
        'repeat_token_ratio': repeat_token_ratio,
        'buy_sell_ratio': buy_sell_ratio,
        'top_token_repeat': top_token_repeat,
        'new_token_ratio': new_token_ratio,
        # 盈亏维度
        'realized_pnl_sol': pnl['realized_pnl_sol'],
        'win_count': pnl['win_count'],
        'lose_count': pnl['lose_count'],
        'win_rate': pnl['win_rate'],
        'avg_win_sol': pnl['avg_win_sol'],
        'avg_lose_sol': pnl['avg_lose_sol'],
        'total_pnl_trades': pnl['total_pnl_trades'],
        # pnl 数据可靠性：至少需要5笔有买有卖的配对才可信
        'pnl_reliable': pnl['total_pnl_trades'] >= 5 and pnl['win_count'] > 0 and pnl['lose_count'] > 0,

        # 与 UI 兼容字段
        'avg_hold_minutes': max(1, avg_hold_time_seconds // 60),
        'monthly_tx_count': len(trading_txs),    # 代币交易笔数
        'daily_tx_count': transactions_last_24h,  # 24h代币交易

        # 计算单笔 SOL 转出金额（用全量txs，钱包直接转出的SOL）
        'max_single_tx_usd': 0,   # 需要SOL价格，暂不计算
        'avg_tx_amount_usd': 0.0, # 需要SOL价格，暂不计算
        'max_single_tx_sol': round(max(
            [sum(int(nt.get('amount', 0)) for nt in (tx.get('nativeTransfers') or [])
              if str(nt.get('fromUserAccount', '')).lower() == wallet_address.lower())
             for tx in recent_100] or [0]
        ) / 1e9, 3),
        'avg_tx_sol': round(
            sum(
                sum(int(nt.get('amount', 0)) for nt in (tx.get('nativeTransfers') or [])
                    if str(nt.get('fromUserAccount', '')).lower() == wallet_address.lower())
                for tx in recent_100
            ) / max(1, len([tx for tx in recent_100
                if any(str(nt.get('fromUserAccount','')).lower() == wallet_address.lower()
                       and int(nt.get('amount',0)) > 0
                       for nt in (tx.get('nativeTransfers') or []))])) / 1e9, 3
        ),
        'stable_major_ratio': 0.0,
        'max_unrealized_loss_pct': 0,
        'gas_fee_ratio': 0.0,
        'airdrop_received_usd': 0.0,
        'cross_chain_count': 0,
        'token_variety': token_diversity_count,

        # 关闭高风险随机指控项
        'loss_margin_calls': 0,
        'honeypot_count': 0,
        'mev_sandwich_count': 0,
        'approve_drain_count': 0,
        'presale_direct_count': 0,
        'buy_after_500x_ratio': 0.0,
        'loss_24h_after_buy_ratio': 0.0,
        'buy_before_contract_blocks': 99,
        'new_wallet_big_buy': False,
    }


def get_wallet_stats(wallet_address: str) -> Dict:
    """
    获取 Solana 钱包真实链上统计数据（仅支持 Solana 地址）。
    """
    import re
    addr = wallet_address.strip()

    # ── 仅支持 Solana Base58 地址 ──────────────────────
    is_solana = bool(re.fullmatch(r'[1-9A-HJ-NP-Za-km-z]{32,44}', addr))
    if not is_solana:
        raise ValueError(
            f'不支持的地址格式："{addr[:20]}…" — 本工具仅支持 Solana 钱包地址（Base58，32-44位）。')
    # ──────────────────────────────────────────────────

    helius_base = _get_helius_base_stats(addr)
    lamports = helius_base.get('helius_lamports')
    txs = _fetch_helius_transactions(addr, limit=100)

    # 空钱包 / 无交易记录
    if not txs and (lamports is None or lamports == 0):
        raise ValueError(
            '空白钱包或链上无交易记录 — 该地址从未上过链，或最近 100 笔交易为空。请换一个活跃地址。')
    if not txs:
        raise ValueError(
            f'该地址余额约 {lamports/1e9:.4f} SOL，但最近 100 笔交易记录为空，无法生成审计报告。')

    real_metrics = _derive_real_metrics(addr, txs, lamports)
    real_metrics['wallet_address'] = addr
    return real_metrics


def generate_profile(stats: Dict) -> Dict:
    """基于完整 stats 生成侧写结论与证据包。"""
    result = _generate_profile_inner(stats)
    # 统一注入盈亏字段到 evidence，确保 ai_profiler 能读到
    ev = result.get('evidence', {})
    for key in ('realized_pnl_sol', 'win_rate', 'win_count', 'lose_count', 'avg_win_sol', 'avg_lose_sol', 'total_pnl_trades', 'pnl_reliable', 'buy_sell_ratio', 'repeat_token_ratio', 'avg_tx_sol', 'max_single_tx_sol', 'span_hours', 'avg_interval_seconds'):
        if key not in ev and key in stats:
            ev[key] = stats[key]
    result['evidence'] = ev

    # 统一注入英文标签和策略
    _LABEL_EN = {
        '同盘反复刷单机':   'Same-Pool Loop Trader',
        '创世节点':         'Genesis Sniper',
        '暗网收割神明':     'Dark Pool Harvester',
        '破晓狙击手':       'Dawn Sniper',
        '无情机器':         'Ruthless Machine',
        '逃顶魔术师':       'Top Exit Wizard',
        '深海巨鲸':         'Deep Sea Whale',
        'DeFi炼金术士':     'DeFi Alchemist',
        '女巫军阀':         'Sybil Warlord',
        '锚定捍卫者':       'Peg Defender',
        '像素黑手党':       'Pixel Mafia',
        '逆向周期之狼':     'Contrarian Wolf',
        '多空双爆受害者':   'Both-Way Rekt Degen',
        '针尖舞者':         'Needle Dancer',
        '插针燃料':         'Wick Fuel',
        '上头复仇者':       'Tilt Avenger',
        '抗单大帝':         'Diamond Hands Emperor',
        '高位站岗哨兵':     'Top-Buy Bagholder',
        '首发狙击炮灰':     'Launch Snipe Cannon Fodder',
        '貔貅提款机':       'Honeypot ATM',
        '夹子外卖员':       'Sandwich Delivery Boy',
        '归零集邮大师':     'Zero-Bag Collector',
        '打款敢死队':       'YOLO Transfer Squad',
        '阴间作息炒家':     'Graveyard Shift Degen',
        '踏空追高综合征':   'FOMO Chaser Syndrome',
        'Gas费慈善家':      'Gas Fee Philanthropist',
        '被钓鱼的裸奔者':   'Phished Streaker',
        '邪教归零死忠粉':   'Cult Zero Maximalist',
        '本金消失术大师':   'Principal Disappearing Act',
        '高风险赌徒':       'High-Risk Degen Gambler',
        '链上稳定盈利者':   'On-Chain Consistent Winner',
        '🤖 发现链上高频协议 (NON-HUMAN)': '🤖 Non-Human Protocol Detected',
    }
    _STRATEGY_EN = {
        '同盘反复刷单机':   '[Behavior: Same-pool high-freq loop trading — arb bot or mindless aping]',
        '高风险赌徒':       '[Behavior: Wins small, loses big — textbook degen gambler mentality]',
        '链上稳定盈利者':   '[Behavior: Consistent win rate with disciplined strategy]',
        '创世节点':         '[Behavior: Genesis-level sniper — insider or ultra-early deployer]',
        '高位站岗哨兵':     '[Behavior: Buys tops, holds bags — classic exit liquidity]',
        '貔貅提款机':       '[Behavior: Keeps buying honeypots — can\'t sell, only donate]',
        '夹子外卖员':       '[Behavior: Repeatedly sandwiched — free lunch for MEV bots]',
        '抗单大帝':         '[Behavior: Never cuts loss — diamond hands or just paralyzed]',
        '归零集邮大师':     '[Behavior: Collects zero-value tokens like stamps]',
        '上头复仇者':       '[Behavior: Revenge trading after losses — tilt mode activated]',
    }
    lbl = result.get('label', '')
    result['label_en'] = _LABEL_EN.get(lbl, lbl)  # 找不到则原样输出
    strat = result.get('strategy', '')
    # 从strategy里提取核心描述做英文版
    result['strategy_en'] = _STRATEGY_EN.get(lbl, f'[Behavior profile: {_LABEL_EN.get(lbl, lbl)}]')

    return result


def _generate_profile_inner(stats: Dict) -> Dict:
    s = stats

    # 真实统计模式：只使用“行为指纹”指标，不做 Win Rate / PnL 财务审计
    if s.get('data_source') == 'helius-real':
        tx_24h = int(s.get('transactions_last_24h', 0))
        hold_sec = int(s.get('avg_hold_time_seconds', 60))
        diversity = int(s.get('token_diversity_count', 0))
        platform = s.get('platform_preference', 'Mixed')
        repeat_ratio = float(s.get('repeat_token_ratio', 0.0))   # TOP1代币占比
        buy_sell_r   = float(s.get('buy_sell_ratio', 0.5))       # 买入比例
        top_repeat   = int(s.get('top_token_repeat', 0))         # TOP1代币交易次数
        new_tok_r    = float(s.get('new_token_ratio', 0.0))      # 新币比例
        # 盈亏维度
        win_rate_pct    = float(s.get('win_rate', 0.0))
        realized_pnl    = float(s.get('realized_pnl_sol', 0.0))
        win_count       = int(s.get('win_count', 0))
        lose_count      = int(s.get('lose_count', 0))
        avg_win_sol     = float(s.get('avg_win_sol', 0.0))
        avg_lose_sol    = float(s.get('avg_lose_sol', 0.0))
        total_pnl_trades = int(s.get('total_pnl_trades', 0))
        pnl_reliable    = bool(s.get('pnl_reliable', False))

        # 盈亏人格辅助判断（要求至少5笔有效交易，避免数据不足误判）
        is_big_loser         = realized_pnl < -1.0 and lose_count > win_count and total_pnl_trades >= 5
        is_consistent_winner = win_rate_pct >= 60 and win_count >= 5 and realized_pnl > 0 and lose_count > 0  # 必须有亏损才算真胜率
        is_gambler           = avg_lose_sol != 0 and avg_win_sol != 0 and abs(avg_lose_sol) > 2 * abs(avg_win_sol) and lose_count >= 3

        # ── 交易逻辑人格判断 ──────────────────────────────────
        is_single_token_grinder = repeat_ratio > 0.4 and top_repeat >= 10
        is_new_token_hunter = diversity >= 20 and new_tok_r > 0.7
        is_buy_only = buy_sell_r > 0.8 and diversity >= 5
        is_major_swing = platform != 'Pump.fun' and hold_sec >= 300 and diversity < 10
        # 已知系统/主流币地址 → 可读名映射
        _KNOWN_TOKENS = {
            'So11111111111111111111111111111111111111112':  'wSOL（原生SOL）',
            'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v': 'USDC',
            'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB': 'USDT',
            'mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So':  'mSOL',
            'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263': 'BONK',
            'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm': 'WIF',
            'jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL':  'JTO',
            'HZ1JovNiVvGqsvEYFboiu6cOBeaJP6FQZS7C3VqkZXoQ': 'Pyth',
        }
        raw_top = (s.get('frequent_tokens') or ['未知代币'])[0]
        top_token = _KNOWN_TOKENS.get(raw_top, raw_top if len(raw_top) < 12 else f'{raw_top[:6]}…{raw_top[-4:]}（未知土狗）')

        is_likely_bot = s.get('is_likely_bot', False)

        if is_likely_bot or (tx_24h > 500 and hold_sec < 5) or tx_24h >= 1000:
            return {
                'label': '🤖 发现链上高频协议 (NON-HUMAN)',
                'system_label': '【🤖 发现链上高频协议 (NON-HUMAN)】',
                'strategy': '【链上行为拦截：检测到非人类操作频率】',
                'tone': 'roast',
                'is_bot': True,
                'evidence': {
                    'transactions_last_24h': tx_24h,
                    'avg_hold_time_seconds': hold_sec,
                    'token_diversity_count': diversity,
                    'platform_preference': platform,
                    '致命操作': '检测到非人类操作频率，拒绝进行心理审计。',
                    '割肉速度': f'24h 交易 {tx_24h} 次，平均持仓 {hold_sec} 秒',
                    '偏好赛道': '非人类行为，无法分类',
                }
            }
        elif hold_sec < 60 and tx_24h >= 200:
            label = '多巴胺中毒的极速纸手'
            tone = 'roast'
            strategy = '【真实行为侧写：极速纸手 / MEV触手怪倾向】'
        elif is_consistent_winner:
            label = '链上稳定盈利者'
            tone = 'praise'
            strategy = f'【真实行为侧写：胜率 {win_rate_pct:.0f}%，近100笔净盈利 {realized_pnl:.2f} SOL，有策略纪律】'
        elif is_gambler:
            label = '高风险赌徒'
            tone = 'roast'
            strategy = f'【真实行为侧写：平均单笔亏 {abs(avg_lose_sol):.2f} SOL，赢小亏大，典型赌徒心态】'
        elif is_big_loser:
            label = '持续亏损大怨种'
            tone = 'roast'
            strategy = f'【真实行为侧写：近100笔净亏 {abs(realized_pnl):.2f} SOL，败多胜少，给庄家打工】'
        elif is_single_token_grinder:
            label = '同盘反复刷单机'
            tone = 'roast'
            strategy = '【真实行为侧写：单一代币高频刷单，可能是做差价脚本或无脑梭哈】'
        elif is_new_token_hunter and platform == 'Pump.fun':
            label = 'Pump.fun新盘狙击手'
            tone = 'roast'
            strategy = '【真实行为侧写：专冲新发土狗，每次换新盘，典型的土狗猎人】'
        elif is_buy_only and platform == 'Pump.fun':
            label = '貔貅受害常客'
            tone = 'roast'
            strategy = '【真实行为侧写：只买不卖，极可能持续踩貔貅或死扛亏损盘】'
        elif is_major_swing:
            label = '主流币波段选手'
            tone = 'praise'
            strategy = '【真实行为侧写：Raydium/主流币波段，有一定纪律性】'
        elif diversity >= 50:
            label = '链上丐帮集邮大师'
            tone = 'roast'
            strategy = '【真实行为侧写：土狗集邮流】'
        elif platform == 'Raydium' and hold_sec >= 300:
            label = '耐心伏击型交易者'
            tone = 'praise'
            strategy = '【真实行为侧写：Raydium 纪律交易】'
        else:
            label = '高频扫描型交易者'
            tone = 'roast' if hold_sec < 120 else 'praise'
            strategy = '【真实行为侧写：行为驱动中性档】'

        system_label = f"【{label}】"
        return {
            'label': label,
            'system_label': system_label,
            'strategy': strategy,
            'tone': tone,
            'evidence': {
                'transactions_last_24h': tx_24h,
                'avg_hold_time_seconds': hold_sec,
                'token_diversity_count': diversity,
                'platform_preference': platform,
                '致命操作': f"最近100笔主战场是 {top_token}，平台偏好 {platform}",
                '割肉速度': f"平均持仓 {hold_sec} 秒，24h 交易 {tx_24h} 次",
                '偏好赛道': f"近100笔共碰 {diversity} 个土狗 Mint",
                '交易逻辑': f"同盘刷单比 {repeat_ratio:.0%}，买入占比 {buy_sell_r:.0%}，新币比 {new_tok_r:.0%}",
                '盈亏概况': f"近100笔胜率 {win_rate_pct:.0f}%，净盈亏 {realized_pnl:+.2f} SOL（赢{win_count}次/亏{lose_count}次）",
                'realized_pnl_sol': realized_pnl,
                'win_rate': win_rate_pct,
                'win_count': win_count,
                'lose_count': lose_count,
                'avg_win_sol': avg_win_sol,
                'avg_lose_sol': avg_lose_sol,
                '数据源': s.get('data_source'),
            }
        }

    # ════════════════════════════════════════
    # 【夸的角色】优先匹配
    # ════════════════════════════════════════

    # S: 创世节点
    if s['buy_before_contract_blocks'] <= 3 and s['win_rate'] >= 95:
        return {
            'label': '创世节点',
            'strategy': '【策略：创世节点 / 降维内幕收割者】',
            'tone': 'praise',
            'evidence': {
                '首买距合约创建区块数': f"{s['buy_before_contract_blocks']} 个区块",
                '胜率': f"{s['win_rate']}%",
                '备注': '买入时间早于所有公开喊单'
            }
        }

    # O: 暗网收割神明 / 高频套利
    if s['daily_tx_count'] > 500 and s['win_rate'] > 90:
        return {
            'label': '暗网收割神明',
            'strategy': '【策略：暗网收割神明 / 高频套利幽灵】',
            'tone': 'praise',
            'evidence': {
                '日均交易次数': s['daily_tx_count'],
                '胜率': f"{s['win_rate']}%",
                '合约种类': s['contract_variety']
            }
        }

    # K: 破晓狙击手 / 顶级Alpha猎人
    if s['buy_before_pump'] and s['pnl_pct'] > 500 and s['win_rate'] > 40:
        hot_pick = random.choice(['WIF', 'BOME', 'BONK', 'POPCAT'])
        entry_sol = random.randint(8, 60)
        burst_pct = random.randint(120, 680)
        return {
            'label': '破晓狙击手',
            'strategy': '【策略：破晓狙击手 / 顶级 Alpha 猎人】',
            'tone': 'praise',
            'evidence': {
                '致命操作': f"{hot_pick} 刚起量就打进 {entry_sol} SOL，吃到 {burst_pct}% 拉升",
                '割肉速度': f"平均持仓 {s['avg_hold_minutes']} 分钟，回撤不到 8% 就走",
                '偏好赛道': f"专盯新发 Meme 龙头（{hot_pick} / BONK / WIF）",
                '补充证据': f"7D 胜率 {s['win_rate']}%，阶段收益 {s['pnl_pct']}%"
            }
        }

    # L: 无情机器 / 极高盈亏比刺客
    if s['max_single_loss_pct'] < 10 and s['avg_win_pct'] > 50 and s['trade_frequency_stable']:
        return {
            'label': '无情机器',
            'strategy': '【策略：绝对理性的无情机器 / 极高盈亏比刺客】',
            'tone': 'praise',
            'evidence': {
                '单笔最大亏损': f"{s['max_single_loss_pct']}%",
                '平均盈利单收益': f"{s['avg_win_pct']}%",
                '交易频率稳定': '是'
            }
        }

    # M: 逃顶魔术师
    if s['sell_near_top_ratio'] > 0.8 and s['price_drop_after_sell'] > 0.2:
        return {
            'label': '逃顶魔术师',
            'strategy': '【策略：先知级逃顶魔术师 / 庄家底牌偷窥者】',
            'tone': 'praise',
            'evidence': {
                '卖出命中局部最高点比例': f"{s['sell_near_top_ratio']*100:.0f}%",
                '卖出后24h价格下跌': f"{s['price_drop_after_sell']*100:.0f}%"
            }
        }

    # N: 深海巨鲸
    if s['max_single_tx_usd'] > 100000 and s['monthly_tx_count'] < 10 and s['stable_major_ratio'] > 0.6:
        return {
            'label': '深海巨鲸',
            'strategy': '【策略：降维打击的深海巨鲸 / 周期信徒】',
            'tone': 'praise',
            'evidence': {
                '单笔最大交易额': f"${s['max_single_tx_usd']:,.0f}",
                '月交易次数': s['monthly_tx_count'],
                '主流币稳定币占比': f"{s['stable_major_ratio']*100:.0f}%"
            }
        }

    # P: DeFi炼金术士
    if s['lp_interaction_ratio'] > 0.7 and s['impermanent_loss_pct'] < 5:
        return {
            'label': 'DeFi炼金术士',
            'strategy': '【策略：DeFi 炼金术士 / 链上无情印钞机】',
            'tone': 'praise',
            'evidence': {
                'LP合约交互占比': f"{s['lp_interaction_ratio']*100:.0f}%",
                '无常损失': f"{s['impermanent_loss_pct']}%"
            }
        }

    # Q: 女巫军阀
    if s['airdrop_received_usd'] > 50000 and s['avg_tx_amount_usd'] < 5:
        return {
            'label': '女巫军阀',
            'strategy': '【策略：女巫军阀 / 协议国库的合法劫匪】',
            'tone': 'praise',
            'evidence': {
                '空投总收益': f"${s['airdrop_received_usd']:,.0f}",
                '单笔平均金额': f"${s['avg_tx_amount_usd']:.2f}"
            }
        }

    # R: 锚定捍卫者 / 危机秃鹫
    if s['buys_during_panic'] and s['fear_greed_buy_index'] < 20 and s['fear_greed_sell_index'] > 80:
        return {
            'label': '锚定捍卫者',
            'strategy': '【策略：锚定捍卫者 / 嗜血的危机秃鹫】',
            'tone': 'praise',
            'evidence': {
                '买入时恐贪指数': s['fear_greed_buy_index'],
                '卖出时恐贪指数': s['fear_greed_sell_index'],
                '恐慌期大量买入': '是'
            }
        }

    # T: 像素黑手党 / NFT鲸
    if s['total_assets_eth'] > 500 and s['nft_bluechip_ratio'] > 0.9:
        return {
            'label': '像素黑手党',
            'strategy': '【策略：像素黑手党 / Web3 卢浮宫馆长】',
            'tone': 'praise',
            'evidence': {
                '总资产ETH': f"{s['total_assets_eth']:.0f} ETH",
                '蓝筹NFT资产占比': f"{s['nft_bluechip_ratio']*100:.0f}%"
            }
        }

    # U: 逆向周期之狼
    if s['fear_greed_buy_index'] < 25 and s['fear_greed_sell_index'] > 75 and s['avg_hold_days'] > 180:
        return {
            'label': '逆向周期之狼',
            'strategy': '【策略：绝对逆行者 / 嗜血的周期之狼】',
            'tone': 'praise',
            'evidence': {
                '买入时恐贪指数': s['fear_greed_buy_index'],
                '卖出时恐贪指数': s['fear_greed_sell_index'],
                '平均持仓天数': s['avg_hold_days']
            }
        }

    # ════════════════════════════════════════
    # 【第一病区：合约与杠杆赌狗】
    # ════════════════════════════════════════

    # 多空双爆受害者
    if s['consecutive_loss_double_in'] >= 2 and s['avg_hold_minutes'] < 60:
        return {
            'label': '多空双爆受害者',
            'strategy': '【多空双爆受害者】',
            'tone': 'roast',
            'evidence': {
                '连续同币亏损后加倍次数': s['consecutive_loss_double_in'],
                '平均持仓时长': f"{s['avg_hold_minutes']} 分钟",
                '备注': '完美的震荡市明灯，你一买它就跌，你一卖它就涨'
            }
        }

    # 针尖舞者 / 极速秒射流
    if s['avg_hold_seconds'] < 180 and s['win_rate'] > 60 and s['pnl_pct'] < 0:
        return {
            'label': '针尖舞者',
            'strategy': '【针尖舞者 / 极速秒射流】',
            'tone': 'roast',
            'evidence': {
                '平均持仓秒数': s['avg_hold_seconds'],
                '胜率': f"{s['win_rate']}%",
                '总收益': f"{s['pnl_pct']}%",
                '备注': '胜率极高的刮刮乐大师，赚的钱全交了手续费和滑点'
            }
        }

    # 插针燃料 / 爆仓提款机
    if s['max_single_loss_pct'] > 90 and s['avg_hold_minutes'] < 10:
        return {
            'label': '插针燃料',
            'strategy': '【插针燃料 / 爆仓提款机】',
            'tone': 'roast',
            'evidence': {
                '单笔最大亏损': f"{s['max_single_loss_pct']}%",
                '平均持仓时长': f"{s['avg_hold_minutes']} 分钟",
                '备注': '你存在的唯一价值，就是给K线画一根长长的下影线'
            }
        }

    # 上头复仇者
    if s['loss_margin_calls'] >= 3:
        return {
            'label': '上头复仇者',
            'strategy': '【上头复仇者】',
            'tone': 'roast',
            'evidence': {
                '连续亏损后加倍买入次数': s['loss_margin_calls'],
                '备注': '经典的赌徒谬误，市场不欠你钱，但马上会要你的命'
            }
        }

    # 抗单大帝
    if s['max_unrealized_loss_pct'] > 50 and s['still_buying_loser'] and s['sells_during_loss'] == 0:
        return {
            'label': '抗单大帝',
            'strategy': '【抗单大帝】',
            'tone': 'roast',
            'evidence': {
                '最大账面浮亏': f"{s['max_unrealized_loss_pct']}%",
                '浮亏期间卖出次数': 0,
                '还在加仓': '是',
                '备注': '左侧补仓，越补越穿，仓位管理像沉没的泰坦尼克号'
            }
        }

    # 高位站岗哨兵
    if s['top_buy_ratio'] > 0.8:
        bag_token = random.choice(['WIF', 'BOME', 'BONK', 'SLERF'])
        top_entry_sol = random.randint(15, 90)
        drawdown_pct = random.randint(22, 58)
        hold_minutes = random.randint(8, 60)
        return {
            'label': '高位站岗哨兵',
            'strategy': '【高位站岗哨兵】',
            'tone': 'roast',
            'evidence': {
                '致命操作': f"在 {bag_token} 日内最高点附近一把冲进 {top_entry_sol} SOL，原地接盘",
                '割肉速度': f"持仓 {hold_minutes} 分钟后被埋 {drawdown_pct}%，纸手割肉离场",
                '偏好赛道': '只冲土狗 Meme，KTV 嗨完就被庄家按地上摩擦',
                '补充证据': f"高位接盘占比 {s['top_buy_ratio']*100:.0f}%"
            }
        }

    # ════════════════════════════════════════
    # 【第二病区：链上土狗与Meme难民】
    # ════════════════════════════════════════

    # D: 黑暗森林首发狙击炮灰
    if s['avg_token_age_hours'] < 1 and s['win_rate'] < 10 and s['max_single_gain_pct'] > 1000:
        return {
            'label': '首发狙击炮灰',
            'strategy': '【策略：黑暗森林首发狙击炮灰 / 赌狗型伪科学家】',
            'tone': 'roast',
            'evidence': {
                '平均买入币龄': f"{s['avg_token_age_hours']} 小时",
                '胜率': f"{s['win_rate']}%",
                '历史单笔最高收益': f"{s['max_single_gain_pct']}%"
            }
        }

    # 貔貅提款机
    if s['honeypot_count'] > 3:
        trap_token = random.choice(['BABYDOGE2', 'PEPEX', 'DOGEAI', 'FLOKI2'])
        bait_sol = random.randint(3, 25)
        return {
            'label': '貔貅提款机',
            'strategy': '【貔貅提款机 (Honeypot Magnet)】',
            'tone': 'roast',
            'evidence': {
                '致命操作': f"看到 {trap_token} 5分钟暴拉就冲了 {bait_sol} SOL，结果只能买不能卖",
                '割肉速度': f"{s['honeypot_count']} 次被埋，钱包里一堆归零空气币",
                '偏好赛道': '专冲匿名土狗预售盘，长期给项目方送外卖',
                '补充证据': f"归零代币占比 {s['zero_value_token_ratio']*100:.0f}%"
            }
        }

    # 夹子外卖员
    if s['mev_sandwich_count'] > 10:
        return {
            'label': '夹子外卖员',
            'strategy': '【夹子外卖员 (Sandwich Victim)】',
            'tone': 'roast',
            'evidence': {
                '被MEV夹子次数': s['mev_sandwich_count'],
                '备注': '你的每一笔交易都在给黑暗森林里的夹子机器人送外卖'
            }
        }

    # 归零集邮大师
    if s['token_variety'] > 50 and s['zero_value_token_ratio'] > 0.9:
        return {
            'label': '归零集邮大师',
            'strategy': '【归零集邮大师】',
            'tone': 'roast',
            'evidence': {
                '钱包代币种类': s['token_variety'],
                '归零代币占比': f"{s['zero_value_token_ratio']*100:.0f}%",
                '备注': '你的钱包不是金库，是土狗币的赛博坟场'
            }
        }

    # 打款敢死队
    if s['presale_direct_count'] > 5:
        return {
            'label': '打款敢死队',
            'strategy': '【打款敢死队 (Presale Ape)】',
            'tone': 'roast',
            'evidence': {
                '向个人地址打预售次数': s['presale_direct_count'],
                '备注': '蒙着眼睛往黑洞里扔钱，你的信任比Solana的网络还要廉价'
            }
        }

    # 阴间作息炒家
    if 2 <= s['peak_hour_utc8'] <= 6:
        return {
            'label': '阴间作息炒家',
            'strategy': '【阴间作息炒家】',
            'tone': 'roast',
            'evidence': {
                '最活跃交易时段（东八区）': f"{s['peak_hour_utc8']}:00",
                '备注': '熬最深的夜，冲最烂的狗，你的肝和钱包一样千疮百孔'
            }
        }

    # 踏空追高综合征
    if s['buy_after_500x_ratio'] > 0.7 and s['loss_24h_after_buy_ratio'] > 0.6:
        return {
            'label': '踏空追高综合征',
            'strategy': '【踏空追高综合征】',
            'tone': 'roast',
            'evidence': {
                '买入时代币已涨500%+的比例': f"{s['buy_after_500x_ratio']*100:.0f}%",
                '买入后24h亏损比例': f"{s['loss_24h_after_buy_ratio']*100:.0f}%",
                '备注': '你以为是抄底，其实是半山腰接飞刀'
            }
        }

    # Gas费慈善家
    if s['gas_fee_ratio'] > 0.2:
        return {
            'label': 'Gas费慈善家',
            'strategy': '【Gas 费慈善家】',
            'tone': 'roast',
            'evidence': {
                'Gas费占总资产比例': f"{s['gas_fee_ratio']*100:.1f}%",
                '备注': '你交易不是为了赚钱，是为了支持区块链网络建设'
            }
        }

    # 被钓鱼的裸奔者
    if s['approve_drain_count'] > 0:
        return {
            'label': '被钓鱼的裸奔者',
            'strategy': '【被钓鱼的裸奔者】',
            'tone': 'roast',
            'evidence': {
                '被钓鱼授权清仓次数': s['approve_drain_count'],
                '备注': '随便点个链接底裤都被黑客扒光了'
            }
        }

    # ════════════════════════════════════════
    # 【第三病区：价值投资幻觉】
    # ════════════════════════════════════════

    # E: 邪教归零死忠粉
    if s['max_unrealized_loss_pct'] > 90 and s['max_hold_days'] > 30 and s['sells_during_loss'] == 0 and s['still_buying_loser']:
        return {
            'label': '邪教归零死忠粉',
            'strategy': '【策略：邪教式极左侧归零死忠粉 / PUA 深度受害者】',
            'tone': 'roast',
            'evidence': {
                '最大账面浮亏': f"{s['max_unrealized_loss_pct']}%",
                '持仓天数': s['max_hold_days'],
                '浮亏期间卖出次数': 0,
                '还在加仓': '是'
            }
        }

    # 本金消失术大师（质押亏本）
    if s['staking_yield_pct'] > 0 and s['staked_token_drop_pct'] > 80:
        return {
            'label': '本金消失术大师',
            'strategy': '【本金消失术大师】',
            'tone': 'roast',
            'evidence': {
                '质押年化收益': f"{s['staking_yield_pct']}%",
                '质押代币本身跌幅': f"{s['staked_token_drop_pct']}%",
                '备注': '为了图那点利息，把本金全搭进去了，现代版买椟还珠'
            }
        }

    # 无用治理参与者
    if s['dao_vote_count'] > 20 and s['pnl_pct'] < -50:
        return {
            'label': '无用治理参与者',
            'strategy': '【无用治理参与者】',
            'tone': 'roast',
            'evidence': {
                'DAO投票次数': s['dao_vote_count'],
                '总收益': f"{s['pnl_pct']}%",
                '备注': '拿着跌了90%的币去投个毫无卵用的票，体验虚假赛博民主'
            }
        }

    # 天量解锁接盘客
    if s['bought_before_unlock'] and s['loss_24h_after_buy_ratio'] > 0.7:
        return {
            'label': '天量解锁接盘客',
            'strategy': '【天量解锁接盘客】',
            'tone': 'roast',
            'evidence': {
                '大额解锁前买入': '是',
                '买入后24h亏损比例': f"{s['loss_24h_after_buy_ratio']*100:.0f}%",
                '备注': '精准接盘风投机构的抛压，你就是华尔街精英眼里的完美流动性'
            }
        }

    # I: 传统金融遗老
    if s['stable_major_ratio'] > 0.9 and s['avg_token_age_hours'] > 8760 and s['staking_yield_pct'] > 0:
        return {
            'label': '传统金融遗老',
            'strategy': '【策略：传统金融遗老 / 幻觉型无风险套利老农】',
            'tone': 'roast',
            'evidence': {
                '稳定币+主流币占比': f"{s['stable_major_ratio']*100:.0f}%",
                '质押年化': f"{s['staking_yield_pct']}%",
                '近期无高波动交易': '是'
            }
        }

    # 僵尸链守墓人
    if s['main_token_is_old'] and s['last_active_days_ago'] > 180:
        return {
            'label': '僵尸链守墓人',
            'strategy': '【僵尸链守墓人】',
            'tone': 'roast',
            'evidence': {
                '主力持仓为上古代币': '是',
                '距上次活跃天数': s['last_active_days_ago'],
                '备注': '沉睡在2017年的古典遗老，还在等大清复亡吗？'
            }
        }

    # 完美踏空撸毛人
    if s['missed_snapshot_ratio'] > 0.8 and s['monthly_tx_count'] > 50:
        return {
            'label': '完美踏空撸毛人',
            'strategy': '【完美踏空撸毛人】',
            'tone': 'roast',
            'evidence': {
                '交互却错过快照比例': f"{s['missed_snapshot_ratio']*100:.0f}%",
                '月交易次数': s['monthly_tx_count'],
                '备注': '在赛博电子厂拧了一年螺丝，发工资那天你刚好请假了'
            }
        }

    # ════════════════════════════════════════
    # 【第四病区：异类】
    # ════════════════════════════════════════

    # 跨链流浪汉
    if s['cross_chain_count'] > 20 and s['pnl_pct'] < 0:
        return {
            'label': '跨链流浪汉',
            'strategy': '【跨链流浪汉】',
            'tone': 'roast',
            'evidence': {
                '跨链桥使用次数': s['cross_chain_count'],
                '总收益': f"{s['pnl_pct']}%",
                '备注': '哪里有热点就往哪里转，最后钱全没在过桥费里了'
            }
        }

    # 赛博杂货铺
    if s['token_variety'] > 100 and s['top_token_ratio'] < 0.05:
        return {
            'label': '赛博杂货铺',
            'strategy': '【赛博杂货铺】',
            'tone': 'roast',
            'evidence': {
                '钱包代币种类': s['token_variety'],
                '最大单一代币占比': f"{s['top_token_ratio']*100:.1f}%",
                '备注': '你这不是投资组合，这是垃圾回收站'
            }
        }

    # 赛博域名黄牛
    if s['domain_count'] > 20 and s['token_variety'] < 5:
        return {
            'label': '赛博域名黄牛',
            'strategy': '【赛博域名黄牛】',
            'tone': 'roast',
            'evidence': {
                '域名数量': s['domain_count'],
                '代币种类': s['token_variety'],
                '备注': '蹲在赛博公路旁炒地皮的黄牛，盼着哪个大企业来高价收你的破烂'
            }
        }

    # 只看不买的太监
    if s['last_active_days_ago'] > 365 and s['total_tx_count'] < 5:
        return {
            'label': '只看不买的太监',
            'strategy': '【只看不买的太监】',
            'tone': 'roast',
            'evidence': {
                '总交易次数': s['total_tx_count'],
                '距上次活跃天数': s['last_active_days_ago'],
                '备注': '每天看别人暴富，自己一动不动，极度阳痿的链上观察者'
            }
        }

    # 老鼠仓
    if s['new_wallet_big_buy'] and s['win_rate'] > 90:
        return {
            'label': '老鼠仓',
            'strategy': '【老鼠仓 / 内幕交易员】',
            'tone': 'roast',
            'evidence': {
                '新钱包创建即全仓买入': '是',
                '胜率': f"{s['win_rate']}%",
                '备注': '毫不掩饰的内幕交易，不用侧写了，建议直接报警'
            }
        }

    # ════════════════════════════════════════
    # 早期标签系统兜底（F/G/H/J）
    # ════════════════════════════════════════

    # F: 惊弓之鸟精准割肉
    if s['avg_hold_minutes'] < 60 and s['avg_loss_tolerance_pct'] < 10 and s['sell_at_local_low_ratio'] > 0.6:
        return {
            'label': '惊弓之鸟精准割肉',
            'strategy': '【策略：极度恐慌型精准割肉纸手 / 震荡市流动性 ATM机】',
            'tone': 'roast',
            'evidence': {
                '平均持仓时长': f"{s['avg_hold_minutes']} 分钟",
                '平均止损容忍度': f"{s['avg_loss_tolerance_pct']}%",
                '卖出命中局部最低点比例': f"{s['sell_at_local_low_ratio']*100:.0f}%"
            }
        }

    # G: 俄罗斯轮盘单吊流
    if s['top_token_ratio'] > 0.95 and s['token_variety'] <= 2:
        return {
            'label': '俄罗斯轮盘单吊流',
            'strategy': '【策略：俄罗斯轮盘式单吊梭哈 / 绝命毒师】',
            'tone': 'roast',
            'evidence': {
                '最大单一代币资金占比': f"{s['top_token_ratio']*100:.0f}%",
                '钱包代币种类': s['token_variety']
            }
        }

    # H: 赛博丐帮
    if s['monthly_tx_count'] > 100 and s['avg_tx_amount_usd'] < 5 and s['contract_variety'] > 20:
        return {
            'label': '赛博丐帮',
            'strategy': '【策略：赛博丐帮低保撸毛工作室 / 链上电子厂打工人】',
            'tone': 'roast',
            'evidence': {
                '月交易次数': s['monthly_tx_count'],
                '单笔平均金额': f"${s['avg_tx_amount_usd']:.2f}",
                '交互合约种类': s['contract_variety']
            }
        }

    # J: 晚期接盘侠
    if s['buy_after_500x_ratio'] > 0.7 and s['loss_24h_after_buy_ratio'] > 0.6:
        return {
            'label': '晚期接盘侠',
            'strategy': '【策略：信息链最底端晚期 FOMO 接盘侠 / 庄家最爱的亲人】',
            'tone': 'roast',
            'evidence': {
                '买入时代币已涨500%+的比例': f"{s['buy_after_500x_ratio']*100:.0f}%",
                '买入后24h亏损比例': f"{s['loss_24h_after_buy_ratio']*100:.0f}%"
            }
        }

    # ════════════════════════════════════════
    # 默认兜底
    # ════════════════════════════════════════
    win_rate = s['win_rate']
    avg_hold = s['avg_hold_minutes']

    if win_rate < 30:
        label = '高位接盘侠'
    elif win_rate < 50:
        label = '菜鸟交易员'
    elif win_rate < 70:
        label = '稳健型选手'
    else:
        label = '交易高手'

    if avg_hold < 30:
        label += ' + 多动症纸手'
    elif avg_hold < 120:
        label += ' + 短线猎手'
    elif avg_hold < 2880:
        label += ' + 中线持有者'
    else:
        label += ' + 长期信仰者'

    return {
        'label': label,
        'strategy': f'【综合侧写：{label}】',
        'tone': 'roast' if win_rate < 50 else 'praise',
        'evidence': {
            '胜率': f"{win_rate}%",
            '平均持仓时长': f"{avg_hold} 分钟",
            '高位接盘比例': f"{s['top_buy_ratio']*100:.0f}% 的买入都在当日最高点"
        }
    }


if __name__ == '__main__':
    test_wallets = [
        '9B5X5wUohEzB9fd6X56QjpEWqYzEGAJoKooK7FJqkAd7',
        'TokenkegQfeZyiNwAJsyFbPVwwQQfg5bgvWqNKqLAd',
        'SysvarC1ock11111111111111111111111111111111'
    ]

    print('=' * 70)
    print('Web3 钱包数据分析引擎 v2.0')
    print('=' * 70)

    for wallet in test_wallets:
        stats = get_wallet_stats(wallet)
        profile = generate_profile(stats)
        print(f'\n📍 钱包: {wallet[:20]}...')
        print(f'   标签: {profile["label"]}')
        print(f'   策略: {profile["strategy"]}')
        print(f'   语气: {"夸" if profile["tone"] == "praise" else "讽刺"}')
        print(f'   证据: {profile["evidence"]}')

    print('\n' + '=' * 70)
  