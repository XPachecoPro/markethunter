###############################################################################
# FILE: binance_scanner.py - Scanner de Cripto na Binance via CCXT
###############################################################################
import ccxt
import pandas as pd
from datetime import datetime

# Lista padrão de pares para monitorar na Binance
DEFAULT_PAIRS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
    'ADA/USDT', 'AVAX/USDT', 'DOGE/USDT', 'DOT/USDT', 'MATIC/USDT',
    'LINK/USDT', 'ATOM/USDT', 'UNI/USDT', 'LTC/USDT', 'NEAR/USDT',
    'APT/USDT', 'ARB/USDT', 'OP/USDT', 'INJ/USDT', 'SUI/USDT',
    'PEPE/USDT', 'WIF/USDT', 'BONK/USDT', 'SHIB/USDT', 'FLOKI/USDT'
]

def get_binance_exchange():
    """Retorna instância da exchange Binance (apenas dados públicos)."""
    return ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })

def scan_binance(pairs=None, timeframe='1h', volume_threshold=3.0, price_threshold=3.0, periodo_media=20):
    """
    Varre pares na Binance buscando padrões de acumulação.
    
    Args:
        pairs: Lista de pares para monitorar (usa DEFAULT_PAIRS se None)
        timeframe: Período das velas ('1h', '4h', '1d')
        volume_threshold: Múltiplo do volume médio para gatilho
        price_threshold: Volatilidade máxima permitida (%)
        periodo_media: Período para cálculo da média de volume
    
    Returns:
        Lista de oportunidades detectadas
    """
    if pairs is None:
        pairs = DEFAULT_PAIRS
    
    exchange = get_binance_exchange()
    opportunities = []
    
    for symbol in pairs:
        try:
            # Busca velas OHLCV
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=periodo_media + 5)
            
            if not ohlcv or len(ohlcv) < periodo_media:
                continue
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Cálculos
            df['vol_sma'] = df['volume'].rolling(window=periodo_media).mean()
            df['volatilidade'] = ((df['high'] - df['low']) / df['open']) * 100
            
            # Última vela fechada (penúltima, pois a última está em formação)
            ultima_vela = df.iloc[-2]
            current_price = df.iloc[-1]['close']
            
            vol_ratio = ultima_vela['volume'] / ultima_vela['vol_sma'] if ultima_vela['vol_sma'] > 0 else 0
            volatilidade = ultima_vela['volatilidade']
            
            # Verifica padrão de acumulação
            if vol_ratio > volume_threshold and volatilidade < price_threshold:
                # Busca ticker para preço atual
                ticker = exchange.fetch_ticker(symbol)
                price_change_24h = ticker.get('percentage', 0)
                
                opportunities.append({
                    "symbol": symbol,
                    "price": current_price,
                    "volume": ultima_vela['volume'],
                    "avg_volume": ultima_vela['vol_sma'],
                    "vol_ratio": vol_ratio,
                    "volatilidade": volatilidade,
                    "price_change_24h": price_change_24h,
                    "platform": "Binance",
                    "dex": "Binance Spot",
                    "url": f"https://www.binance.com/pt-BR/trade/{symbol.replace('/', '_')}",
                    "reason": f"Volume {vol_ratio:.1f}x acima da média, volatilidade de apenas {volatilidade:.2f}%"
                })
                
        except Exception as e:
            # Silencioso para não poluir o log
            continue
    
    return opportunities


def scan_binance_gainers(min_change=5.0, max_change=20.0, min_volume=1000000):
    """
    Scanner de moedas em alta na Binance (potenciais breakouts).
    
    Args:
        min_change: Variação mínima de preço em 24h (%)
        max_change: Variação máxima (para evitar pumps extremos)
        min_volume: Volume mínimo em USDT
    """
    exchange = get_binance_exchange()
    opportunities = []
    
    try:
        tickers = exchange.fetch_tickers()
        
        for symbol, ticker in tickers.items():
            # Filtra apenas pares USDT
            if not symbol.endswith('/USDT'):
                continue
            
            change = ticker.get('percentage', 0) or 0
            volume = ticker.get('quoteVolume', 0) or 0
            
            if min_change < change < max_change and volume > min_volume:
                opportunities.append({
                    "symbol": symbol,
                    "price": ticker.get('last', 0),
                    "price_change_24h": change,
                    "volume_24h": volume,
                    "platform": "Binance",
                    "url": f"https://www.binance.com/pt-BR/trade/{symbol.replace('/', '_')}",
                    "reason": f"Alta de {change:.1f}% com volume de ${volume:,.0f}"
                })
                
    except Exception as e:
        print(f"Erro ao buscar gainers: {e}")
    
    # Ordena por variação de preço (maior primeiro)
    opportunities.sort(key=lambda x: x['price_change_24h'], reverse=True)
    
    return opportunities[:20]  # Retorna top 20


if __name__ == "__main__":
    print("🔎 Iniciando Scanner Binance...")
    
    print("\n📊 Buscando padrões de acumulação...")
    results = scan_binance()
    
    if results:
        print(f"🎯 {len(results)} OPORTUNIDADES (Acumulação):")
        for r in results:
            print(f"  - {r['symbol']}: {r['reason']}")
    else:
        print("Nenhuma acumulação detectada.")
    
    print("\n🚀 Buscando gainers...")
    gainers = scan_binance_gainers()
    
    if gainers:
        print(f"🔥 {len(gainers)} GAINERS DETECTADOS:")
        for g in gainers[:5]:
            print(f"  - {g['symbol']}: +{g['price_change_24h']:.1f}%")
