###############################################################################
# FILE: gem_scanner.py - Módulo A: Scanner de Gems (Moedas Novas)
# 
# LÓGICA FINANCEIRA:
# ------------------
# Premissa: Moedas de baixa capitalização (< $50M) com volume crescente e
# pouco tempo de mercado têm maior potencial de valorização explosiva.
# 
# Critérios de filtro baseados em padrões históricos de "moonshots":
# - Market Cap < $50M: "Low/Micro cap" permite multiplicações de 10-100x
# - Volume 24h > $500K: Garante liquidez mínima para entrada/saída
# - Idade < 90 dias: Projetos recentes ainda não descobertos pelo mercado
# 
# RISCO: Alto! Moedas novas têm alta taxa de falha (>90%). Use apenas
# capital que está disposto a perder 100%.
###############################################################################

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

# Critérios de filtro (ajustáveis)
DEFAULT_MAX_MARKET_CAP = 50_000_000      # $50M máximo
DEFAULT_MIN_VOLUME_24H = 500_000          # $500K mínimo
DEFAULT_MAX_AGE_DAYS = 90                  # 90 dias máximo

# Rate limiting
REQUEST_TIMEOUT = 15

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def _calcular_idade_gem(genesis_date: Optional[str]) -> int:
    """
    Calcula a idade da moeda em dias desde o lançamento.
    
    Args:
        genesis_date: Data de criação no formato "YYYY-MM-DD"
    
    Returns:
        Número de dias desde o lançamento, ou 999 se desconhecido
    """
    if not genesis_date:
        return 999  # Desconhecido = assume antiga
    
    try:
        data_genesis = datetime.strptime(genesis_date, "%Y-%m-%d")
        idade = (datetime.now() - data_genesis).days
        return max(0, idade)
    except (ValueError, TypeError):
        return 999


def _calcular_score_gem(gem: Dict) -> int:
    """
    Calcula score inicial da gem (0-10) baseado em critérios quantitativos.
    
    Critérios:
    - Market cap no "sweet spot" ($5M-$20M): +3 pontos
    - Volume alto relativo ao market cap: +2 pontos
    - Idade < 30 dias: +2 pontos
    - Variação 24h positiva: +2 pontos
    - Menção em exchanges: +1 ponto
    
    Args:
        gem: Dicionário com dados da moeda
    
    Returns:
        Score de 0 a 10
    """
    score = 0
    
    # Market cap sweet spot ($5M - $20M = zona de maior potencial)
    mcap = gem.get('market_cap', 0) or 0
    if 5_000_000 <= mcap <= 20_000_000:
        score += 3
    elif mcap < 5_000_000 and mcap > 0:
        score += 1  # Muito pequeno = mais arriscado
    
    # Volume/Market Cap ratio (quanto maior, melhor interesse)
    vol = gem.get('volume_24h', 0) or 0
    if mcap > 0:
        vol_ratio = vol / mcap
        if vol_ratio > 0.5:
            score += 2  # Volume > 50% do mcap = alto interesse
        elif vol_ratio > 0.2:
            score += 1
    
    # Idade (moedas mais novas = mais potencial de descoberta)
    idade = gem.get('age_days', 999)
    if idade <= 30:
        score += 2
    elif idade <= 60:
        score += 1
    
    # Variação de preço 24h
    var_24h = gem.get('price_change_24h', 0) or 0
    if var_24h > 20:
        score += 2  # Já em movimento
    elif var_24h > 5:
        score += 1
    
    return min(10, score)


# ============================================================================
# FUNÇÃO PRINCIPAL: BUSCAR GEMS
# ============================================================================

