import os
import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# 🛡️ 兼容 Streamlit 云端 Secrets + 本地 .env
def _get_nvidia_key() -> str:
    try:
        import streamlit as st
        key = st.secrets.get("NVIDIA_API_KEY") or os.getenv('NVIDIA_API_KEY', '')
    except Exception:
        key = os.getenv('NVIDIA_API_KEY', '')
    return (key or '').strip()

# 动态 Few-Shot 范本库
FEW_SHOT_LIBRARY = {
    # ── 纸手 / Jeet ──
    'jeet_1': '你就这点出息？持仓时间比你那啥时间都短。你是来交易的，还是来给 Solana 贡献手续费的？看到绿柱子就手抖，看到红柱子就尿裤子，夹子机器人看你都像在看自助餐。',
    'jeet_2': '恭喜你，凭借一己之力养活了三个套利机器人。你的操作逻辑总结起来就四个字：反复去世。这种持仓时长，建议出门左转去买彩票，别在链上丢人现眼了。',
    'jeet_3': '你是懂落袋为安的，每次都精准避开了所有的涨幅。你上辈子可能是个割肉机，这辈子专门来链上当人体润滑剂，帮庄家丝滑出货。',
    # ── 接盘侠 / 顶级韭菜 ──
    'bagholder_1': '你是打算把这些归零土狗当成传家宝吗？项目方推特都注销了，你还在那儿格局？你不是在投资，你是在搞赛博慈善。你的钱包就是土狗币的终点站，所有垃圾最后都会死在你手里。',
    'bagholder_2': '在山顶站岗的感觉冷吗？你这种至死不渝的浪漫，让庄家在会所嫩模时都忍不住想给你点个赞。你不是在买币，你是在给项目方付豪宅首付。',
    'bagholder_3': '别看了，解套是不可能解套的，这辈子都不可能。你对价值投资的误解比你的亏损还要深。建议把钱包助记词刻在墓碑上，看看下辈子能不能回本。',
    # ── 赛博乞丐 ──
    'beggar_1': '你是来 Solana 上捡破烂的吗？这钱包里的余额连吃顿黄焖鸡都费劲。你的交易记录像极了垃圾邮件箱，除了灰尘就是废纸。就这几块钱，你还盯着看了一下午？',
    'beggar_2': '这种持仓规模，别叫 Degen 了，叫赛博盲流更合适。你在链上忙活半天，赚的还没给 Helius 贡献的流量多。求求你，找个班上吧，别在 Web3 浪费网费了。',
    # ── FOMO 冲子 / 逆向指标 ──
    'fomo_1': '你就是传说中的人形反向指标？只要你一买，项目方就想跑路；只要你一卖，币价就开始升天。这种精准踩雷的天赋，Arkham 都得请你去当顾问。',
    'fomo_2': '别问为什么又被 Rug 了，问就是智商欠费。你这种无脑冲高位的姿态，让所有 12 岁项目方开发者都感受到了这个世界的温暖。你是他们的光，你是他们退出的流动性。',
    # ── 高频刷单 ──
    'hf_cold': '一天对着同一个垃圾盘疯狂抽插 100 次，1 秒钟的微薄利润也要榨干。你这不是在交易，你是个挂在 RPC 节点上舔滑点的打工狗。Gas 费快把利润烧穿了吧？',
    'hf_rage': '平均持仓 1 秒？不仅是纸手，是极度严重的极端早泄。24 小时在同一个土狗上抽搐 100 次，你的多巴胺受体已经被这根 K 线彻底烧毁了。你不是在炒币，你是把 Solana 当成刮刮乐疯狂摩擦。',
    'hf_twitch': '24小时在同一个盘子里抽搐 100 次，平均持仓 72 秒？除了给节点交 Gas 费，唯一的贡献就是证明了你是一个多巴胺中毒的低级脚本。去挂个脑科，看看你的反射弧是不是已经烧焦了。',
    # ── 撸毛乞丐 ──
    'airdrop': '每天像个丐帮一样在各大链上点鼠标，交的 Gas 费比你这辈子赚的空投都多。V神看到你的转账记录都得连夜给你发个低保。别搁这假装 Web3 建设者了，你那手速去电子厂拧螺丝早当上车间主任了。',
    # ── 逃顶神（嫉妒嘲讽）──
    'smart_money': '胜率 80%、精准逃顶？行吧，算你狠。老鼠仓的铜臭味隔着屏幕都能闻到。赚麻了赶紧滚去 touch grass，你现实生活应该极度枯燥，朋友圈最后一条动态还是 2019 年发的吧？Fuck you and congrats.',
    # ── 死扛 ──
    'diamond_hand': '跌了 90% 还在加仓，你把抄底玩成了抄家。别人是炒币，你是在跟垃圾项目谈一场没有结果的恋爱。人家创始人早拿你的钱去 KTV 搂嫩模了。醒醒吧大怨种。',
    # ── 杂牌收集 ──
    'chaos': '钱包里躺着几十个名字没听过的土狗币，每个价值不到 1 块钱。这不是投资组合，这是 Web3 废品回收站。到处撒网精准踩雷，你对这个黑暗森林的唯一贡献就是用真金白银给所有骗子送外卖。',
}


