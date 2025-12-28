###############################################################################
# FILE: sniper_logic.py - Sistema de Detecção de Acumulação PRÉ-PUMP
# 
# OBJETIVO CRÍTICO:
# -----------------
# Identificar criptomoedas em fase de ACUMULAÇÃO ANTES do preço explodir.
# Detectar quando "Smart Money" está comprando silenciosamente.
#
# 3 REGRAS DE DETECÇÃO:
# ---------------------
# Regra A: Divergência Volume/Preço (Iceberg Orders)
#   - Volume > 300% da média 24h MAS preço < 5% de variação
#   - Significado: Grandes compradores acumulando sem mover preço
#
# Regra B: Liquidity Snipe (Lançamentos)
#   - Pool nova (< 1h) com liquidez > $50K
#   - Significado: Projeto novo com capital real
#
# Regra C: Smart Money Tracker
#   - Baleias comprando token que nunca tiveram
#   - Significado: Insider information ou análise superior
#
# AVISO DE RISCO:
# Este código é para fins educacionais. Trading de criptomoedas envolve
# alto risco. Não invista mais do que pode perder.
###############################################################################

import requests
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

# Thresholds para Regra A
VOLUME_SPIKE_THRESHOLD = 3.0      # 300% = 3x a média
PRICE_CHANGE_MAX = 5.0             # Máximo 5% de variação de preço
VOLUME_PERIOD_HOURS = 24           # Período para calcular média

# Thresholds para Regra B
MIN_LIQUIDITY_USD = 50_000         # Mínimo $50K de liquidez
MAX_POOL_AGE_HOURS = 1             # Pool criada há menos de 1 hora

# Thresholds para Score de Confiança
CONFIDENCE_THRESHOLDS = {
    'ignore': 50,      # < 50% = ignorar
    'monitor': 75,     # 50-75% = monitorar
    'alert': 90,       # 75-90% = alerta
    'max_alert': 100   # > 90% = ALERTA MÁXIMO
}

# APIs
DEXSCREENER_API = "https://api.dexscreener.com/latest"
COINGECKO_API = "https://api.coingecko.com/api/v3"

# Request settings
REQUEST_TIMEOUT = 15

# Smart Money Watch List (carteiras de baleias conhecidas)
# Adicione endereços reais aqui
DEFAULT_WATCH_LIST = {
    'ethereum': [
        # Exemplo: "0x..." 
    ],
    'solana': [
        # Exemplo: "ABC..." 
    ]
}


# ============================================================================
# REGRA A: DIVERGÊNCIA VOLUME/PREÇO
# ============================================================================

