import requests
from datetime import datetime, timezone, timedelta

def check_new_liquidity_pools(liquidity_min=50000):
    """
    Regra B: Detecção de Liquidez (Liquidity Snipe)
    Filtro: Pool criada há menos de 1h, Liquidez > $50.000.
    """
    url = "https://api.geckoterminal.com/api/v2/networks/new_pools"
    headers = {'Accept': 'application/json;version=20230203'}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Erro ao acessar GeckoTerminal: {response.status_code}")
            return []
            
        data = response.json()
        new_valid_pools = []
        
        now = datetime.now(timezone.utc)
        
        for pool in data.get('data', []):
            attr = pool.get('attributes', {})
            created_at_str = attr.get('pool_created_at')
            liquidity = float(attr.get('reserve_in_usd') or 0)
            name = attr.get('name')
            
            if not created_at_str:
                continue
                
            # Exemplo de string: "2023-05-24T14:15:22.000Z"
            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            
            age = now - created_at
            
            # Filtro: Menos de 1 hora e Liquidez > 50k
            if age < timedelta(hours=1) and liquidity > liquidity_min:
                new_valid_pools.append({
                    'name': name,
                    'liquidity': liquidity,
                    'age_minutes': age.total_seconds() / 60,
                    'address': pool.get('id'),
                    'network': pool.get('relationships', {}).get('network', {}).get('data', {}).get('id')
                })
                
        return new_valid_pools
    except Exception as e:
        print(f"Erro na Regra B: {e}")
        return []

if __name__ == "__main__":
    pools = check_new_liquidity_pools()
    if pools:
        for p in pools:
            print(f"✅ Lançamento Potencial Detectado: {p['name']} | Liquidez: ${p['liquidity']:,.2f} | Rede: {p['network']} | Criada há {p['age_minutes']:.1f} min")
    else:
        print("Nenhuma pool nova com alta liquidez encontrada nos últimos 60 min.")
