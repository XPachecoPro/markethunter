import requests
import json
import time

# Redes suportadas para busca no DexScreener
SUPPORTED_CHAINS = {
    "solana": {"name": "Solana", "icon": "☀️", "query": "solana"},
    "ethereum": {"name": "Ethereum", "icon": "⟠", "query": "ethereum"},
    "bsc": {"name": "BNB Chain", "icon": "🟡", "query": "bsc"},
    "arbitrum": {"name": "Arbitrum", "icon": "🔵", "query": "arbitrum"},
    "base": {"name": "Base", "icon": "🔷", "query": "base"},
    "polygon": {"name": "Polygon", "icon": "🟣", "query": "polygon"},
    "avalanche": {"name": "Avalanche", "icon": "🔺", "query": "avalanche"},
}

def scan_dexscreener(chain="solana", min_liquidity=10000, max_fdv=5000000):
    """
    Varre pares recentes no DexScreener para uma rede específica.
    Aplica o filtro de 'Acumulação Silenciosa' para identificar gemas.
    
    Args:
        chain: Rede a ser escaneada (solana, ethereum, bsc, etc)
        min_liquidity: Liquidez mínima em USD
        max_fdv: FDV máximo em USD
    """
    chain_info = SUPPORTED_CHAINS.get(chain, SUPPORTED_CHAINS["solana"])
    query = chain_info["query"]
    url = f"https://api.dexscreener.com/latest/dex/search?q={query}"
    
    try:
        response = requests.get(url, timeout=15)
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
            
            # Liquidez > min E FDV < max
            if liquidity < min_liquidity or (fdv > max_fdv or fdv == 0):
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
                    "chain": chain,
                    "chain_icon": chain_info["icon"],
                    "symbol": pair.get('baseToken', {}).get('symbol'),
                    "name": pair.get('baseToken', {}).get('name'),
                    "pairAddress": pair.get('pairAddress'),
                    "dex": pair.get('dexId'),
                    "url": pair.get('url'),
                    "liquidity": liquidity,
                    "fdv": fdv,
                    "vol_anomaly": vol_anomaly_ratio,
                    "price_change_h1": price_change_h1,
                    "reason": f"Volume 1h (${vol_h1:,.0f}) é {vol_anomaly_ratio:.1f}x maior que a média, preço variou apenas {price_change_h1:.2f}%."
                })
                
        return opportunities
        
    except Exception as e:
        print(f"Erro no scanner DexScreener ({chain}): {e}")
        return []

def scan_all_chains(min_liquidity=10000, max_fdv=5000000):
    """
    Varre TODAS as redes suportadas e retorna gemas de todas elas.
    """
    all_gems = []
    for chain_id in SUPPORTED_CHAINS.keys():
        gems = scan_dexscreener(chain_id, min_liquidity, max_fdv)
        all_gems.extend(gems)
        time.sleep(0.5)  # Rate limiting
    return all_gems

if __name__ == "__main__":
    print("🔎 Iniciando Scanner Multi-Chain no DexScreener...")
    
    for chain_id, chain_info in SUPPORTED_CHAINS.items():
        print(f"\n{chain_info['icon']} Buscando em {chain_info['name']}...")
        results = scan_dexscreener(chain_id)
        
        if results:
            print(f"  🎯 {len(results)} oportunidades encontradas!")
            for r in results[:3]:
                print(f"    - {r['symbol']}: {r['reason'][:50]}...")
        else:
            print("  Nenhuma oportunidade detectada.")

