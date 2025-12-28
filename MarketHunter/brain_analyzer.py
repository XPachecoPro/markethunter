###############################################################################
# FILE: brain_analyzer.py - Módulo C: O Cérebro (Analisador de Oportunidades)
# 
# LÓGICA FINANCEIRA:
# ------------------
# Este módulo integra os dados do Gem Scanner (moedas novas promissoras) com
# o News Hunter (notícias e sentimento) para identificar oportunidades de
# alta probabilidade.
# 
# PRINCÍPIO CORE: Convergência de Sinais
# Quando múltiplos fatores positivos se alinham, a probabilidade de um
# movimento significativo aumenta exponencialmente.
# 
# SISTEMA DE PONTUAÇÃO (0-20):
# - Moeda nova (< 90 dias) com market cap baixo = Base
# - Notícia positiva recente = Catalisador
# - Volume aumentando = Confirmação de interesse
# - Sentimento bullish = Momentum social
# 
# CLASSIFICAÇÃO DE OPORTUNIDADES:
# 🔥 HOT (15-20): Alerta imediato - Múltiplos sinais fortes convergindo
# ⚡ WARM (10-14): Oportunidade interessante - Vale monitorar de perto
# ❄️ COLD (0-9): Baixo potencial imediato - Apenas observação
#
# AVISO: Trading de criptomoedas envolve alto risco. Este sistema é
# apenas uma ferramenta de análise, não constitui conselho financeiro.
###############################################################################

from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Importa módulos irmãos
try:
    from gem_scanner import scan_coingecko_gems, get_gem_details
    from news_hunter import fetch_crypto_news, search_news_for_symbol, detect_keywords
except ImportError:
    # Para testes isolados
    def scan_coingecko_gems(*args, **kwargs): return []
    def get_gem_details(*args, **kwargs): return None
    def fetch_crypto_news(*args, **kwargs): return []
    def search_news_for_symbol(*args, **kwargs): return []
    def detect_keywords(text): return {'total_score': 0}

# ============================================================================
# CONFIGURAÇÃO DO SISTEMA DE PONTUAÇÃO
# ============================================================================

# Thresholds para classificação
SCORE_HOT_THRESHOLD = 15       # >= 15 = HOT 🔥
SCORE_WARM_THRESHOLD = 10      # >= 10 = WARM ⚡
# Abaixo de 10 = COLD ❄️

# Pesos para cada fator
SCORING_WEIGHTS = {
    # Fatores do Gem Scanner (Módulo A)
    'gem_score': 1.0,                # Score base da gem (0-10)
    'volume_spike_4h': 2.0,          # Volume subiu >50% em 4h
    'sweet_spot_mcap': 3.0,          # Market cap $5M-$20M
    'price_momentum': 2.0,           # Preço subindo
    
    # Fatores do News Hunter (Módulo B)
    'news_major_exchange': 5.0,      # Menção Binance/Coinbase listing
    'news_partnership': 3.0,         # Partnership anunciada
    'news_positive_sentiment': 3.0,  # Sentimento positivo
    'news_recent': 2.0,              # Notícia < 6 horas
    
    # Fatores de Convergência
    'multiple_news_sources': 2.0,    # Múltiplas fontes cobrindo
    'social_buzz': 1.0,              # Trending em social media
}


# ============================================================================
# FUNÇÕES DE ANÁLISE
# ============================================================================

def _calculate_volume_score(gem: Dict) -> Tuple[float, str]:
    """
    Calcula score baseado no comportamento do volume.
    
    LÓGICA FINANCEIRA:
    Volume crescente = interesse crescente = potencial de movimento.
    Se volume/mcap > 50%, há compras ativas significativas.
    
    Returns:
        Tuple com (pontos ganhos, explicação)
    """
    score = 0
    explanations = []
    
    vol = gem.get('volume_24h', 0) or 0
    mcap = gem.get('market_cap', 0) or 0
    
    if mcap > 0:
        vol_ratio = vol / mcap
        
        # Volume > 50% do market cap = alto interesse
        if vol_ratio > 0.5:
            score += SCORING_WEIGHTS['volume_spike_4h']
            explanations.append(f"📈 Volume {vol_ratio:.0%} do MCap")
        
    return score, "; ".join(explanations) if explanations else ""


