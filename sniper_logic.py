import ccxt
import pandas as pd
import time

def check_accumulation_pattern(symbol, timeframe='1h', volume_threshold=3.0, price_threshold=0.02, periodo_media=20):
    """
    Regra A Refinada: Detecção de Acumulação Furtiva.
    - Gatilho: Volume > 300% da média das últimas 20 velas.
    - Condição: Volatilidade (High-Low) < 2%.
    """
    try:
        # Usamos Binance como padrão, mas pode ser expandido
        exchange = ccxt.binance()
        
        # Buscamos 30 velas para garantir que temos o período de média (20) + margem
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=30)
        
        if not ohlcv or len(ohlcv) < periodo_media:
            return None
            
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # 1. Cálculos de Média e Volatilidade
        df['vol_sma'] = df['volume'].rolling(window=periodo_media).mean()
        df['volatilidade'] = (df['high'] - df['low']) / df['open']
        
        # 2. Análise da Última Vela Fechada (iloc[-2] pois -1 é a vela em formação)
        ultima_vela = df.iloc[-2]
        
        vol_increase_ratio = ultima_vela['volume'] / ultima_vela['vol_sma']
        volatilidade_pct = ultima_vela['volatilidade'] * 100
        
        is_accumulating = (vol_increase_ratio > volume_threshold) and (ultima_vela['volatilidade'] < price_threshold)
        
        return {
            'symbol': symbol,
            'vol_increase_ratio': vol_increase_ratio,
            'volatilidade_pct': volatilidade_pct,
            'is_accumulating': is_accumulating,
            'current_vol': ultima_vela['volume'],
            'avg_vol': ultima_vela['vol_sma']
        }
    except Exception as e:
        # print(f"Erro ao verificar {symbol}: {e}") # Silencioso no scanner principal
        return None

if __name__ == "__main__":
    # Teste rápido com BTC/USDT
    print("Testando lógica refinada com BTC/USDT...")
    result = check_accumulation_pattern('BTC/USDT')
    if result:
        print(f"Resultado: {result}")
        if result['is_accumulating']:
            print(f"🎯 OPORTUNIDADE ENCONTRADA! {result['symbol']}")
            print(f"Motivo: Volume {result['vol_increase_ratio']:.2f}x acima da média detectado enquanto volatilidade foi de apenas {result['volatilidade_pct']:.2f}%")
        else:
            print("Padrão de acumulação furtiva não detectado no momento.")
