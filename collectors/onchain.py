import requests
from loguru import logger

_TIMEOUT = 8


def get_defi_tvl() -> dict:
    try:
        data = requests.get('https://api.llama.fi/v2/historicalChainTvl', timeout=_TIMEOUT).json()
        if len(data) >= 2:
            tvl = float(data[-1].get('tvl', 0))
            prev = float(data[-2].get('tvl', 1))
            change = (tvl - prev) / prev * 100
            return {'tvl_usd': tvl, 'tvl_change_24h': round(change, 2)}
    except Exception as e:
        logger.warning(f"DeFiLlama 获取失败: {e}")
    return {'tvl_usd': 0, 'tvl_change_24h': 0}


def get_market_overview(demo_key: str = '') -> dict:
    try:
        headers = {'x-cg-demo-api-key': demo_key} if demo_key else {}
        data = requests.get(
            'https://api.coingecko.com/api/v3/global', headers=headers, timeout=_TIMEOUT
        ).json().get('data', {})
        return {
            'total_mcap_usd': float(data.get('total_market_cap', {}).get('usd', 0)),
            'mcap_change_24h': float(data.get('market_cap_change_percentage_24h_usd', 0)),
            'btc_dominance': float(data.get('market_cap_percentage', {}).get('btc', 0)),
        }
    except Exception as e:
        logger.warning(f"CoinGecko 获取失败: {e}")
    return {'total_mcap_usd': 0, 'mcap_change_24h': 0, 'btc_dominance': 0}
