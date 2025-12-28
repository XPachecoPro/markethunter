###############################################################################
# FILE: stock_scanner.py - Scanner de Ações usando yfinance
###############################################################################
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# Lista padrão de ações populares para monitorar
DEFAULT_WATCHLIST = [
    "AAPL", "GOOGL", "MSFT", "TSLA", "AMZN", "META", "NVDA", "AMD",
    "NFLX", "DIS", "BA", "JPM", "GS", "V", "MA", "PYPL",
    "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA"  # Ações brasileiras
]

def scan_stocks(watchlist=None, volume_threshold=2.0, price_change_max=5.0):
    """
    Varre ações buscando padrões de acumulação (volume alto + preço estável).
    
    Args:
        watchlist: Lista de tickers para monitorar (usa DEFAULT_WATCHLIST se None)
        volume_threshold: Múltiplo do volume médio para gatilho (ex: 2.0 = 200% da média)
        price_change_max: Variação máxima de preço permitida (%)
    
    Returns:
        Lista de oportunidades detectadas
    """
    if watchlist is None:
        watchlist = DEFAULT_WATCHLIST
    
    opportunities = []
    
    for symbol in watchlist:
        try:
            ticker = yf.Ticker(symbol)
            
            # Busca histórico de 30 dias para calcular média de volume
            hist = ticker.history(period="1mo", interval="1d")
            
            if hist.empty or len(hist) < 5:
                continue
            
            # Cálculos
            avg_volume = hist['Volume'].rolling(window=20).mean().iloc[-1]
            current_volume = hist['Volume'].iloc[-1]
            price_change = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            current_price = hist['Close'].iloc[-1]
            
            # Verifica padrão de acumulação
            vol_ratio = current_volume / avg_volume if avg_volume > 0 else 0
            
            if vol_ratio > volume_threshold and abs(price_change) < price_change_max:
                # Busca informações adicionais
                info = ticker.info
                company_name = info.get('shortName', symbol)
                market_cap = info.get('marketCap', 0)
                
                opportunities.append({
                    "symbol": symbol,
                    "name": company_name,
                    "price": current_price,
                    "volume": current_volume,
                    "avg_volume": avg_volume,
                    "vol_ratio": vol_ratio,
                    "price_change": price_change,
                    "market_cap": market_cap,
                    "platform": "Stocks",
                    "url": f"https://finance.yahoo.com/quote/{symbol}",
                    "reason": f"Volume {vol_ratio:.1f}x acima da média, preço variou apenas {price_change:.2f}%"
                })
                
        except Exception as e:
            # Silencioso para não poluir o log
            continue
    
    return opportunities


def scan_stocks_intraday(watchlist=None, volume_threshold=3.0):
    """
    Scanner intradiário para detectar movimentos anômalos durante o pregão.
    Usa dados de 1 hora.
    """
    if watchlist is None:
        watchlist = DEFAULT_WATCHLIST[:10]  # Limita para não sobrecarregar
    
    opportunities = []
    
    for symbol in watchlist:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d", interval="1h")
            
            if hist.empty or len(hist) < 24:
                continue
            
            # Última hora vs média das últimas 24 horas
            avg_volume_24h = hist['Volume'].tail(24).mean()
            last_volume = hist['Volume'].iloc[-1]
            last_price_change = ((hist['Close'].iloc[-1] - hist['Open'].iloc[-1]) / hist['Open'].iloc[-1]) * 100
            
            vol_ratio = last_volume / avg_volume_24h if avg_volume_24h > 0 else 0
            
            if vol_ratio > volume_threshold and abs(last_price_change) < 2.0:
                opportunities.append({
                    "symbol": symbol,
                    "price": hist['Close'].iloc[-1],
                    "volume": last_volume,
                    "vol_ratio": vol_ratio,
                    "price_change": last_price_change,
                    "platform": "Stocks (Intraday)",
                    "url": f"https://finance.yahoo.com/quote/{symbol}",
                    "reason": f"Volume horário {vol_ratio:.1f}x acima da média, preço estável ({last_price_change:.2f}%)"
                })
                
        except Exception as e:
            continue
    
    return opportunities


if __name__ == "__main__":
    print("🔎 Iniciando Scanner de Ações...")
    results = scan_stocks()
    
    if results:
        print(f"🎯 {len(results)} OPORTUNIDADES ENCONTRADAS:")
        for r in results:
            print(f"  - {r['symbol']}: {r['reason']}")
    else:
        print("Nenhuma oportunidade detectada com os critérios atuais.")
