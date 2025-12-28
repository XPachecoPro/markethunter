from sniper_logic import check_accumulation_pattern
from dex_logic import check_new_liquidity_pools
from dex_scanner import scan_dexscreener
from wallet_logic import SmartMoneyWatcher
import time

# Lista de moedas para monitorar (CEX - Regra A)
WATCHLIST_CEX = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT', 
    'XRP/USDT', 'DOT/USDT', 'DOGE/USDT', 'AVAX/USDT', 'LINK/USDT'
]

# Lista de carteiras para monitorar (Regra C)
WATCHLIST_WALLETS = [
    "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B", # Exemplo: Vitalik
]

def run_scanner():
    print("🚀 SniperBot Early Detection System Ativado!")
    print("-" * 60)
    
    # Inicializa o watcher de carteiras
    wallet_watcher = SmartMoneyWatcher(watch_list=WATCHLIST_WALLETS)
    # Primeiro run para mapear o estado atual (sem alertar tudo de uma vez)
    wallet_watcher.check_smart_money_movements()
    
    while True:
        # --- REGRA A: ACUMULAÇÃO CEX ---
        print("\n[VARRAGEM] Verificando Regra A (CEX)...")
        for symbol in WATCHLIST_CEX:
            result = check_accumulation_pattern(symbol)
            if result and result['is_accumulating']:
                print(f"⚠️ ALERTA DE ACUMULAÇÃO (Regra A): {result['symbol']} | "
                      f"Volume 1h: {result['vol_increase_ratio']:.2f}x | "
                      f"Volatilidade: {result['volatilidade_pct']:.2f}% | "
                      f"Potencial de Explosão Iminente")

        # --- REGRA B: NOVAS POOLS DEX (GeckoTerminal) ---
        print("[VARRAGEM] Verificando Regra B (DEX - New Pools)...")
        dex_pools = check_new_liquidity_pools(liquidity_min=50000)
        for pool in dex_pools:
            print(f"🔥 LANÇAMENTO POTENCIAL (Regra B): {pool['name']} | "
                  f"Liquidez: ${pool['liquidity']:,.2f} | "
                  f"Rede: {pool['network']} | "
                  f"Criada há {pool['age_minutes']:.1f} min")

        # --- SNIPER MODE: DEXSCREENER SEARCH ---
        print("[VARRAGEM] Verificando Sniper Mode (DexScreener)...")
        dex_opportunities = scan_dexscreener("solana") # Busca por moedas no ecossistema Solana
        for opp in dex_opportunities:
            print(f"🎯 OPORTUNIDADE SNIPER: {opp['symbol']} | "
                  f"DEX: {opp['dex']} | "
                  f"Motivo: {opp['reason']}")

        # --- REGRA C: SMART MONEY ---
        print("[VARRAGEM] Verificando Regra C (Wallets)...")
        wallet_alerts = wallet_watcher.check_smart_money_movements()
        for alert in wallet_alerts:
            print(f"🚨 ALERTA MÁXIMO (Regra C): Carteira {alert['wallet'][:10]}... "
                  f"comprou novo token {alert['token']}! "
                  f"Contrato: {alert['contract']}")
            
        print("\n" + "="*60)
        print(f"[INFO] Scan completo em {time.strftime('%H:%M:%S')}. Próximo scan em 5 minutos...")
        time.sleep(300)

if __name__ == "__main__":
    try:
        run_scanner()
    except KeyboardInterrupt:
        print("\nBot parado pelo usuário.")
    except Exception as e:
        print(f"Erro crítico no loop principal: {e}")
