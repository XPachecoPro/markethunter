###############################################################################
# FILE: news_hunter.py - Módulo B: Caçador de Notícias
# 
# LÓGICA FINANCEIRA:
# ------------------
# Premissa: Notícias positivas (partnerships, listings, lançamentos) 
# historicamente precedem movimentações significativas de preço.
# 
# Keywords de alto impacto baseadas em análise histórica:
# - "Binance Listing": +50-200% em 24-48h historicamente
# - "Coinbase Listing": +30-150% devido à exposição institucional
# - "Partnership": +10-50% dependendo do parceiro
# - "Mainnet Launch": +20-100% em projetos legítimos
# - "Investment Round": +10-30% com validação de VCs
#
# ESTRATÉGIA: Capturar notícias ANTES do movimento se espalhar,
# usando fontes agregadoras com pouca latência.
###############################################################################

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import re

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

# CryptoPanic - Agregador gratuito de notícias crypto
CRYPTOPANIC_BASE_URL = "https://cryptopanic.com/api/v1/posts/"
CRYPTOPANIC_API_KEY = ""  # Opcional para requests básicos

# Request settings
REQUEST_TIMEOUT = 15

# Keywords e seus scores de impacto
# Baseado em análise histórica de impacto no preço
KEYWORDS_IMPACT = {
    # Tier 1: Altíssimo impacto (+5 pontos)
    "binance listing": 5,
    "coinbase listing": 5,
    "listed on binance": 5,
    "listed on coinbase": 5,
    
    # Tier 2: Alto impacto (+4 pontos)
    "kraken listing": 4,
    "bybit listing": 4,
    "okx listing": 4,
    "major exchange": 4,
    
    # Tier 3: Impacto significativo (+3 pontos)
    "partnership with": 3,
    "partners with": 3,
    "mainnet launch": 3,
    "mainnet live": 3,
    "token burn": 3,
    "strategic investment": 3,
    
    # Tier 2: Impacto moderado (+2 pontos)
    "investment round": 2,
    "series a": 2,
    "series b": 2,
    "seed round": 2,
    "funding round": 2,
    "new feature": 2,
    "upgrade": 2,
    "airdrop": 2,
    
    # Tier 1: Impacto baixo (+1 ponto)
    "integration": 1,
    "announcement": 1,
    "update": 1,
    "roadmap": 1,
}

# Keywords negativas (reduzem score)
KEYWORDS_NEGATIVE = {
    "hack": -5,
    "hacked": -5,
    "exploit": -4,
    "rug pull": -5,
    "scam": -5,
    "sec lawsuit": -4,
    "delisting": -4,
    "crash": -3,
    "dump": -2,
    "fud": -1,
}

# ============================================================================
# FUNÇÕES DE ANÁLISE
# ============================================================================

def detect_keywords(text: str) -> Dict:
    """
    Detecta keywords de impacto no texto da notícia.
    
    LÓGICA:
    - Busca por keywords positivas e negativas
    - Calcula score total baseado nos matches
    - Identifica qual tier de impacto foi encontrado
    
    Args:
        text: Texto da notícia (título + conteúdo)
    
    Returns:
        Dict com keywords encontradas, score total, e tier
    """
    text_lower = text.lower()
    
    found_positive = []
    found_negative = []
    total_score = 0
    
    # Busca keywords positivas
    for keyword, score in KEYWORDS_IMPACT.items():
        if keyword in text_lower:
            found_positive.append({
                'keyword': keyword,
                'score': score
            })
            total_score += score
    
    # Busca keywords negativas
    for keyword, score in KEYWORDS_NEGATIVE.items():
        if keyword in text_lower:
            found_negative.append({
                'keyword': keyword,
                'score': score
            })
            total_score += score  # Score negativo subtrai
    
    # Determina tier baseado no maior score encontrado
    max_positive = max([k['score'] for k in found_positive], default=0)
    if max_positive >= 5:
        tier = "🔥 TIER 1 - Exchange Major"
    elif max_positive >= 4:
        tier = "⚡ TIER 2 - Alto Impacto"
    elif max_positive >= 3:
        tier = "📈 TIER 3 - Impacto Significativo"
    elif max_positive >= 1:
        tier = "📊 TIER 4 - Impacto Moderado"
    else:
        tier = "❄️ Sem impacto detectado"
    
    return {
        'positive_keywords': found_positive,
        'negative_keywords': found_negative,
        'total_score': total_score,
        'tier': tier,
        'is_bullish': total_score > 0 and len(found_negative) == 0,
        'is_bearish': total_score < 0 or len(found_negative) > 0
    }