# 英文 CT 风格 Few-Shot 范本库
FEW_SHOT_LIBRARY_EN = {
    'hf_cold_en': 'Trading 100 times a day on a single Pump.fun coin? You are not a trader — you are a 1-second-duration high-speed jeeter licking crumbs off the RPC node. Your electric bill and gas fees are about to torch whatever micro-profits you scraped. Silicon-based bottom-feeder.',
    'hf_rage_en': 'Average hold time of 1 second? Bro, this is not paper hands — this is cyber-premature ejaculation. 100 trades in 24 hours on the same dog coin? Your dopamine receptors are completely fried by this K-line. You are not trading, you are using Solana as a scratch card. Touch grass and see a doctor.',
    'hf_short_en': 'In and out of the same Pump.fun garbage in 1 second, twitching 100 times a day. If a real HFT quant saw your on-chain history they would send you a security guard job offer. Does your keyboard only have two keys — Buy and Sell?',
    'fomo_en': 'A CT influencer tweets and you ape in full port, handing your retirement fund straight to the dev. Your win rate is worse than a coin flip and you keep buying rugs and honeypots. Your wallet is not just a degen graveyard — it is a crematorium for your IQ. Feels cold under that bag, huh?',
    'airdrop_en': 'Clicking around every chain like a cyber-beggar guild, spending more on gas than every airdrop you have ever farmed combined. Vitalik would personally mail you a welfare check if he saw your transaction history. Stop larping as a Web3 builder — your click speed belongs on a factory floor.',
    'smart_money_en': '80% win rate and perfect exits? We see you, insider dev. No normal human grinds these numbers without either a bot or insider info. Enjoy your rugs while the SEC nap lasts. Your real life must be absolutely cooked — when did you last touch grass? Fuck you and congrats, I guess.',
    'diamond_hand_en': 'Down 90% and still buying? You turned buying the dip into buying the grave. Everyone else trades coins — you are in a parasocial relationship with a dead project. The dev already bounced to Bali with your money. Wake up, professional bag-holder.',
    'chaos_en': 'Dozens of coins nobody has ever heard of, each worth less than a dollar. That is not a portfolio — that is a Web3 junkyard. Casting nets everywhere, stepping on every single landmine. Your contribution to this ecosystem is personally funding every scammer\'s exit.',
    # ── Jeet / paper hands ──
    'jeet_1_en': 'That\'s all you got? Your average hold time is shorter than your attention span. Are you here to trade or to personally fund Solana validator fees? Green candle and your hand trembles. Red candle and you\'ve already wet yourself. MEV bots look at your wallet like an all-you-can-eat buffet.',
    'jeet_2_en': 'Congratulations — you single-handedly kept three arbitrage bots profitable this month. Your entire trading philosophy can be summarized in two words: perpetual exit liquidity. With hold times like these, go buy lottery tickets. Stop embarrassing yourself on-chain.',
    'jeet_3_en': 'You really understand taking profits — you just happen to take them right before every single pump. You were probably a stop-loss machine in a past life. This life, you showed up on-chain to be the human lubricant that helps devs dump smoothly.',
    # ── bagholder / top buyer ──
    'bagholder_1_en': 'You planning to pass these zeroed-out dog coins down as inheritance? The dev\'s Twitter is deleted and you\'re out here talking about fundamentals. You\'re not investing — you\'re running a crypto charity. Your wallet is the final destination for every piece of garbage in this ecosystem.',
    'bagholder_2_en': 'How\'s it feel standing guard at the top? That devoted loyalty of yours — the dev is probably toasting you from his yacht right now. You\'re not buying coins. You\'re making the down payment on his next mansion.',
    'bagholder_3_en': 'There is no recovery. There will never be a recovery. Your misunderstanding of value investing runs deeper than your losses. Consider tattooing your seed phrase on your tombstone and hoping for a better next life.',
    # ── cyber beggar ──
    'beggar_1_en': 'Did you come to Solana to dumpster dive? The balance in this wallet can\'t buy a meal. Your transaction history looks exactly like a spam folder — nothing but dust and dead links. And you sat staring at this for an entire afternoon?',
    'beggar_2_en': 'At this portfolio size, stop calling yourself a Degen — Cyber Vagrant is more accurate. You spent all afternoon grinding on-chain and your net gains are less than the bandwidth you gave Helius for free. Get a job. Stop wasting Wi-Fi on Web3.',
    # ── FOMO ──
    'fomo_1_en': 'You are literally a human inverse indicator. Every time you buy, the dev starts planning his exit. Every time you sell, the chart goes vertical. Your brain is exactly one phase shift behind the market at all times. Arkham Intelligence should hire you as a contrarian signal.',
    'fomo_2_en': 'Stop asking why you got rugged again. The answer is IQ deficiency. Your reflex to ape into tops at full port has given every 12-year-old dev in this space a warm and fuzzy feeling. You are their light. You are their exit liquidity.',
}


