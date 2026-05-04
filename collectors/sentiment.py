import requests
from loguru import logger

_TIMEOUT = 6


def get_fear_greed() -> dict:
    try:
        resp = requests.get('https://api.alternative.me/fng/?limit=1', timeout=_TIMEOUT)
        d = resp.json()['data'][0]
        return {'value': int(d['value']), 'label': d['value_classification']}
    except Exception as e:
        logger.warning(f"恐贪指数获取失败: {e}")
        return {'value': 50, 'label': 'Neutral'}


def get_crypto_news(token: str, limit: int = 8) -> list:
    if not token:
        return []
    try:
        url = f'https://cryptopanic.com/api/v1/posts/?auth_token={token}&kind=news&filter=hot&public=true'
        posts = requests.get(url, timeout=_TIMEOUT).json().get('results', [])[:limit]
        news = []
        for p in posts:
            votes = p.get('votes', {})
            bullish = int(votes.get('positive', 0))
            bearish = int(votes.get('negative', 0))
            sentiment = 'bullish' if bullish > bearish else 'bearish' if bearish > bullish else 'neutral'
            coins = [c['code'] for c in p.get('currencies', [])][:3]
            news.append({'title': p['title'], 'sentiment': sentiment, 'coins': coins})
        return news
    except Exception as e:
        logger.warning(f"CryptoPanic 获取失败: {e}")
        return []