def _calculate_mcap_score(gem: Dict) -> Tuple[float, str]:
    """
    Calcula score baseado no market cap.
    
    LÓGICA FINANCEIRA:
    "Sweet spot" entre $5M-$20M oferece melhor risk/reward:
    - Muito pequeno (<$1M): Risco extremo de rug
    - Sweet spot ($5M-$20M): Potencial de 10-50x ainda viável
    - Maior ($20M+): Menor potencial percentual
    
    Returns:
        Tuple com (pontos ganhos, explicação)
    """
    mcap = gem.get('market_cap', 0) or 0
    
    if 5_000_000 <= mcap <= 20_000_000:
        return (SCORING_WEIGHTS['sweet_spot_mcap'], 
                f"💎 Sweet spot MCap ${mcap/1_000_000:.1f}M")
    elif 1_000_000 <= mcap < 5_000_000:
        return (SCORING_WEIGHTS['sweet_spot_mcap'] * 0.5,
                f"📊 Micro cap ${mcap/1_000_000:.1f}M")
    elif 20_000_000 < mcap <= 50_000_000:
        return (SCORING_WEIGHTS['sweet_spot_mcap'] * 0.3,
                f"📊 Low cap ${mcap/1_000_000:.1f}M")
    
    return (0, "")


def _calculate_price_momentum_score(gem: Dict) -> Tuple[float, str]:
    """
    Calcula score baseado no momentum de preço.
    
    LÓGICA FINANCEIRA:
    Preço subindo indica interesse de compra. Mas subida muito forte
    pode indicar que já é tarde para entrar.
    
    - +5% a +20% em 24h: Momentum saudável ✅
    - > +50%: Possível FOMO, cuidado ⚠️
    - Negativo: Menor urgência, mas pode ser oportunidade
    
    Returns:
        Tuple com (pontos ganhos, explicação)
    """
    change_24h = gem.get('price_change_24h', 0) or 0
    
    if 5 <= change_24h <= 20:
        return (SCORING_WEIGHTS['price_momentum'],
                f"🚀 Momentum +{change_24h:.1f}%")
    elif 20 < change_24h <= 50:
        return (SCORING_WEIGHTS['price_momentum'] * 0.5,
                f"⚡ Alta forte +{change_24h:.1f}%")
    elif change_24h > 50:
        return (0, f"⚠️ Possível FOMO +{change_24h:.1f}%")
    
    return (0, "")


def _calculate_news_score(news_list: List[Dict]) -> Tuple[float, str, List[Dict]]:
    """
    Calcula score baseado nas notícias relacionadas.
    
    LÓGICA FINANCEIRA:
    - Menção de exchange major = catalisador forte
    - Múltiplas notícias = cobertura ampla
    - Notícia recente = timing bom para entrada
    
    Returns:
        Tuple com (pontos, explicação, notícias relevantes)
    """
    if not news_list:
        return (0, "", [])
    
    score = 0
    explanations = []
    relevant_news = []
    
    for news in news_list:
        keywords = news.get('keywords', {})
        sentiment = news.get('sentiment', {})
        age_hours = news.get('age_hours', 999)
        
        # Verifica keywords de exchange major
        for kw in keywords.get('positive_keywords', []):
            if kw['score'] >= 5:  # Tier 1 (Exchange major)
                score += SCORING_WEIGHTS['news_major_exchange']
                explanations.append(f"🏦 {kw['keyword'].title()}")
                relevant_news.append(news)
                break
            elif kw['score'] >= 3:  # Partnership/Mainnet
                score += SCORING_WEIGHTS['news_partnership']
                explanations.append(f"🤝 {kw['keyword'].title()}")
                relevant_news.append(news)
                break
        
        # Verifica sentimento
        if sentiment.get('sentiment') == 'POSITIVE':
            score += SCORING_WEIGHTS['news_positive_sentiment']
            explanations.append("😊 Sentimento positivo")
        
        # Verifica recência
        if age_hours < 6:
            score += SCORING_WEIGHTS['news_recent']
            explanations.append(f"⏰ Notícia há {age_hours:.0f}h")
    
    # Múltiplas fontes cobrindo
    if len(relevant_news) > 1:
        score += SCORING_WEIGHTS['multiple_news_sources']
        explanations.append(f"📰 {len(relevant_news)} fontes")
    
    return (score, "; ".join(set(explanations)), relevant_news)