def _pick_dynamic_examples(tone: str, label: str, evidence: dict) -> list:
    label_l = (label or '').lower()
    tx_24h = int(evidence.get('transactions_last_24h', 0) or 0)
    hold_sec = int(evidence.get('avg_hold_time_seconds', 0) or 0)
    diversity = int(evidence.get('token_diversity_count', 0) or 0)
    pool = []
    if any(k in label_l for k in ['高频', '短线', '纸手', 'mev', 'bot', '触手', '刷单']):
        pool.extend(['hf_twitch', 'hf_cold', 'hf_rage', 'jeet_1', 'jeet_2'])
    if any(k in label_l for k in ['接盘', '追高', '站岗', 'fomo', '貔貅', '受害', '只买']):
        pool.extend(['fomo_1', 'fomo_2', 'bagholder_1', 'bagholder_2', 'chaos'])
    if any(k in label_l for k in ['新盘', '狙击', '土狗猎']):
        pool.extend(['chaos', 'hf_twitch', 'jeet_3'])
    if any(k in label_l for k in ['主流币', '波段', '伏击', '纪律']):
        pool.extend(['smart_money', 'jeet_1'])
    if any(k in label_l for k in ['撸毛', '低保', '交互']):
        pool.extend(['airdrop', 'beggar_1', 'beggar_2'])
    if any(k in label_l for k in ['死扛', '钻石', '加仓']):
        pool.extend(['diamond_hand', 'bagholder_3', 'bagholder_2'])
    if any(k in label_l for k in ['聪明钱', '巨鲸', '纪律', '伏击']):
        pool.extend(['smart_money'])
    if any(k in label_l for k in ['集邮', '多样', '丐帮', 'chaos', '废品']):
        pool.extend(['chaos', 'airdrop'])
    if tone == 'praise':
        pool.extend(['smart_money', 'hf_short'])
    else:
        pool.extend(['fomo', 'chaos', 'hf_rage'])
    if hold_sec > 0 and hold_sec < 60 and tx_24h >= 80:
        pool.extend(['hf_cold', 'hf_rage'])
    if diversity >= 50:
        pool.extend(['chaos', 'airdrop'])
    if tx_24h >= 500:
        pool.extend(['hf_short', 'hf_cold'])
    picked = []
    for key in pool:
        if key not in picked and key in FEW_SHOT_LIBRARY:
            picked.append(key)
        if len(picked) == 2:
            break
    if len(picked) < 2:
        for key in ['hf_rage', 'fomo', 'smart_money', 'chaos']:
            if key not in picked:
                picked.append(key)
            if len(picked) == 2:
                break
    return [FEW_SHOT_LIBRARY[k] for k in picked]


