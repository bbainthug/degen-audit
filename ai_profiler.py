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
    'hf_cold': '一天对着 Pump.fun 上的同一个狗屎盘子疯狂抽插 100 次，1 秒钟的微薄利润也要榨干。你这不是在交易，你是个挂在 RPC 节点上舔滑点的RPC节点打工狗。为了抠别人那几美分的差价，你的电费和 Gas 费快把利润烧穿了吧？硅基生命里的底层打工狗。',
    'hf_rage': '平均持仓 1 秒？兄弟，你这不仅是纸手，你这是极其严重的极端早泄。24 小时内在一个土狗币上买卖 100 次，你的多巴胺受体已经被这根 K 线彻底烧毁了。你不是在炒币，你是在把 Solana 当成刮刮乐疯狂摩擦。建议尽早拔掉网线，去医院挂个泌尿科。',
    'hf_short': '在同一个 Pump.fun 垃圾盘里，1秒进，1秒出，一天抽搐 100 次。华尔街的高频量化要是看了你的操作，都得连夜给你发个保安的 Offer。你的键盘上是不是只剩下 Buy 和 Sell 两个键了？',
    'hf_twitch': '24小时在同一个盘子里抽搐 100 次，平均持仓 72 秒？你这不是在交易，你是在给 Solana 网络的吞吐量做压力测试。这种毫无意义的极速纸手操作，除了给节点交 Gas 费，唯一的贡献就是证明了你是一个多巴胺中毒的低级脚本。建议去挂个脑科，看看你的反射弧是不是已经烧焦了。',
    'hf_bot': '一天交易超过一千次，每笔金额 $0.001，胜率 32%？你这根本不是人在炒币，你是个挂在 RPC 节点上撒网的低级扫射脚本。策略就是往一万个垃圾盘里各扔一分钱，碰运气等个百倍盘。Gas 费和手续费加起来早把利润吃光了吧？链上寄生虫，滚去 touch grass。',
    'fomo': '看到推特大V一喊单你就高潮，满仓冲进去刚好给庄家发退休金。你的胜率比抛硬币还惨，买的全是貔貅和被撤池子的杀猪盘。你的钱包不仅是Web3垃圾场，更是你智商的火化炉。风很大，套得很冷吧？',
    'airdrop': '每天像个丐帮一样在各大链上点鼠标，交的 Gas 费比你这辈子赚的空投都多。V神看到你的转账记录都得连夜给你发个低保。别搁这假装 Web3 建设者了，你那手速去电子厂拧螺丝早当上车间主任了。',
    'smart_money': '胜率 80%、精准逃顶？行吧，算你狠。看你这毫无感情的机器操作，估计天天熬夜盯盘头发都掉光了吧？老鼠仓的铜臭味隔着屏幕都能闻到。恭喜你赚麻了，赶紧滚去摸摸草（Touch grass）吧，Fuck you and congrats. 你现实生活应该极度枯燥，朋友圈最后一条动态还是 2019 年发的吧？',
    'diamond_hand': '跌了 90% 还在加仓，你把"抄底"玩成了"抄家"。别人是炒币，你是在跟这个垃圾项目谈一场没有结果的恋爱。你这种极度自律的慢性自杀，庄家看了都得给你磕个头。醒醒吧大怨种，人家创始人早拿你的钱去 KTV 搂嫩模了。',
    'chaos': '钱包里躺着几十个名字都没听过的土狗币，每个价值不到 1 块钱。你这不是投资组合，你这特么是 Web3 废品回收站。到处撒网，精准踩雷，你对这个黑暗森林的贡献，就是用真金白银给所有骗子送外卖。',
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
    'chaos_en': 'Dozens of coins in your wallet that nobody has heard of, each worth less than a dollar. That is not a portfolio — that is a Web3 junkyard. Casting nets everywhere, stepping on every landmine. Your contribution to this dark forest is delivering food to every scammer at your own expense.',
}