def check_accumulation_pattern_dex(
    token_address: str,
    chain: str = "solana",
    volume_threshold: float = VOLUME_SPIKE_THRESHOLD,
    price_threshold: float = PRICE_CHANGE_MAX
) -> Optional[Dict]:
    """
    Regra A (DEX): Detecta padrão de acumulação em DEX via DexScreener.
    
    LÓGICA FINANCEIRA:
    ------------------
    Quando grandes players querem acumular uma moeda, eles usam "Iceberg Orders":
    ordens grandes fracionadas em pequenas para não mover o preço.
    
    Resultado: Volume MUITO alto, mas preço quase não se move.
    Isso é o "cheiro" de acumulação institucional.
    
    GATILHO:
    - Volume 1h > 300% da média 24h
    - Variação de preço < 5%
    
    Args:
        token_address: Endereço do contrato do token
        chain: Rede blockchain (solana, ethereum, bsc, etc)
        volume_threshold: Múltiplo do volume médio para trigger (3.0 = 300%)
        price_threshold: Máximo % de variação de preço
    
    Returns:
        Dict com análise ou None se erro
    """
    try:
        # Busca dados do par via DexScreener
        url = f"{DEXSCREENER_API}/dex/tokens/{token_address}"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        pairs = data.get('pairs', [])
        if not pairs:
            return None
        
        # Usa o par com maior liquidez
        pair = max(pairs, key=lambda x: float(x.get('liquidity', {}).get('usd', 0) or 0))
        
        # Extrai métricas
        volume_h1 = float(pair.get('volume', {}).get('h1', 0) or 0)
        volume_h24 = float(pair.get('volume', {}).get('h24', 0) or 0)
        price_change_h1 = float(pair.get('priceChange', {}).get('h1', 0) or 0)
        price_change_h24 = float(pair.get('priceChange', {}).get('h24', 0) or 0)
        liquidity = float(pair.get('liquidity', {}).get('usd', 0) or 0)
        
        # Calcula média horária de volume nas últimas 24h
        avg_volume_h1 = volume_h24 / 24 if volume_h24 > 0 else 0
        
        # Calcula ratio de spike de volume
        volume_ratio = volume_h1 / avg_volume_h1 if avg_volume_h1 > 0 else 0
        
        # ================================================================
        # DETECÇÃO DE ACUMULAÇÃO
        # Volume alto (>300%) + Preço estável (<5%) = Acumulação
        # ================================================================
        is_accumulating = (
            volume_ratio >= volume_threshold and
            abs(price_change_h1) <= price_threshold and
            liquidity >= 10000  # Mínimo $10K de liquidez
        )
        
        # Calcula confiança (0-100)
        confidence = 0
        signals = []
        
        if volume_ratio >= volume_threshold:
            confidence += 25
            signals.append(f"📈 Volume {volume_ratio:.1f}x acima da média")
        
        if abs(price_change_h1) <= price_threshold:
            confidence += 25
            signals.append(f"💤 Preço estável ({price_change_h1:+.1f}%)")
        
        if volume_ratio >= 5.0:  # Spike extremo
            confidence += 15
            signals.append(f"🚨 Volume EXTREMO ({volume_ratio:.1f}x)")
        
        if liquidity >= MIN_LIQUIDITY_USD:
            confidence += 10
            signals.append(f"💧 Liquidez ${liquidity:,.0f}")
        
        return {
            'rule': 'A',
            'rule_name': 'Volume/Price Divergence',
            'symbol': pair.get('baseToken', {}).get('symbol', 'N/A'),
            'name': pair.get('baseToken', {}).get('name', 'N/A'),
            'address': token_address,
            'chain': pair.get('chainId', chain),
            'dex': pair.get('dexId', 'N/A'),
            'price_usd': float(pair.get('priceUsd', 0) or 0),
            'volume_h1': volume_h1,
            'volume_h24': volume_h24,
            'avg_volume_h1': avg_volume_h1,
            'volume_ratio': volume_ratio,
            'price_change_h1': price_change_h1,
            'price_change_h24': price_change_h24,
            'liquidity_usd': liquidity,
            'is_accumulating': is_accumulating,
            'confidence': min(100, confidence),
            'signals': signals,
            'url': pair.get('url', f"https://dexscreener.com/{chain}/{token_address}"),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ [Regra A] Erro ao analisar {token_address}: {e}")
        return None


def check_accumulation_pattern_cex(
    symbol: str,
    volume_threshold: float = VOLUME_SPIKE_THRESHOLD,
    price_threshold: float = PRICE_CHANGE_MAX
) -> Optional[Dict]:
    """
    Regra A (CEX): Detecta padrão de acumulação em exchanges centralizadas.
    
    Usa ccxt para buscar dados de Binance ou outras CEX.
    
    Args:
        symbol: Par de trading (ex: 'BTC/USDT')
        volume_threshold: Múltiplo do volume médio
        price_threshold: Máximo % de variação de preço
    
    Returns:
        Dict com análise ou None se erro
    """
    try:
        import ccxt
        exchange = ccxt.binance({'enableRateLimit': True})
        
        # Busca candles de 1h das últimas 24h
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=25)
        
        if not ohlcv or len(ohlcv) < 24:
            return None
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Calcula métricas
        avg_volume = df['volume'].iloc[:-1].mean()  # Média excluindo candle atual
        current_volume = df['volume'].iloc[-2]       # Último candle fechado
        
        # Variação de preço do último candle
        open_price = df['open'].iloc[-2]
        close_price = df['close'].iloc[-2]
        price_change = ((close_price - open_price) / open_price) * 100
        
        # Volume ratio
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        
        # Volatilidade (high-low)
        volatility = ((df['high'].iloc[-2] - df['low'].iloc[-2]) / open_price) * 100
        
        # Detecção de acumulação
        is_accumulating = (
            volume_ratio >= volume_threshold and
            abs(price_change) <= price_threshold
        )
        
        # Calcula confiança
        confidence = 0
        signals = []
        
        if volume_ratio >= volume_threshold:
            confidence += 25
            signals.append(f"📈 Volume {volume_ratio:.1f}x acima da média")
        
        if abs(price_change) <= price_threshold:
            confidence += 25
            signals.append(f"💤 Preço estável ({price_change:+.2f}%)")
        
        if volatility <= 2.0:  # Baixa volatilidade = acumulação suave
            confidence += 15
            signals.append(f"😴 Volatilidade baixa ({volatility:.2f}%)")
        
        if volume_ratio >= 5.0:
            confidence += 10
            signals.append("🚨 Volume EXTREMO")
        
        return {
            'rule': 'A',
            'rule_name': 'Volume/Price Divergence (CEX)',
            'symbol': symbol,
            'exchange': 'Binance',
            'current_price': close_price,
            'current_volume': current_volume,
            'avg_volume': avg_volume,
            'volume_ratio': volume_ratio,
            'price_change_pct': price_change,
            'volatility_pct': volatility,
            'is_accumulating': is_accumulating,
            'confidence': min(100, confidence),
            'signals': signals,
            'url': f"https://www.binance.com/trade/{symbol.replace('/', '_')}",
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ [Regra A CEX] Erro ao analisar {symbol}: {e}")
        return None


# ============================================================================
# REGRA B: LIQUIDITY SNIPE (NOVOS LANÇAMENTOS)
# ============================================================================

def check_liquidity_snipe(
    chain: str = "solana",
    min_liquidity: float = MIN_LIQUIDITY_USD,
    max_age_hours: float = MAX_POOL_AGE_HOURS
) -> List[Dict]:
    """
    Regra B: Detecta novos pools de liquidez com potencial.
    
    LÓGICA FINANCEIRA:
    ------------------
    Novos tokens com liquidez significativa (>$50K) indicam projeto sério.
    Se a liquidez está travada, o risco de rug pull é menor.
    Entrar cedo em um projeto legítimo = maior potencial de ganho.
    
    GATILHO:
    - Pool criada há menos de 1 hora
    - Liquidez > $50.000
    - (Opcional) Liquidez travada
    
    Args:
        chain: Rede blockchain
        min_liquidity: Liquidez mínima em USD
        max_age_hours: Idade máxima da pool em horas
    
    Returns:
        Lista de pools detectadas
    """
    opportunities = []
    
    try:
        # Busca perfis de tokens recentes via DexScreener
        url = f"{DEXSCREENER_API}/token-profiles/latest/v1"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        
        if response.status_code != 200:
            # Fallback: buscar trending com filtro de tempo
            url = f"{DEXSCREENER_API}/dex/search?q={chain}"
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
        
        response.raise_for_status()
        data = response.json()
        
        # Processa tokens/pares
        pairs = data.get('pairs', []) if 'pairs' in data else []
        
        for pair in pairs[:50]:  # Limita para evitar sobrecarga
            try:
                # Filtra por chain
                if pair.get('chainId', '').lower() != chain.lower():
                    continue
                
                liquidity = float(pair.get('liquidity', {}).get('usd', 0) or 0)
                pair_created = pair.get('pairCreatedAt', 0)
                
                # Verifica idade da pool
                if pair_created:
                    created_time = datetime.fromtimestamp(pair_created / 1000)
                    age_hours = (datetime.now() - created_time).total_seconds() / 3600
                else:
                    age_hours = 999  # Desconhecido = assume antiga
                
                # ============================================================
                # FILTRO: Pool nova + Liquidez significativa
                # ============================================================
                if age_hours <= max_age_hours and liquidity >= min_liquidity:
                    
                    confidence = 0
                    signals = []
                    
                    # Score por liquidez
                    if liquidity >= 100_000:
                        confidence += 30
                        signals.append(f"💎 Liquidez alta ${liquidity:,.0f}")
                    elif liquidity >= 50_000:
                        confidence += 20
                        signals.append(f"💧 Liquidez ${liquidity:,.0f}")
                    
                    # Score por idade
                    if age_hours <= 0.5:  # Menos de 30 min
                        confidence += 25
                        signals.append(f"🆕 Pool recém-criada ({age_hours*60:.0f}min)")
                    elif age_hours <= 1:
                        confidence += 15
                        signals.append(f"⏰ Pool nova ({age_hours:.1f}h)")
                    
                    # Volume inicial
                    vol_h1 = float(pair.get('volume', {}).get('h1', 0) or 0)
                    if vol_h1 > liquidity * 0.2:  # Volume > 20% da liquidez
                        confidence += 20
                        signals.append(f"📈 Volume inicial alto")
                    
                    opportunities.append({
                        'rule': 'B',
                        'rule_name': 'Liquidity Snipe',
                        'symbol': pair.get('baseToken', {}).get('symbol', 'N/A'),
                        'name': pair.get('baseToken', {}).get('name', 'N/A'),
                        'address': pair.get('baseToken', {}).get('address', ''),
                        'chain': pair.get('chainId', chain),
                        'dex': pair.get('dexId', 'N/A'),
                        'price_usd': float(pair.get('priceUsd', 0) or 0),
                        'liquidity_usd': liquidity,
                        'volume_h1': vol_h1,
                        'age_hours': age_hours,
                        'age_minutes': age_hours * 60,
                        'confidence': min(100, confidence),
                        'signals': signals,
                        'url': pair.get('url', ''),
                        'timestamp': datetime.now().isoformat()
                    })
                    
            except Exception:
                continue
        
        # Ordena por confiança
        opportunities.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        
    except Exception as e:
        print(f"❌ [Regra B] Erro ao buscar novos pools: {e}")
    
    return opportunities


# ============================================================================
# REGRA C: SMART MONEY TRACKER
# ============================================================================

def check_smart_money(
    watch_list: Optional[Dict[str, List[str]]] = None,
    chain: str = "solana"
) -> List[Dict]:
    """
    Regra C: Monitora transações de carteiras de "Smart Money".
    
    LÓGICA FINANCEIRA:
    ------------------
    Algumas carteiras têm histórico de acertar trades cedo.
    Quando essas carteiras compram um token novo (que nunca tiveram),
    pode indicar insider knowledge ou análise superior.
    
    GATILHO:
    - Wallet da watch list compra token novo
    - Token que ela nunca possuiu antes
    
    Args:
        watch_list: Dict de {chain: [endereços]} para monitorar
        chain: Chain padrão se não especificado
    
    Returns:
        Lista de alertas de Smart Money
    """
    if watch_list is None:
        watch_list = DEFAULT_WATCH_LIST
    
    alerts = []
    
    wallets = watch_list.get(chain, [])
    if not wallets:
        return []
    
    try:
        for wallet in wallets:
            # Para Solana, usar Solscan ou Helius
            if chain.lower() == "solana":
                alerts.extend(_check_solana_wallet(wallet))
            # Para Ethereum, usar Etherscan
            elif chain.lower() in ["ethereum", "eth"]:
                alerts.extend(_check_ethereum_wallet(wallet))
    
    except Exception as e:
        print(f"❌ [Regra C] Erro ao monitorar smart money: {e}")
    
    return alerts


def _check_solana_wallet(wallet_address: str) -> List[Dict]:
    """Verifica transações recentes de uma wallet Solana."""
    # Placeholder - implementar com Solscan API ou Helius
    # https://docs.solscan.io/api-reference/account/account-tokens
    return []


def _check_ethereum_wallet(wallet_address: str) -> List[Dict]:
    """Verifica transações recentes de uma wallet Ethereum."""
    # Placeholder - implementar com Etherscan API
    # Requer API key do Etherscan
    return []


# ============================================================================
# FUNÇÃO DE SCORE COMBINADO
# ============================================================================

def calculate_confidence_score(result: Dict) -> int:
    """
    Calcula score de confiança combinado (0-100%).
    
    Args:
        result: Resultado de qualquer regra
    
    Returns:
        Score inteiro 0-100
    """
    return result.get('confidence', 0)


def classify_alert(confidence: int) -> Tuple[str, str, str]:
    """
    Classifica o alerta baseado no score de confiança.
    
    Returns:
        Tuple de (classificação, emoji, ação)
    """
    if confidence >= 90:
        return ("MAX_ALERT", "🔥", "ALERTA MÁXIMO - Múltiplos sinais fortes!")
    elif confidence >= 75:
        return ("ALERT", "🟢", "ALERTA - Oportunidade detectada")
    elif confidence >= 50:
        return ("MONITOR", "🟡", "MONITORAR - Potencial interessante")
    else:
        return ("IGNORE", "⚪", "Ignorar - Sinais fracos")


# ============================================================================
# SCANNER PRINCIPAL
# ============================================================================

def run_accumulation_scan(
    tokens: Optional[List[str]] = None,
    cex_pairs: Optional[List[str]] = None,
    chain: str = "solana",
    watch_list: Optional[Dict] = None
) -> Dict:
    """
    Executa scan completo de todas as regras.
    
    Args:
        tokens: Lista de endereços de tokens para Regra A (DEX)
        cex_pairs: Lista de pares CEX para Regra A (CEX)
        chain: Chain padrão para scans
        watch_list: Wallets para Regra C
    
    Returns:
        Dict com todos os alertas encontrados
    """
    print(f"🎯 [Sniper] Iniciando scan de acumulação...")
    print(f"⏰ Hora: {datetime.now().strftime('%H:%M:%S')}")
    print("-" * 60)
    
    all_alerts = {
        'rule_a_dex': [],
        'rule_a_cex': [],
        'rule_b': [],
        'rule_c': [],
        'high_confidence': []  # Todos com confidence > 75%
    }
    
    # Regra A (DEX)
    if tokens:
        print(f"📊 [Regra A DEX] Analisando {len(tokens)} tokens...")
        for token in tokens:
            result = check_accumulation_pattern_dex(token, chain)
            if result and result.get('is_accumulating'):
                all_alerts['rule_a_dex'].append(result)
                if result.get('confidence', 0) >= 75:
                    all_alerts['high_confidence'].append(result)
    
    # Regra A (CEX)
    if cex_pairs:
        print(f"📊 [Regra A CEX] Analisando {len(cex_pairs)} pares...")
        for pair in cex_pairs:
            result = check_accumulation_pattern_cex(pair)
            if result and result.get('is_accumulating'):
                all_alerts['rule_a_cex'].append(result)
                if result.get('confidence', 0) >= 75:
                    all_alerts['high_confidence'].append(result)
    
    # Regra B
    print(f"💧 [Regra B] Buscando novos pools em {chain}...")
    new_pools = check_liquidity_snipe(chain)
    all_alerts['rule_b'] = new_pools
    for pool in new_pools:
        if pool.get('confidence', 0) >= 75:
            all_alerts['high_confidence'].append(pool)
    
    # Regra C
    if watch_list:
        print(f"🐋 [Regra C] Monitorando {sum(len(v) for v in watch_list.values())} wallets...")
        smart_money = check_smart_money(watch_list, chain)
        all_alerts['rule_c'] = smart_money
        for alert in smart_money:
            if alert.get('confidence', 0) >= 75:
                all_alerts['high_confidence'].append(alert)
    
    # Ordena high_confidence por score
    all_alerts['high_confidence'].sort(
        key=lambda x: x.get('confidence', 0), 
        reverse=True
    )
    
    # Resumo
    print("\n" + "=" * 60)
    print("📋 RESUMO DO SCAN:")
    print(f"   🔍 Regra A (DEX): {len(all_alerts['rule_a_dex'])} alertas")
    print(f"   📈 Regra A (CEX): {len(all_alerts['rule_a_cex'])} alertas")
    print(f"   💧 Regra B: {len(all_alerts['rule_b'])} pools")
    print(f"   🐋 Regra C: {len(all_alerts['rule_c'])} smart money")
    print(f"   🔥 ALTA CONFIANÇA: {len(all_alerts['high_confidence'])}")
    print("=" * 60)
    
    return all_alerts


# ============================================================================
# TESTE STANDALONE
# ============================================================================

if __name__ == "__main__":
    print("🎯 SNIPER LOGIC - Teste de Detecção de Acumulação")
    print("=" * 60)
    
    # Teste Regra A (CEX)
    print("\n📊 Testando Regra A (CEX) com BTC/USDT...")
    result = check_accumulation_pattern_cex('BTC/USDT')
    if result:
        print(f"   Volume Ratio: {result['volume_ratio']:.2f}x")
        print(f"   Price Change: {result['price_change_pct']:+.2f}%")
        print(f"   Acumulando: {'✅' if result['is_accumulating'] else '❌'}")
        print(f"   Confiança: {result['confidence']}%")
        for signal in result['signals']:
            print(f"   • {signal}")
    
    # Teste Regra B
    print("\n💧 Testando Regra B (Novos Pools)...")
    pools = check_liquidity_snipe("solana", min_liquidity=10000)  # Reduzido para teste
    print(f"   Encontrados: {len(pools)} pools")
    for pool in pools[:3]:
        print(f"   • {pool['symbol']}: ${pool['liquidity_usd']:,.0f} liq, {pool['confidence']}% conf")