def _pick_dynamic_examples_en(tone: str, label: str, evidence: dict) -> list:
    label_l = (label or '').lower()
    tx_24h = int(evidence.get('transactions_last_24h', 0) or 0)
    hold_sec = int(evidence.get('avg_hold_time_seconds', 0) or 0)
    diversity = int(evidence.get('token_diversity_count', 0) or 0)
    pool = []
    if any(k in label_l for k in ['freq', 'mev', 'jeet', 'paper', '高频', '纸手']):
        pool.extend(['hf_cold_en', 'hf_rage_en', 'hf_short_en'])
    if any(k in label_l for k in ['fomo', 'ape', '接盘', '站岗']):
        pool.extend(['fomo_en', 'chaos_en'])
    if any(k in label_l for k in ['airdrop', '撸毛', '集邮', 'chaos']):
        pool.extend(['airdrop_en', 'chaos_en'])
    if any(k in label_l for k in ['diamond', 'hold', '死扛']):
        pool.extend(['diamond_hand_en', 'fomo_en'])
    if any(k in label_l for k in ['smart', 'elite', 'whale', '聪明', '巨鲸', '伏击']):
        pool.extend(['smart_money_en', 'hf_short_en'])
    if tone == 'praise':
        pool.extend(['smart_money_en', 'hf_short_en'])
    else:
        pool.extend(['hf_rage_en', 'fomo_en', 'chaos_en'])
    if hold_sec > 0 and hold_sec < 60 and tx_24h >= 80:
        pool.extend(['hf_cold_en', 'hf_rage_en'])
    if diversity >= 50:
        pool.extend(['chaos_en', 'airdrop_en'])
    picked = []
    for key in pool:
        if key not in picked and key in FEW_SHOT_LIBRARY_EN:
            picked.append(key)
        if len(picked) == 2:
            break
    if len(picked) < 2:
        for key in ['hf_rage_en', 'fomo_en', 'smart_money_en', 'chaos_en']:
            if key not in picked:
                picked.append(key)
            if len(picked) == 2:
                break
    return [FEW_SHOT_LIBRARY_EN[k] for k in picked]