def calculate_opportunity_score(gem: Dict, related_news: List[Dict]) -> Dict:
    """
    Calcula score total de oportunidade para uma gem.
    
    Combina todos os fatores para gerar um score único e classificação.
    
    Args:
        gem: Dados da gem do Gem Scanner
        related_news: Notícias relacionadas do News Hunter
    
    Returns:
        Dict com score total, classificação, breakdown de fatores, e explicações
    """
    total_score = 0
    explanations = []
    breakdown = {}
    
    # 1. Score base da gem
    gem_score = gem.get('gem_score', 0)
    total_score += gem_score
    breakdown['gem_base'] = gem_score
    
    # 2. Score de volume
    vol_score, vol_exp = _calculate_volume_score(gem)
    total_score += vol_score
    breakdown['volume'] = vol_score
    if vol_exp:
        explanations.append(vol_exp)
    
    # 3. Score de market cap
    mcap_score, mcap_exp = _calculate_mcap_score(gem)
    total_score += mcap_score
    breakdown['market_cap'] = mcap_score
    if mcap_exp:
        explanations.append(mcap_exp)
    
    # 4. Score de momentum
    momentum_score, momentum_exp = _calculate_price_momentum_score(gem)
    total_score += momentum_score
    breakdown['momentum'] = momentum_score
    if momentum_exp:
        explanations.append(momentum_exp)
    
    # 5. Score de notícias
    news_score, news_exp, relevant_news = _calculate_news_score(related_news)
    total_score += news_score
    breakdown['news'] = news_score
    if news_exp:
        explanations.append(news_exp)
    
    # Determina classificação
    if total_score >= SCORE_HOT_THRESHOLD:
        classification = "HOT"
        emoji = "🔥"
        action = "ALERTA IMEDIATO - Múltiplos sinais convergindo"
    elif total_score >= SCORE_WARM_THRESHOLD:
        classification = "WARM"
        emoji = "⚡"
        action = "MONITORAR - Potencial interessante"
    else:
        classification = "COLD"
        emoji = "❄️"
        action = "OBSERVAR - Baixo potencial imediato"
    
    return {
        'symbol': gem.get('symbol', ''),
        'name': gem.get('name', ''),
        'total_score': round(total_score, 1),
        'max_score': 20,
        'classification': classification,
        'emoji': emoji,
        'action': action,
        'breakdown': breakdown,
        'explanations': explanations,
        'related_news': relevant_news,
        'gem_data': gem
    }


# ============================================================================
# FUNÇÃO PRINCIPAL: GERAR SINAIS
# ============================================================================

