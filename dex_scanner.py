import requests
import json
import time

def scan_dexscreener(query="solana"):
    """
    Varre pares recentes no DexScreener e aplica o filtro de 'Acumulação Silenciosa'.
    """
    url = f"https://api.dexscreener.com/latest/dex/search?q={query}"
    
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Erro ao acessar DexScreener: {response.status_code}")
            return []
            
        data = response.json()
        pairs = data.get('pairs', [])
        opportunities = []
        
        for pair in pairs:
            # 1. Filtros Anti-Golpe (Rug Pull Check)
            liquidity = float(pair.get('liquidity', {}).get('usd', 0))
            fdv = float(pair.get('fdv', 0))
            
            # Liquidez > $10.000 E FDV < $5.000.000
            if liquidity < 10000 or (fdv > 5000000 or fdv == 0):
                continue
                
            # 2. Dados de Volume e Preço
            vol_h1 = float(pair.get('volume', {}).get('h1', 0))
            vol_h24 = float(pair.get('volume', {}).get('h24', 0))
            price_change_h1 = float(pair.get('priceChange', {}).get('h1', 0))
            
            # 3. Cálculo da Média Esperada (Volume h24 / 24)
            avg_vol_h1_expected = vol_h24 / 24 if vol_h24 > 0 else 0
            
            if avg_vol_h1_expected == 0:
                continue
                
            # 4. Identificação da Anomalia: Volume h1 > 3x Média
            vol_anomaly_ratio = vol_h1 / avg_vol_h1_expected
            
            # 5. Filtro de Preço (A Mola): abs(priceChange.h1) < 3%
            price_stability = abs(price_change_h1) < 3.0
            
            if vol_anomaly_ratio > 3.0 and price_stability:
                opportunities.append({
                    "symbol": pair.get('baseToken', {}).get('symbol'),
                    "pairAddress": pair.get('pairAddress'),
                    "dex": pair.get('dexId'),
                    "url": pair.get('url'),
                    "reason": f"Volume 1h (${vol_h1:,.0f}) é {vol_anomaly_ratio:.1f}x maior que a média, preço variou apenas {price_change_h1:.2f}%."
                })
                
        return opportunities
        
    except Exception as e:
        print(f"Erro no scanner DexScreener: {e}")
        return []

if __name__ == "__main__":
    # Teste de busca por moedas na rede Solana (comum para novos lançamentos)
    print("🔎 Iniciando Busca Sniper no DexScreener (Solana)...")
    results = scan_dexscreener("solana")
    
    if results:
        print(f"🎯 {len(results)} OPORTUNIDADES ENCONTRADAS:")
        print(json.dumps(results, indent=2))
    else:
        print("Nenhuma oportunidade detectada com os critérios atuais.")
