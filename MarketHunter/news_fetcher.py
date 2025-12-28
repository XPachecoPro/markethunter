###############################################################################
# FILE: news_fetcher.py - Agregador de Notícias Financeiras via RSS
###############################################################################
import feedparser
from datetime import datetime
import time

# RSS Feeds de Notícias Financeiras
NEWS_FEEDS = {
    "crypto": [
        {"name": "Cointelegraph", "url": "https://cointelegraph.com/rss", "icon": "🪙"},
        {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "icon": "📰"},
        {"name": "Decrypt", "url": "https://decrypt.co/feed", "icon": "🔐"},
    ],
    "stocks": [
        {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex", "icon": "📈"},
        {"name": "Investing.com", "url": "https://www.investing.com/rss/news.rss", "icon": "💹"},
        {"name": "MarketWatch", "url": "https://feeds.marketwatch.com/marketwatch/topstories/", "icon": "📊"},
    ],
    "brazil": [
        {"name": "InfoMoney", "url": "https://www.infomoney.com.br/feed/", "icon": "🇧🇷"},
        {"name": "Valor Econômico", "url": "https://valor.globo.com/rss/valor/", "icon": "💰"},
    ]
}


def fetch_news_from_feed(feed_url, max_items=10):
    """
    Busca notícias de um feed RSS específico.
    """
    try:
        feed = feedparser.parse(feed_url)
        articles = []
        
        for entry in feed.entries[:max_items]:
            # Tenta extrair a data de publicação
            published = entry.get('published', entry.get('updated', ''))
            try:
                # Tenta parsear a data
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6])
                    time_ago = format_time_ago(pub_date)
                else:
                    time_ago = published[:20] if published else "Recente"
            except:
                time_ago = "Recente"
            
            articles.append({
                'title': entry.get('title', 'Sem título'),
                'link': entry.get('link', '#'),
                'summary': clean_summary(entry.get('summary', entry.get('description', ''))),
                'published': time_ago,
                'source': feed.feed.get('title', 'Fonte desconhecida')
            })
        
        return articles
    except Exception as e:
        print(f"Erro ao buscar feed {feed_url}: {e}")
        return []


def fetch_all_news(category="crypto", max_per_source=5):
    """
    Busca notícias de todas as fontes de uma categoria.
    """
    feeds = NEWS_FEEDS.get(category, NEWS_FEEDS["crypto"])
    all_news = []
    
    for feed_info in feeds:
        articles = fetch_news_from_feed(feed_info['url'], max_per_source)
        for article in articles:
            article['source_name'] = feed_info['name']
            article['icon'] = feed_info['icon']
        all_news.extend(articles)
    
    return all_news


def clean_summary(text):
    """Remove tags HTML do resumo."""
    import re
    clean = re.sub(r'<[^>]+>', '', text)
    return clean[:300] + "..." if len(clean) > 300 else clean


def format_time_ago(dt):
    """Formata a data como 'há X minutos/horas'."""
    now = datetime.now()
    diff = now - dt
    
    if diff.days > 0:
        return f"há {diff.days} dia{'s' if diff.days > 1 else ''}"
    elif diff.seconds >= 3600:
        hours = diff.seconds // 3600
        return f"há {hours} hora{'s' if hours > 1 else ''}"
    elif diff.seconds >= 60:
        minutes = diff.seconds // 60
        return f"há {minutes} min"
    else:
        return "agora"


def get_trending_topics(news_list):
    """
    Extrai os tópicos mais mencionados nas notícias.
    """
    from collections import Counter
    
    # Palavras-chave de interesse
    keywords = ['bitcoin', 'btc', 'ethereum', 'eth', 'solana', 'sol', 'xrp', 'bnb',
                'fed', 'trump', 'sec', 'etf', 'bull', 'bear', 'alta', 'queda',
                'ibovespa', 'dólar', 'petrobras', 'vale', 'selic', 'inflação']
    
    word_count = Counter()
    
    for news in news_list:
        text = (news.get('title', '') + ' ' + news.get('summary', '')).lower()
        for keyword in keywords:
            if keyword in text:
                word_count[keyword] += 1
    
    return word_count.most_common(5)


if __name__ == "__main__":
    print("🔎 Testando agregador de notícias...")
    
    print("\n📰 NOTÍCIAS CRYPTO:")
    crypto_news = fetch_all_news("crypto", max_per_source=3)
    for news in crypto_news[:5]:
        print(f"  {news['icon']} [{news['source_name']}] {news['title'][:60]}...")
    
    print("\n📈 NOTÍCIAS STOCKS:")
    stock_news = fetch_all_news("stocks", max_per_source=3)
    for news in stock_news[:5]:
        print(f"  {news['icon']} [{news['source_name']}] {news['title'][:60]}...")
    
    print("\n🇧🇷 NOTÍCIAS BRASIL:")
    br_news = fetch_all_news("brazil", max_per_source=3)
    for news in br_news[:5]:
        print(f"  {news['icon']} [{news['source_name']}] {news['title'][:60]}...")