def generate_opportunity_signals(
    max_market_cap: int = 50_000_000,
    min_volume: int = 500_000,
    gemini_api_key: Optional[str] = None,
    limit: int = 10
) -> List[Dict]:
    """
    Pipeline completo de geração de sinais de oportunidade.
    
    1. Busca gems (Módulo A)
    2. Para cada gem, busca notícias relacionadas (Módulo B)
    3. Cruza dados e calcula score (Módulo C)
    4. Ordena e retorna as melhores oportunidades
    
    Args:
        max_market_cap: Filtro de market cap máximo
        min_volume: Filtro de volume mínimo 24h
        gemini_api_key: API key para análise de sentimento IA (opcional)
        limit: Número máximo de oportunidades a retornar
    
    Returns:
        Lista de oportunidades ordenadas por score
    """
    print("🧠 [Brain] Iniciando análise de oportunidades...")
    
    opportunities = []
    
    # Passo 1: Buscar gems
    print("🔮 [Brain] Buscando gems...")
    gems = scan_coingecko_gems(
        max_market_cap=max_market_cap,
        min_volume_24h=min_volume,
        limit=20  # Busca mais para ter margem após filtragem
    )
    
    if not gems:
        print("❌ [Brain] Nenhuma gem encontrada")
        return []
    
    print(f"✅ [Brain] {len(gems)} gems encontradas")
    
    # Passo 2: Buscar notícias gerais (para cruzamento rápido)
    print("📰 [Brain] Buscando notícias...")
    all_news = fetch_crypto_news(limit=50)
    print(f"✅ [Brain] {len(all_news)} notícias coletadas")
    
    # Passo 3: Para cada gem, buscar notícias específicas e calcular score
    print("🔍 [Brain] Cruzando dados...")
    
    for gem in gems:
        symbol = gem.get('symbol', '').upper()
        name = gem.get('name', '').lower()
        
        # Filtra notícias que mencionam a gem
        related_news = []
        for news in all_news:
            title = news.get('title', '').lower()
            # Match por símbolo ou nome
            if symbol.lower() in title or name in title:
                related_news.append(news)
        
        # Se não encontrou notícias gerais, busca específica
        if not related_news:
            related_news = search_news_for_symbol(symbol, gemini_api_key)
        
        # Calcula score de oportunidade
        opportunity = calculate_opportunity_score(gem, related_news)
        opportunities.append(opportunity)
    
    # Passo 4: Ordenar por score
    opportunities.sort(key=lambda x: x['total_score'], reverse=True)
    
    # Estatísticas
    hot_count = sum(1 for o in opportunities if o['classification'] == 'HOT')
    warm_count = sum(1 for o in opportunities if o['classification'] == 'WARM')
    
    print(f"\n📊 [Brain] Análise completa:")
    print(f"   🔥 HOT: {hot_count}")
    print(f"   ⚡ WARM: {warm_count}")
    print(f"   ❄️ COLD: {len(opportunities) - hot_count - warm_count}")
    
    return opportunities[:limit]


def format_signal_alert(opportunity: Dict) -> str:
    """
    Formata uma oportunidade como mensagem de alerta.
    
    Útil para enviar via Telegram ou exibir na UI.
    
    Args:
        opportunity: Dict de oportunidade do generate_opportunity_signals
    
    Returns:
        String formatada para alerta
    """
    gem = opportunity.get('gem_data', {})
    
    msg = f"""
{opportunity['emoji']} *{opportunity['classification']}* - {opportunity['symbol']}

📊 *Score:* {opportunity['total_score']}/{opportunity['max_score']}
💰 *Preço:* ${gem.get('price', 0):.6f}
📈 *MCap:* ${gem.get('market_cap', 0)/1_000_000:.1f}M
📊 *Vol 24h:* ${gem.get('volume_24h', 0)/1_000_000:.1f}M
🔄 *Var 24h:* {gem.get('price_change_24h', 0):+.1f}%

📋 *Fatores:*
"""
    
    for exp in opportunity.get('explanations', []):
        msg += f"• {exp}\n"
    
    if opportunity.get('related_news'):
        msg += "\n📰 *Notícias:*\n"
        for news in opportunity['related_news'][:2]:
            msg += f"• {news.get('title', '')[:60]}...\n"
    
    msg += f"\n⚡ *Ação:* {opportunity['action']}"
    
    return msg


# ============================================================================
# TESTE STANDALONE
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🧠 BRAIN ANALYZER - Sistema de Oportunidades")
    print("=" * 60)
    
    opportunities = generate_opportunity_signals(limit=5)
    
    if opportunities:
        for i, opp in enumerate(opportunities, 1):
            print(f"\n{'='*60}")
            print(format_signal_alert(opp))
    else:
        print("\n❌ Nenhuma oportunidade identificada")