def get_ai_roast(profile_data: dict, lang: str = 'zh') -> str:
    """
    根据 profile_data 生成 AI 评语。
    lang: 'zh' 中文暴躁游资模式 | 'en' 英文 CT 街头灵魂模式
    """
    api_key = _get_nvidia_key()
    if not api_key:
        return 'API 密钥未配置，无法进行侧写分析。'

    # 智能代理：本地有代理就用，云端直连
    _proxy_url = 'http://127.0.0.1:7891'
    try:
        import socket as _socket
        _s = _socket.create_connection(('127.0.0.1', 7891), timeout=0.3)
        _s.close()
        transport = httpx.HTTPTransport(proxy=_proxy_url)
    except Exception:
        transport = httpx.HTTPTransport()
    http_client = httpx.Client(transport=transport, timeout=120)
    client = OpenAI(
        api_key=api_key,
        base_url='https://integrate.api.nvidia.com/v1',
        http_client=http_client,
    )

    tone = profile_data.get('tone', 'roast')
    label = profile_data.get('label', '')
    evidence = profile_data.get('evidence', {})
    system_label = profile_data.get('system_label') or f'【{label}】'
    dynamic_examples = _pick_dynamic_examples(tone=tone, label=label, evidence=evidence)
    examples_block = '\n'.join([f'- 范本{i+1}：{txt}' for i, txt in enumerate(dynamic_examples)])

    # English 分支（模板驱动，与中文逻辑对齐）
    if lang == 'en':
        en_examples = _pick_dynamic_examples_en(tone=tone, label=label, evidence=evidence)
        en_examples_block = '\n'.join([f'- Example {i+1}: {txt}' for i, txt in enumerate(en_examples)])
        tx_24h    = int(evidence.get('transactions_last_24h', 0) or 0)
        hold_sec  = int(evidence.get('avg_hold_time_seconds', 60) or 60)
        diversity = int(evidence.get('token_diversity_count', 0) or 0)
        avg_tx    = float(evidence.get('avg_tx_sol') or profile_data.get('avg_tx_sol', 0))
        span_h    = float(evidence.get('span_hours') or profile_data.get('span_hours', 0))
        avg_int   = int(evidence.get('avg_interval_seconds') or profile_data.get('avg_interval_seconds', 0))
        pnl_ok    = bool(evidence.get('pnl_reliable') or profile_data.get('pnl_reliable', False))
        rpnl      = float(evidence.get('realized_pnl_sol') or profile_data.get('realized_pnl_sol', 0) or 0)
        wr        = float(evidence.get('win_rate') or profile_data.get('win_rate', 0) or 0)
        avg_lose_e = float(evidence.get('avg_lose_sol') or profile_data.get('avg_lose_sol', 0) or 0)

        if hold_sec < 60:
            hold_str = f'{hold_sec}s'
        elif hold_sec < 3600:
            hold_str = f'{hold_sec // 60} min'
        else:
            hold_str = f'{hold_sec // 3600}h'

        if span_h < 1:
            density_str = f'last 100 txs done in {span_h*60:.0f} min, avg {avg_int}s per trade'
        elif span_h < 24:
            density_str = f'last 100 txs over {span_h:.1f}h, avg {avg_int//60} min per trade'
        else:
            density_str = f'last 100 txs over {span_h/24:.1f} days, avg {avg_int//3600}h per trade'

        EN_TEMPLATES = {
            'god_mode': (
                f'{wr:.0f}% win rate and up {rpnl:+.2f} SOL? Sure bro. '
                f'No human grinds numbers like that without a bot or inside info. '
                f'Enjoy your rugs while the SEC nap lasts. '
                f'Your real life must be completely cooked. Fuck you and congrats.'
            ),
            'beggar_mode': (
                f'{density_str}, {tx_24h} token trades, avg hold {hold_str}, '
                f'touched {diversity} garbage mints, avg {avg_tx:.2f} SOL per trade. '
                f'You are not trading. You are personally funding every validator on this network. '
                f'Your gas fees exceed your gains. Get a job.'
            ),
            'diamond_hands': (
                f'Holding for {hold_str} while down bad? '
                f'You turned buying the dip into buying the grave. '
                f'The dev already bounced to Bali with your SOL. '
                f'Wake up, professional bagholder.'
            ),
            'default': (
                f'{density_str}, {tx_24h} trades, avg hold {hold_str}, {diversity} dog coins, {avg_tx:.2f} SOL avg. '
                f'You are not a trader. You are exit liquidity with a wallet address. '
                f'Every single move you make is a gift to someone smarter than you.'
            ),
        }

        if tone == 'praise' and pnl_ok and rpnl > 5:
            en_tmpl = EN_TEMPLATES['god_mode']
        elif avg_tx < 0.5 and tx_24h >= 20:
            en_tmpl = EN_TEMPLATES['beggar_mode']
        elif hold_sec > 3600 * 6:
            en_tmpl = EN_TEMPLATES['diamond_hands']
        else:
            en_tmpl = EN_TEMPLATES['default']

        pnl_rule = f'PnL data reliable: win rate {wr:.0f}%, realized {rpnl:+.2f} SOL — must mention in roast.' if pnl_ok else 'PnL data unreliable — DO NOT mention any PnL, win rate, or SOL profit/loss numbers.'

        en_system = f"""You are the most savage, foul-mouthed CT degen on the internet. You roast people\'s on-chain behavior like a Baidu Tieba OG — blunt, crude, zero mercy.
You MUST follow the script below. Do NOT improvise. Do NOT soften the tone.

[YOUR SCRIPT AND DATA]
{en_tmpl}

[YOUR ONLY JOB]
Rewrite the script above using the most brutal, street-level CT slang possible.
Keep ALL the data points. Keep the core insult. Max 80 words. End with a gut-punch closing line.
Banned words: algorithm, remarkable, admirable, notable, impressive.
{pnl_rule}

[STYLE EXAMPLES]
{en_examples_block}"""
        en_user = 'Drop the roast. Now.'
        try:
            response = client.chat.completions.create(
                model='meta/llama-3.3-70b-instruct',
                messages=[{'role': 'system', 'content': en_system}, {'role': 'user', 'content': en_user}],
                temperature=0.9, max_tokens=300,
            )
            text = response.choices[0].message.content.strip()
            banned_en = ['algorithm', 'remarkable', 'admirable', 'last 50', '50-tx slice']
            for w in banned_en:
                text = text.replace(w, '')
            return text
        except Exception as e:
            return 'You are literally exit liquidity in human form. Touch grass.' if tone != 'praise' else 'Fuck you and congrats, you degenerate.'

    # 中文分支：Python 层预判断 + 锚定数据
    tx_24h_val    = int(evidence.get('transactions_last_24h', 0) or 0)
    hold_sec_val  = int(evidence.get('avg_hold_time_seconds', 60) or 60)
    diversity_val = int(evidence.get('token_diversity_count', 0) or 0)
    platform_val  = evidence.get('platform_preference', 'N/A')

    if hold_sec_val < 60:
        hold_time_str = f'{hold_sec_val} 秒'
    elif hold_sec_val < 3600:
        hold_time_str = f'{hold_sec_val // 60} 分钟'
    else:
        hold_time_str = f'{hold_sec_val // 3600} 小时'

    # 盈亏数据
    pnl_reliable  = bool(evidence.get('pnl_reliable') or profile_data.get('pnl_reliable', False))
    realized_pnl  = evidence.get('realized_pnl_sol') or profile_data.get('realized_pnl_sol', 0)
    win_rate_val  = evidence.get('win_rate') or profile_data.get('win_rate', 0)
    win_cnt       = evidence.get('win_count') or profile_data.get('win_count', 0)
    lose_cnt      = evidence.get('lose_count') or profile_data.get('lose_count', 0)
    avg_lose      = evidence.get('avg_lose_sol') or profile_data.get('avg_lose_sol', 0)
    avg_win       = evidence.get('avg_win_sol') or profile_data.get('avg_win_sol', 0)

    if pnl_reliable and realized_pnl:
        pnl_str = f'{realized_pnl:+.2f} SOL'
        pnl_anchor = (
            f'- 已实现盈亏：{pnl_str}\n'
            f'- 胜率：{win_rate_val:.0f}%（赢 {win_cnt} 次 / 亏 {lose_cnt} 次）\n'
            f'- 平均单笔盈利：{avg_win:+.2f} SOL\n'
            f'- 平均单笔亏损：{avg_lose:.2f} SOL\n'
        )
    else:
        pnl_str = '数据不足（链上买卖配对 < 5 笔）'
        pnl_anchor = '- 盈亏数据：不可靠，禁止在评语中提及盈亏、胜率、SOL 盈利数字\n'

    buy_sell_ratio = float(evidence.get('buy_sell_ratio') or profile_data.get('buy_sell_ratio', 0.5))
    span_hours = float(evidence.get('span_hours') or profile_data.get('span_hours', 0))
    avg_interval_sec = int(evidence.get('avg_interval_seconds') or profile_data.get('avg_interval_seconds', 0))
    avg_tx_sol = float(evidence.get('avg_tx_sol') or profile_data.get('avg_tx_sol', 0))

    if buy_sell_ratio > 0.75:
        trade_direction = f'偏买入（买入占比 {buy_sell_ratio:.0%}，有卖出行为）'
    elif buy_sell_ratio < 0.35:
        trade_direction = f'偏卖出（买入占比 {buy_sell_ratio:.0%})'
    else:
        trade_direction = f'买卖均衡（买入占比 {buy_sell_ratio:.0%}）'

    # 时间密度描述
    if span_hours < 1:
        density_str = f'最近100笔仅用了 {span_hours*60:.0f} 分钟打完，平均每 {avg_interval_sec} 秒一笔'
    elif span_hours < 24:
        density_str = f'最近100笔横跨 {span_hours:.1f} 小时，平均每 {avg_interval_sec//60} 分钟一笔'
    else:
        density_str = f'最近100笔横跨 {span_hours/24:.1f} 天，平均每 {avg_interval_sec//3600} 小时一笔'

    # 金额描述
    if avg_tx_sol > 0.01:
        amount_str = f'单笔均值 {avg_tx_sol:.2f} SOL'
    else:
        amount_str = '单笔金额数据不足'

    data_anchor = (
        f'[ DEGEN AUDIT 锚定证据 - 以下数字为天条，严禁修改或捏造 ]\n'
        f'- 交易密度：{density_str}\n'
        f'- 24h代币交易次数：{tx_24h_val} 次\n'
        f'- 平均持仓时长：{hold_time_str}\n'
        f'- 土狗 Mint 多样性：{diversity_val} 个\n'
        f'- 平台偏好：{platform_val}\n'
        f'- 交易方向：{trade_direction}\n'
        f'- 资金规模：{amount_str}\n'
        + pnl_anchor +
        f'- 主战场：{evidence.get("致命操作", "N/A")}\n'
        f'- 操作节奏：{evidence.get("割肉速度", "N/A")}\n'
        f'- 偏好赛道：{evidence.get("偏好赛道", "N/A")}'
    )

    # ── 模板驱动 Roast ──────────────────────────────────────
    ROAST_TEMPLATES = {
        'god_mode': (
            f'核心设定：这是一个胜率极高、赚了巨款的机器/老鼠仓既视感。\n'
            f'强制引用的数据：胜率 {win_rate_val:.0f}%，赚了 {pnl_str}。\n'
            '你必须传达的情绪：【嫉妒、嘲讽其现实生活悲惨、指控其是老鼠仓或开了脚本吸血】。\n'
            f'文案参考：胜率 {win_rate_val:.0f}%？狂赚 {pnl_str}？行吧，算你狠。'
            '看你这毫无感情的操作，估计平时连女生的手都没摸过，全靠挂着脚本在内存池里吸散户的血吧？'
            '纯纯的内部老鼠仓既视感。赚那么多有命花吗？Fuck you and congrats.'
        ),
        'beggar_mode': (
            f'核心设定：这是一个频繁交易、单笔投入极少、其实在慢性亏损的散户。\n'
            f'强制引用的数据：{density_str}，疯狂交易 {tx_24h_val} 次，平均持仓 {hold_time_str}，接触了 {diversity_val} 个垃圾盘。\n'
            '你必须传达的情绪：【极其鄙视其穷酸气、嘲讽其在给验证者打工、多巴胺早泄】。\n'
            f'文案参考：交易了 {tx_24h_val} 次，碰了 {diversity_val} 个垃圾土狗盘，平均持仓才 {hold_time_str}？'
            f'你这不是在交易，你是在链上乞讨。{amount_str}，你的 Gas 费都快够你在现实里买台二手 iPhone 了。'
            '别意淫能暴富了，赶紧找个厂上班吧，多巴胺早泄患者。'
        ),
        'diamond_hands': (
            f'核心设定：这是一个死扛到底、绝不割肉的大怨种。\n'
            f'强制引用的数据：持有时间极长（{hold_time_str}）。\n'
            '你必须传达的情绪：【嘲讽其在给庄家发年终奖、把抄底玩成抄家、装价值投资】。\n'
            f'文案参考：拿着不放 {hold_time_str}，跌成狗了还不跑？别人是炒币，你是在跟这个垃圾项目谈恋爱。'
            '你这种毫无纪律的死扛，完美演绎了什么叫给庄家发年终奖。风很大，套得很冷吧？Degen 大怨种。'
        ),
        'default': (
            f'核心设定：链上行为侧写。\n'
            f'强制引用的数据：{density_str}，{tx_24h_val}次代币交易，持仓{hold_time_str}，碰了{diversity_val}个土狗，{amount_str}。\n'
            '你必须传达的情绪：【嘲讽他是大怨种、接盘侠、给庄家打工】。\n'
            f'文案参考：{density_str}，碰了{diversity_val}个土狗，平均持仓{hold_time_str}，{amount_str}。'
            '你不是在交易，你是在送外卖。大怨种，赶紧收手吧。'
        ),
    }

    # 根据数据选择模板
    if tone == 'praise' and pnl_reliable and realized_pnl > 5:
        injected_template = ROAST_TEMPLATES['god_mode']
    elif avg_tx_sol < 0.5 and tx_24h_val >= 20:
        injected_template = ROAST_TEMPLATES['beggar_mode']
    elif hold_sec_val > 3600 * 6:
        injected_template = ROAST_TEMPLATES['diamond_hands']
    else:
        injected_template = ROAST_TEMPLATES['default']

    system_prompt = f"""你现在是贴吧最毒的链上开盒老哥，专门当众处刑赌狗。
你说话像真人，不像AI，口语化，脏话内涵都要有，节奏感强，一句一刀。
你必须严格按照我给你的【剧本与数据】进行输出，不准改数字，不准自由发挥跑题。

【你的剧本与数据】：
{injected_template}

【你的唯一任务】：
1. 把【文案参考】用最地道的贴吧/CT 黑话重写，语气要像当众公开处刑，不是在写报告。
2. 必须保留所有具体数字，这是铁律。
3. 字数 100-150 字，分 3-4 句话，每句都要有杀伤力，不许写废话过渡句。
4. 结尾一句必须是直接骂人的收尾，不许用省略号结尾。
5. 严禁使用：综上所述、赛博、灵魂、令人痛心、算法逻辑、卓越、令人敬佩、不得不说。
{'6. ⚠️ 盈亏数据不可靠，严禁提及任何盈亏、胜率、SOL盈利亏损数字。' if not pnl_reliable else ''}

【神级范本 - 这就是你要达到的骂人水准】
{examples_block}"""
    user_prompt = '立刻输出你的毒舌审计报告！'

    try:
        response = client.chat.completions.create(
            model='meta/llama-3.3-70b-instruct',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            temperature=0.7,
            max_tokens=200,
            top_p=1,
        )
        text = response.choices[0].message.content.strip()
        banned = ['梦游', '虚空', '黑暗森林', '令人痛心', '算法逻辑', '卓越', '令人敬佩']
        for w in banned:
            text = text.replace(w, '')
        slang_words = ['接盘', '割肉', '冲土狗', '被埋', '送外卖', '打螺丝', '大怨种', '纸手', '抽搐', '寄生虫', '多巴胺']
        if not any(sw in text for sw in slang_words):
            text = f'{text} 纯大怨种接盘。'
        return text
    except Exception as e:
        print(f'⚠️  API 调用失败: {e}')
        if tone == 'praise':
            return '这执行力不是运气，是纪律。'
        return '你这波操作，像给庄家送外卖。'


if __name__ == '__main__':
    from data_engine import get_wallet_stats, generate_profile
    test_wallets = [
        '9B5X5wUohEzB9fd6X56QjpEWqYzEGAJoKooK7FJqkAd7',
        'TokenkegQfeZyiNwAJsyFbPVwwQQfg5bgvWqNKqLAd',
        'SysvarC1ock11111111111111111111111111111111',
    ]
    for wallet in test_wallets:
        stats = get_wallet_stats(wallet)
        profile = generate_profile(stats)
        comment = get_ai_roast(profile)
        print(f'{wallet[:20]}... -> {comment}')
