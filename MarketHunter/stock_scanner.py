###############################################################################
# FILE: stock_scanner.py - Scanner de Ações (B3 + EUA) com yfinance
# 
# LÓGICA FINANCEIRA:
# ------------------
# Este scanner monitora ações brasileiras (B3) e americanas (NYSE/NASDAQ)
# buscando dois padrões de oportunidade:
#
# 1. DIP BUYING (Compra na Queda):
#    - Preço caiu > 2% em 1 hora
#    - Volume normal ou baixo (não é pânico)
#    - Oportunidade: Comprar "barato" em correção técnica
#
# 2. BREAKOUT (Rompimento):
#    - Preço subiu > 3% em 1 hora
#    - Volume > 2x a média (confirmação)
#    - Oportunidade: Entrar no início de um rally
#
# AVISO: Este código é para fins educacionais. Não constitui
# conselho financeiro. Consulte um profissional antes de investir.
###############################################################################

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

# Thresholds para detecção de oportunidades
DIP_THRESHOLD_PCT = -2.0           # Queda de 2% = oportunidade de dip
BREAKOUT_THRESHOLD_PCT = 3.0       # Alta de 3% = possível breakout
VOLUME_SPIKE_THRESHOLD = 2.0       # Volume 2x acima da média

# Timeframe padrão
DEFAULT_INTERVAL = "15m"           # Candles de 15 minutos
DEFAULT_PERIOD = "1d"              # Último dia de dados

# Watchlists padrão
WATCHLIST_BRASIL = [
    "PETR4.SA",  # Petrobras
    "VALE3.SA",  # Vale
    "ITUB4.SA",  # Itaú
    "BBDC4.SA",  # Bradesco
    "B3SA3.SA",  # B3
    "WEGE3.SA",  # WEG
    "RENT3.SA",  # Localiza
    "MGLU3.SA",  # Magazine Luiza
    "BBAS3.SA",  # Banco do Brasil
    "ABEV3.SA",  # Ambev
]

WATCHLIST_EUA = [
    "AAPL",      # Apple
    "GOOGL",     # Alphabet
    "MSFT",      # Microsoft
    "AMZN",      # Amazon
    "NVDA",      # NVIDIA
    "TSLA",      # Tesla
    "META",      # Meta
    "AMD",       # AMD
    "JPM",       # JPMorgan
    "V",         # Visa
]

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def _calculate_change_1h(df: pd.DataFrame) -> float:
    """
    Calcula a variação percentual na última hora.
    
    Para timeframe 15m, usa os últimos 4 candles.
    """
    if len(df) < 4:
        return 0.0
    
    price_1h_ago = df['Close'].iloc[-4]
    price_now = df['Close'].iloc[-1]
    
    if price_1h_ago == 0:
        return 0.0
    
    return ((price_now - price_1h_ago) / price_1h_ago) * 100


def _calculate_volume_ratio(df: pd.DataFrame) -> float:
    """
    Calcula o ratio do volume atual vs média.
    """
    if len(df) < 5:
        return 1.0
    
    avg_volume = df['Volume'].iloc[:-1].mean()
    current_volume = df['Volume'].iloc[-1]
    
    if avg_volume == 0:
        return 1.0
    
    return current_volume / avg_volume


def _detect_pattern(change_1h: float, volume_ratio: float) -> Dict:
    """
    Detecta padrão de DIP ou BREAKOUT.
    
    Returns:
        Dict com pattern, signal, confidence, e explicação
    """
    pattern = None
    signal = None
    confidence = 0
    explanation = []
    
    # ================================================================
    # PATTERN 1: DIP BUYING (Compra na Queda)
    # Lógica: Queda > 2% pode ser oportunidade de comprar barato
    # ================================================================
    if change_1h <= DIP_THRESHOLD_PCT:
        pattern = "DIP"
        signal = "COMPRAR"
        confidence = 60
        explanation.append(f"📉 Queda de {change_1h:.2f}% na última hora")
        
        # Bonus: Volume baixo = não é pânico, mais seguro
        if volume_ratio < 1.5:
            confidence += 20
            explanation.append("💤 Volume normal (não é pânico de venda)")
        
        # Queda maior = mais desconto
        if change_1h <= -3.0:
            confidence += 10
            explanation.append("💎 Desconto significativo")
    
    # ================================================================
    # PATTERN 2: BREAKOUT (Rompimento)
    # Lógica: Alta > 3% com volume alto = força compradora
    # ================================================================
    elif change_1h >= BREAKOUT_THRESHOLD_PCT:
        pattern = "BREAKOUT"
        signal = "COMPRAR"
        confidence = 50
        explanation.append(f"📈 Alta de {change_1h:.2f}% na última hora")
        
        # Volume alto OBRIGATÓRIO para breakout válido
        if volume_ratio >= VOLUME_SPIKE_THRESHOLD:
            confidence += 30
            explanation.append(f"🔥 Volume {volume_ratio:.1f}x acima da média (confirmado!)")
        else:
            confidence -= 20
            explanation.append(f"⚠️ Volume baixo ({volume_ratio:.1f}x) - breakout fraco")
    
    return {
        'pattern': pattern,
        'signal': signal,
        'confidence': min(100, max(0, confidence)),
        'explanation': explanation
    }