def analyze_sentiment_simple(text: str) -> Dict:
    """
    Análise de sentimento simplificada (sem IA).
    
    Usa heurísticas básicas para classificar o texto.
    Para análise mais precisa, use analyze_sentiment_ai().
    
    Args:
        text: Texto a analisar
    
    Returns:
        Dict com sentiment, confidence, e explicação
    """
    text_lower = text.lower()
    
    # Palavras positivas genéricas
    positive_words = [
        'bullish', 'surge', 'soar', 'rally', 'gain', 'rise', 'pump',
        'breakout', 'milestone', 'success', 'achieve', 'grow', 'growth',
        'adoption', 'revolutionary', 'innovative', 'breakthrough'
    ]
    
    # Palavras negativas genéricas
    negative_words = [
        'bearish', 'crash', 'dump', 'fall', 'drop', 'plunge', 'decline',
        'fail', 'failure', 'concern', 'risk', 'warning', 'trouble',
        'lawsuit', 'investigate', 'fraud'
    ]
    
    pos_count = sum(1 for word in positive_words if word in text_lower)
    neg_count = sum(1 for word in negative_words if word in text_lower)
    
    total = pos_count + neg_count
    if total == 0:
        return {
            'sentiment': 'NEUTRAL',
            'confidence': 0.5,
            'positive_count': 0,
            'negative_count': 0,
            'explanation': 'Sem palavras-chave de sentimento detectadas'
        }
    
    pos_ratio = pos_count / total
    
    if pos_ratio >= 0.7:
        sentiment = 'POSITIVE'
        confidence = min(0.9, 0.5 + (pos_ratio * 0.4))
    elif pos_ratio <= 0.3:
        sentiment = 'NEGATIVE'
        confidence = min(0.9, 0.5 + ((1 - pos_ratio) * 0.4))
    else:
        sentiment = 'NEUTRAL'
        confidence = 0.5
    
    return {
        'sentiment': sentiment,
        'confidence': confidence,
        'positive_count': pos_count,
        'negative_count': neg_count,
        'explanation': f'{pos_count} palavras positivas, {neg_count} negativas'
    }


def analyze_sentiment_ai(text: str, api_key: str) -> Dict:
    """
    Análise de sentimento usando IA (Gemini).
    
    Mais precisa que a análise simples, mas requer API key.
    
    Args:
        text: Texto a analisar
        api_key: Gemini API key
    
    Returns:
        Dict com sentiment, confidence, e explicação da IA
    """
    try:
        from google import genai
        
        client = genai.Client(api_key=api_key)
        
        prompt = f"""Analise o sentimento desta notícia de criptomoeda para trading:

"{text[:500]}"

Responda APENAS no formato:
[SENTIMENTO]: POSITIVE | NEGATIVE | NEUTRAL
[CONFIANÇA]: 0.0-1.0
[IMPACTO]: ALTO | MÉDIO | BAIXO
[RESUMO]: máximo 20 palavras"""

        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt
        )
        
        result = response.text.strip()
        
        # Parse da resposta
        sentiment = 'NEUTRAL'
        confidence = 0.5
        impact = 'BAIXO'
        summary = ''
        
        if '[SENTIMENTO]:' in result:
            if 'POSITIVE' in result.upper():
                sentiment = 'POSITIVE'
            elif 'NEGATIVE' in result.upper():
                sentiment = 'NEGATIVE'
        
        conf_match = re.search(r'\[CONFIANÇA\]:\s*([\d.]+)', result)
        if conf_match:
            confidence = float(conf_match.group(1))
        
        if 'ALTO' in result:
            impact = 'ALTO'
        elif 'MÉDIO' in result:
            impact = 'MÉDIO'
        
        return {
            'sentiment': sentiment,
            'confidence': confidence,
            'impact': impact,
            'raw_response': result,
            'source': 'AI'
        }
        
    except Exception as e:
        print(f"❌ [News Hunter] Erro na análise IA: {e}")
        # Fallback para análise simples
        return analyze_sentiment_simple(text)


# ============================================================================
# FUNÇÃO PRINCIPAL: BUSCAR NOTÍCIAS
# ============================================================================