def _pick_dynamic_examples(tone: str, label: str, evidence: dict) -> list:
    label_l = (label or '').lower()
    tx_24h = int(evidence.get('transactions_last_24h', 0) or 0)
    hold_sec = int(evidence.get('avg_hold_time_seconds', 0) or 0)
    diversity = int(evidence.get('token_diversity_count', 0) or 0)
    pool = []
    if any(k in label_l for k in ['高频', '短线', '纸手', 'mev', 'bot', '触手', '刷单']):
        pool.extend(['hf_bot', 'hf_twitch', 'hf_cold', 'hf_rage', 'hf_short'])
    if any(k in label_l for k in ['接盘', '追高', '站岗', 'fomo', '貔貅', '受害', '只买']):
        pool.extend(['fomo', 'chaos'])
    if any(k in label_l for k in ['新盘', '狙击', '土狗猎']):
        pool.extend(['chaos', 'hf_twitch'])
    if any(k in label_l for k in ['主流币', '波段', '伏击', '纪律']):
        pool.extend(['smart_money', 'hf_short'])
    if any(k in label_l for k in ['撸毛', '低保', '交互']):
        pool.extend(['airdrop', 'chaos'])
    if any(k in label_l for k in ['死扛', '钻石', '加仓']):
        pool.extend(['diamond_hand', 'fomo'])
    if any(k in label_l for k in ['聪明钱', '巨鲸', '纪律', '伏击']):
        pool.extend(['smart_money', 'hf_short'])
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

    # English 分支
    if lang == 'en':
        en_examples = _pick_dynamic_examples_en(tone=tone, label=label, evidence=evidence)
        en_examples_block = '\n'.join([f'- Example {i+1}: {txt}' for i, txt in enumerate(en_examples)])
        tx_24h = evidence.get('transactions_last_24h', '?')
        hold_sec = evidence.get('avg_hold_time_seconds', '?')
        diversity = evidence.get('token_diversity_count', '?')
        platform = evidence.get('platform_preference', '?')
        top_token = profile_data.get('frequent_tokens') or evidence.get('致命操作') or ['unknown']
        if tone != 'praise':
            en_system = (
                'You are a savage, sleep-deprived Crypto Twitter (CT) whale who hates everyone.\n\n'
                'Mandatory rules:\n'
                '1. Must mention: this is based on the last 50 tx slice only.\n'
                f'2. Must quote at least 2 specific numbers ({tx_24h} trades/24h, avg hold {hold_sec}s, {diversity} tokens).\n'
                '3. If avg hold < 60s and high freq: call them MEV bottom-feeder or high-speed jeeter.\n'
                '4. If diversity >= 50: call them Web3 junk collector.\n'
                '5. Output ~50 words. Banned: algorithm, remarkable, admirable.\n\n'
                f'Examples:\n{en_examples_block}'
            )
        else:
            en_system = (
                'You are a salty just-rekt CT degen, EXTREMELY jealous but cannot deny the numbers.\n'
                'Backhanded compliment energy. Imply bot/insider. Mock real life. End with Fuck you and congrats.\n\n'
                'Mandatory rules:\n'
                '1. Must mention: last 50 tx slice only.\n'
                '2. Must quote at least 2 data points.\n'
                '3. Output ~50 words. Banned: algorithm, logic, admirable.\n\n'
                f'Examples:\n{en_examples_block}'
            )
        en_user = (
            f'Platform: {platform}, 24h trades: {tx_24h}, avg hold: {hold_sec}s, '
            f'unique mints: {diversity}, top token: {top_token}. CT roast, ~50 words.'
        )
        try:
            response = client.chat.completions.create(
                model='meta/llama-3.3-70b-instruct',
                messages=[{'role': 'system', 'content': en_system}, {'role': 'user', 'content': en_user}],
                temperature=0.85, max_tokens=300,
            )
            text = response.choices[0].message.content.strip()
            if '50' not in text and 'last 50' not in text:
                text = f'Based on your last 50-tx slice — {text}'
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

    system_prompt = f"""你现在是 Crypto Twitter (CT) 上的顶级暴躁老哥、职业 Degen 开盒机。
你不准自由发挥，你不准使用"综上所述"、"赛博"、"灵魂脑电波"等词汇。
你必须严格按照我给你的【剧本与数据】进行输出。

【你的剧本与数据】：
{injected_template}

【你的唯一任务】：
将上面的【文案参考】用极其地道、暴躁、带有街头攻击性的 Web3 黑话重写一遍。
必须保留所有的数据和核心嘲讽点，字数控制在 80 字以内。
结尾必须狠狠地喷一句！严禁使用任何温和词汇。
严禁输出：梦游、虚空、令人痛心、算法逻辑、卓越、令人敬佩。
{'⚠️ 盈亏数据不可靠，严禁提及任何盈亏、胜率、SOL盈利亏损数字。' if not pnl_reliable else ''}

【神级范本】
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