# ============================================================================
# FUNÇÃO PRINCIPAL DE SCAN
# ============================================================================

def scan_stocks(
    symbols: Optional[List[str]] = None,
    interval: str = DEFAULT_INTERVAL,
    period: str = DEFAULT_PERIOD
) -> List[Dict]:
    """
    Escaneia ações buscando padrões de DIP e BREAKOUT.
    
    LÓGICA DE ALERTA:
    - DIP: Preço caiu > 2% em 1 hora (oportunidade de compra)
    - BREAKOUT: Preço subiu > 3% com volume alto (rompimento)
    
    Args:
        symbols: Lista de símbolos (ex: ['PETR4.SA', 'AAPL'])
        interval: Intervalo dos candles (15m, 1h, 1d)
        period: Período de dados (1d, 5d, 1mo)
    
    Returns:
        Lista de oportunidades detectadas
    """
    if symbols is None:
        symbols = WATCHLIST_BRASIL + WATCHLIST_EUA
    
    opportunities = []
    
    print(f"📊 [Stock Scanner] Analisando {len(symbols)} ativos...")
    
    for symbol in symbols:
        try:
            # Baixa dados do yfinance
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty or len(df) < 4:
                continue
            
            # Calcula métricas
            current_price = df['Close'].iloc[-1]
            change_1h = _calculate_change_1h(df)
            volume_ratio = _calculate_volume_ratio(df)
            
            # Detecta padrão
            detection = _detect_pattern(change_1h, volume_ratio)
            
            if detection['pattern']:
                # Busca info adicional
                info = ticker.info
                name = info.get('shortName', symbol)
                market_cap = info.get('marketCap', 0)
                
                opportunities.append({
                    'type': 'AÇÃO',  # Identificador para diferenciar de cripto
                    'symbol': symbol,
                    'name': name,
                    'price': current_price,
                    'change_1h': change_1h,
                    'volume_ratio': volume_ratio,
                    'pattern': detection['pattern'],
                    'signal': detection['signal'],
                    'confidence': detection['confidence'],
                    'explanation': detection['explanation'],
                    'market_cap': market_cap,
                    'url': f"https://finance.yahoo.com/quote/{symbol}",
                    'timestamp': datetime.now().isoformat()
                })
                
                # Log
                emoji = "📉" if detection['pattern'] == "DIP" else "📈"
                print(f"   {emoji} {symbol}: {detection['pattern']} | {change_1h:+.2f}% | Conf: {detection['confidence']}%")
            
            time.sleep(0.3)  # Rate limiting
            
        except Exception as e:
            print(f"   ❌ Erro em {symbol}: {e}")
            continue
    
    # Ordena por confiança
    opportunities.sort(key=lambda x: x.get('confidence', 0), reverse=True)
    
    print(f"\n✅ {len(opportunities)} oportunidades encontradas")
    
    return opportunities


def scan_brasil() -> List[Dict]:
    """Scan focado em ações brasileiras (B3)."""
    return scan_stocks(WATCHLIST_BRASIL)


def scan_eua() -> List[Dict]:
    """Scan focado em ações americanas."""
    return scan_stocks(WATCHLIST_EUA)


# ============================================================================
# TESTE STANDALONE
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("📊 STOCK SCANNER - Detecção de DIP e BREAKOUT")
    print("=" * 60)
    print()
    print("🎯 PADRÕES MONITORADOS:")
    print(f"   📉 DIP: Queda > {abs(DIP_THRESHOLD_PCT)}% em 1h")
    print(f"   📈 BREAKOUT: Alta > {BREAKOUT_THRESHOLD_PCT}% + Volume 2x")
    print()
    
    # Testa com alguns ativos
    test_symbols = ['PETR4.SA', 'VALE3.SA', 'AAPL', 'NVDA']
    results = scan_stocks(test_symbols)
    
    if results:
        print("\n🎯 OPORTUNIDADES:")
        for r in results:
            print(f"\n   {r['signal']} {r['symbol']} ({r['pattern']})")
            print(f"   💲 Preço: ${r['price']:.2f}")
            print(f"   📊 Variação 1h: {r['change_1h']:+.2f}%")
            print(f"   🎯 Confiança: {r['confidence']}%")
            for exp in r['explanation']:
                print(f"      • {exp}")
    else:
        print("\n❄️ Nenhuma oportunidade detectada no momento")