def fetch_crypto_news(
    currencies: Optional[List[str]] = None,
    filter_type: str = "hot",
    hours_ago: int = 24,
    limit: int = 20
) -> List[Dict]:
    """
    Busca notícias de criptomoedas via CryptoPanic.
    
    ESTRATÉGIA:
    1. Busca notícias recentes (últimas 24h por padrão)
    2. Filtra por moedas específicas se fornecido
    3. Analisa keywords de impacto
    4. Calcula sentimento
    5. Ordena por potencial de impacto
    
    Args:
        currencies: Lista de símbolos (ex: ['BTC', 'ETH']). None = todas
        filter_type: 'hot', 'rising', 'bullish', 'bearish', 'important'
        hours_ago: Buscar notícias das últimas X horas
        limit: Número máximo de notícias
    
    Returns:
        Lista de notícias com análise de impacto
    """
    news_list = []
    
    try:
        # Monta URL
        url = CRYPTOPANIC_BASE_URL
        params = {
            "auth_token": CRYPTOPANIC_API_KEY if CRYPTOPANIC_API_KEY else None,
            "filter": filter_type,
            "public": "true"
        }
        
        # Remove params None
        params = {k: v for k, v in params.items() if v}
        
        # Adiciona filtro de moedas
        if currencies:
            params["currencies"] = ",".join(currencies)
        
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        
        # CryptoPanic pode retornar 403 sem API key para alguns endpoints
        if response.status_code == 403:
            print("⚠️ [News Hunter] CryptoPanic requer API key. Usando fonte alternativa...")
            return _fetch_fallback_news(currencies, limit)
        
        response.raise_for_status()
        data = response.json()
        
        results = data.get('results', [])
        
        for item in results[:limit]:
            try:
                # Extrai dados básicos
                title = item.get('title', '')
                published_at = item.get('published_at', '')
                source = item.get('source', {}).get('title', 'Unknown')
                url = item.get('url', '')
                
                # Verifica idade da notícia
                if published_at:
                    try:
                        pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                        age_hours = (datetime.now(pub_date.tzinfo) - pub_date).total_seconds() / 3600
                        if age_hours > hours_ago:
                            continue
                    except:
                        age_hours = 0
                else:
                    age_hours = 0
                
                # Extrai moedas mencionadas
                currencies_mentioned = []
                for curr in item.get('currencies', []):
                    currencies_mentioned.append({
                        'code': curr.get('code', ''),
                        'title': curr.get('title', '')
                    })
                
                # Analisa keywords
                keyword_analysis = detect_keywords(title)
                
                # Analisa sentimento (simples, sem IA)
                sentiment_analysis = analyze_sentiment_simple(title)
                
                # Monta objeto da notícia
                news = {
                    'title': title,
                    'source': source,
                    'url': url,
                    'published_at': published_at,
                    'age_hours': round(age_hours, 1),
                    'currencies': currencies_mentioned,
                    'keywords': keyword_analysis,
                    'sentiment': sentiment_analysis,
                    'votes': item.get('votes', {}),
                    # Score combinado para ranking
                    'impact_score': keyword_analysis['total_score'] + 
                                   (3 if sentiment_analysis['sentiment'] == 'POSITIVE' else 
                                    -2 if sentiment_analysis['sentiment'] == 'NEGATIVE' else 0)
                }
                
                news_list.append(news)
                
            except Exception as e:
                continue
        
        # Ordena por impact_score
        news_list.sort(key=lambda x: x.get('impact_score', 0), reverse=True)
        return news_list
        
    except requests.exceptions.RequestException as e:
        print(f"❌ [News Hunter] Erro de conexão: {e}")
        return _fetch_fallback_news(currencies, limit)
    except Exception as e:
        print(f"❌ [News Hunter] Erro inesperado: {e}")
        return []


def _fetch_fallback_news(currencies: Optional[List[str]] = None, limit: int = 10) -> List[Dict]:
    """
    Fonte alternativa de notícias usando RSS público.
    
    Usado quando CryptoPanic está indisponível ou requer API key.
    """
    try:
        # CoinDesk RSS (público)
        rss_url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
        
        response = requests.get(rss_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        news_list = []
        
        # Parse simples do RSS XML
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.content)
        
        for item in root.findall('.//item')[:limit]:
            title = item.find('title').text if item.find('title') is not None else ''
            link = item.find('link').text if item.find('link') is not None else ''
            pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ''
            
            # Analisa keywords
            keyword_analysis = detect_keywords(title)
            sentiment_analysis = analyze_sentiment_simple(title)
            
            news_list.append({
                'title': title,
                'source': 'CoinDesk',
                'url': link,
                'published_at': pub_date,
                'age_hours': 0,
                'currencies': [],
                'keywords': keyword_analysis,
                'sentiment': sentiment_analysis,
                'impact_score': keyword_analysis['total_score']
            })
        
        news_list.sort(key=lambda x: x.get('impact_score', 0), reverse=True)
        return news_list
        
    except Exception as e:
        print(f"❌ [News Hunter] Fallback RSS também falhou: {e}")
        return []


def search_news_for_symbol(symbol: str, api_key: Optional[str] = None) -> List[Dict]:
    """
    Busca notícias específicas para um símbolo de moeda.
    
    Útil para cruzar com gems identificadas.
    
    Args:
        symbol: Símbolo da moeda (ex: 'BTC', 'PEPE')
        api_key: Gemini API key para análise de sentimento IA
    
    Returns:
        Lista de notícias relacionadas ao símbolo
    """
    news = fetch_crypto_news(currencies=[symbol.upper()], limit=10)
    
    # Se tiver API key, enriquece com análise IA
    if api_key and news:
        for n in news[:5]:  # Limita IA aos top 5 para economizar
            n['sentiment_ai'] = analyze_sentiment_ai(n['title'], api_key)
    
    return news


# ============================================================================
# TESTE STANDALONE
# ============================================================================

if __name__ == "__main__":
    print("📰 Iniciando News Hunter...")
    print("-" * 60)
    
    news = fetch_crypto_news(filter_type="hot", limit=10)
    
    if news:
        for i, n in enumerate(news, 1):
            print(f"\n{i}. {n['title'][:80]}...")
            print(f"   📍 Fonte: {n['source']} | ⏰ {n['age_hours']}h atrás")
            print(f"   🎯 Keywords: {n['keywords']['tier']}")
            print(f"   💭 Sentimento: {n['sentiment']['sentiment']} ({n['sentiment']['confidence']:.1%})")
            print(f"   📊 Impact Score: {n['impact_score']}")
    else:
        print("❌ Nenhuma notícia encontrada!")