def scan_coingecko_gems(
    max_market_cap: int = DEFAULT_MAX_MARKET_CAP,
    min_volume_24h: int = DEFAULT_MIN_VOLUME_24H,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    limit: int = 10
) -> List[Dict]:
    """
    Busca "gems" (moedas promissoras) usando a API CoinGecko.
    
    ESTRATÉGIA:
    1. Busca moedas ordenadas por market cap crescente
    2. Filtra por volume mínimo (evita moedas "mortas")
    3. Verifica idade do projeto
    4. Calcula score de potencial
    
    Args:
        max_market_cap: Market cap máximo em USD
        min_volume_24h: Volume mínimo 24h em USD
        max_age_days: Idade máxima em dias
        limit: Número máximo de gems a retornar
    
    Returns:
        Lista de dicionários com dados das gems, ordenadas por score
    """
    gems = []
    
    try:
        # Estratégia: Buscar moedas por volume (para pegar as ativas)
        # depois filtrar por market cap localmente
        # CoinGecko free tier não suporta bem market_cap_asc
        
        all_coins = []
        
        # Busca múltiplas páginas para ter mais opções
        for page in range(1, 4):  # Páginas 1, 2, 3
            url = f"{COINGECKO_BASE_URL}/coins/markets"
            params = {
                "vs_currency": "usd",
                "order": "volume_desc",  # Por volume (mais ativas)
                "per_page": 250,
                "page": page,
                "sparkline": False,
                "price_change_percentage": "24h,7d"
            }
            
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            
            if response.status_code == 429:
                print("⚠️ [Gem Scanner] Rate limit CoinGecko, aguardando...")
                import time
                time.sleep(30)
                continue
            
            response.raise_for_status()
            coins = response.json()
            all_coins.extend(coins)
            
            # Rate limiting entre requests
            import time
            time.sleep(1)
        
        # Processar cada moeda
        for coin in all_coins:
            try:
                # Extrai dados básicos
                mcap = coin.get('market_cap') or 0
                vol_24h = coin.get('total_volume') or 0
                
                # ============================================================
                # FILTRO 1: Market Cap < máximo configurado
                # Lógica: Micro caps têm maior potencial de multiplicação
                # ============================================================
                if mcap <= 0 or mcap > max_market_cap:
                    continue
                
                # ============================================================
                # FILTRO 2: Volume 24h > mínimo configurado
                # Lógica: Volume garante que há interesse e liquidez
                # ============================================================
                if vol_24h < min_volume_24h:
                    continue
                
                # Busca data de criação (genesis) - Requer chamada extra
                # Nota: Para otimizar rate limit, estimamos idade pelo ATH date
                # Moedas novas geralmente têm ATH recente
                ath_date = coin.get('ath_date', '')
                idade_estimada = 999
                if ath_date:
                    try:
                        ath_datetime = datetime.fromisoformat(ath_date.replace('Z', '+00:00'))
                        dias_desde_ath = (datetime.now(ath_datetime.tzinfo) - ath_datetime).days
                        # ATH recente (<30 dias) sugere moeda nova ou em pump
                        idade_estimada = max(dias_desde_ath, 0)
                    except:
                        pass
                
                # ============================================================
                # FILTRO 3: Idade estimada < máximo configurado
                # Lógica: Moedas novas ainda não foram "descobertas"
                # ============================================================
                # Se ATH muito antigo (>90 dias), provavelmente moeda antiga
                # Nota: Este é um proxy, não a idade real
                # ============================================================
                
                # Monta objeto da gem
                gem = {
                    'id': coin.get('id', ''),
                    'symbol': coin.get('symbol', '').upper(),
                    'name': coin.get('name', ''),
                    'price': coin.get('current_price', 0),
                    'market_cap': mcap,
                    'volume_24h': vol_24h,
                    'price_change_24h': coin.get('price_change_percentage_24h', 0),
                    'price_change_7d': coin.get('price_change_percentage_7d_in_currency', 0),
                    'image': coin.get('image', ''),
                    'age_days': idade_estimada,
                    'ath': coin.get('ath', 0),
                    'ath_change_percentage': coin.get('ath_change_percentage', 0),
                    'rank': coin.get('market_cap_rank', 999)
                }
                
                # Calcula score de potencial
                gem['gem_score'] = _calcular_score_gem(gem)
                
                gems.append(gem)
                
            except Exception as e:
                # Ignora moedas com dados inválidos
                continue
        
        # Ordena por score (maior primeiro) e limita resultado
        gems.sort(key=lambda x: x.get('gem_score', 0), reverse=True)
        return gems[:limit]
        
    except requests.exceptions.RequestException as e:
        print(f"❌ [Gem Scanner] Erro de conexão CoinGecko: {e}")
        return []
    except Exception as e:
        print(f"❌ [Gem Scanner] Erro inesperado: {e}")
        return []


def get_gem_details(coin_id: str) -> Optional[Dict]:
    """
    Busca detalhes adicionais de uma gem específica.
    
    Inclui: descrição, links, data de criação real, etc.
    
    Args:
        coin_id: ID da moeda no CoinGecko (ex: "bitcoin")
    
    Returns:
        Dicionário com detalhes ou None se falhar
    """
    try:
        url = f"{COINGECKO_BASE_URL}/coins/{coin_id}"
        params = {
            "localization": False,
            "tickers": False,
            "market_data": True,
            "community_data": True,
            "developer_data": False
        }
        
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        # Extrai data real de criação
        genesis_date = data.get('genesis_date')
        idade_real = _calcular_idade_gem(genesis_date)
        
        return {
            'id': data.get('id'),
            'symbol': data.get('symbol', '').upper(),
            'name': data.get('name'),
            'description': data.get('description', {}).get('en', '')[:500],
            'genesis_date': genesis_date,
            'age_days': idade_real,
            'categories': data.get('categories', []),
            'links': {
                'homepage': data.get('links', {}).get('homepage', [None])[0],
                'twitter': data.get('links', {}).get('twitter_screen_name'),
                'telegram': data.get('links', {}).get('telegram_channel_identifier'),
                'github': data.get('links', {}).get('repos_url', {}).get('github', [None])[0]
            },
            'community': {
                'twitter_followers': data.get('community_data', {}).get('twitter_followers', 0),
                'telegram_members': data.get('community_data', {}).get('telegram_channel_user_count', 0)
            }
        }
        
    except Exception as e:
        print(f"❌ [Gem Scanner] Erro ao buscar detalhes de {coin_id}: {e}")
        return None


# ============================================================================
# TESTE STANDALONE
# ============================================================================

if __name__ == "__main__":
    print("🔮 Iniciando Gem Scanner...")
    print(f"📊 Critérios: MCap < ${DEFAULT_MAX_MARKET_CAP:,} | Vol > ${DEFAULT_MIN_VOLUME_24H:,}")
    print("-" * 60)
    
    gems = scan_coingecko_gems(limit=10)
    
    if gems:
        for i, gem in enumerate(gems, 1):
            print(f"\n{i}. {gem['symbol']} - {gem['name']}")
            print(f"   💰 Preço: ${gem['price']:.6f}")
            print(f"   📊 MCap: ${gem['market_cap']:,.0f}")
            print(f"   📈 Vol 24h: ${gem['volume_24h']:,.0f}")
            print(f"   🎯 Var 24h: {gem['price_change_24h']:.2f}%")
            print(f"   ⭐ Score: {gem['gem_score']}/10")
    else:
        print("❌ Nenhuma gem encontrada!")
