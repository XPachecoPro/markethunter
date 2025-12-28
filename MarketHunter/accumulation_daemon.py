###############################################################################
# FILE: accumulation_daemon.py - Monitor 24/7 de Acumulação
# 
# OBJETIVO:
# ---------
# Daemon que roda continuamente monitorando oportunidades de acumulação
# e enviando alertas via Telegram quando detectar padrões promissores.
#
# USO:
# ----
# python accumulation_daemon.py
# 
# Ou com nohup para rodar em background:
# nohup python accumulation_daemon.py > sniper.log 2>&1 &
#
# CONFIGURAÇÃO:
# Configure as variáveis de ambiente ou secrets.toml:
# - TELEGRAM_BOT_TOKEN
# - TELEGRAM_CHAT_ID
###############################################################################

import os
import sys
import time
import requests
from datetime import datetime
from typing import List, Dict, Optional
import threading

# Importa lógica de detecção
try:
    from sniper_logic import (
        check_accumulation_pattern_cex,
        check_accumulation_pattern_dex,
        check_liquidity_snipe,
        check_smart_money,
        classify_alert,
        run_accumulation_scan
    )
except ImportError:
    print("❌ Erro: sniper_logic.py não encontrado!")
    sys.exit(1)

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

# Telegram
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Intervalos de scan (em segundos)
SCAN_INTERVAL_SECONDS = 60         # Scan a cada 1 minuto
NEW_POOLS_INTERVAL_SECONDS = 30    # Novos pools a cada 30s (mais crítico)
SMART_MONEY_INTERVAL_SECONDS = 120 # Smart money a cada 2 min

# Thresholds
MIN_CONFIDENCE_ALERT = 75          # Mínimo 75% para alertar
MIN_CONFIDENCE_TELEGRAM = 85       # Mínimo 85% para enviar Telegram

# Pares CEX para monitorar (Binance)
DEFAULT_CEX_PAIRS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 
    'XRP/USDT', 'ADA/USDT', 'AVAX/USDT', 'DOGE/USDT',
    'DOT/USDT', 'MATIC/USDT', 'PEPE/USDT', 'WIF/USDT',
    'BONK/USDT', 'SHIB/USDT', 'ARB/USDT', 'OP/USDT',
    'SUI/USDT', 'SEI/USDT', 'INJ/USDT', 'TIA/USDT'
]

# Chains para monitorar novos pools
CHAINS_TO_MONITOR = ['solana', 'ethereum', 'bsc', 'base', 'arbitrum']

# Smart Money Watch List (adicionar endereços reais)
SMART_MONEY_WALLETS = {
    'solana': [
        # Adicione endereços de baleias Solana aqui
    ],
    'ethereum': [
        # Adicione endereços de baleias ETH aqui
    ]
}

# Histórico para evitar alertas duplicados
alerted_tokens = set()


# ============================================================================
# TELEGRAM
# ============================================================================

def send_telegram_alert(message: str) -> bool:
    """
    Envia alerta via Telegram.
    
    Args:
        message: Mensagem formatada em Markdown
    
    Returns:
        True se enviou com sucesso
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ [Telegram] Bot não configurado, pulando envio")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            print("📱 [Telegram] Alerta enviado!")
            return True
        else:
            print(f"❌ [Telegram] Erro: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ [Telegram] Exceção: {e}")
        return False


def format_alert_message(alert: Dict) -> str:
    """
    Formata um alerta como mensagem Telegram.
    
    Args:
        alert: Dict de alerta de qualquer regra
    
    Returns:
        Mensagem formatada em Markdown
    """
    rule = alert.get('rule', '?')
    rule_name = alert.get('rule_name', 'Desconhecida')
    symbol = alert.get('symbol', 'N/A')
    confidence = alert.get('confidence', 0)
    
    classification, emoji, action = classify_alert(confidence)
    
    msg = f"""
{emoji} *{classification}: {symbol}*

📋 *Regra:* {rule} - {rule_name}
🎯 *Confiança:* {confidence}%
⚡ *Ação:* {action}

📊 *Sinais Detectados:*
"""
    
    for signal in alert.get('signals', []):
        msg += f"• {signal}\n"
    
    # Dados específicos por regra
    if rule == 'A':
        vol_ratio = alert.get('volume_ratio', 0)
        price_change = alert.get('price_change_h1', alert.get('price_change_pct', 0))
        msg += f"""
📈 Volume: {vol_ratio:.1f}x acima da média
💲 Preço: {price_change:+.2f}%
"""
    
    elif rule == 'B':
        liquidity = alert.get('liquidity_usd', 0)
        age_min = alert.get('age_minutes', 0)
        msg += f"""
💧 Liquidez: ${liquidity:,.0f}
⏰ Idade: {age_min:.0f} minutos
"""
    
    # Link
    url = alert.get('url', '')
    if url:
        msg += f"\n🔗 [Ver no DexScreener]({url})"
    
    msg += f"\n\n⏰ {datetime.now().strftime('%H:%M:%S')}"
    
    return msg


# ============================================================================
# MONITORAMENTO CONTÍNUO
# ============================================================================

def monitor_cex_accumulation():
    """
    Monitora CEX (Binance) para padrões de acumulação.
    """
    print(f"\n📊 [CEX Monitor] Analisando {len(DEFAULT_CEX_PAIRS)} pares...")
    
    for pair in DEFAULT_CEX_PAIRS:
        try:
            result = check_accumulation_pattern_cex(pair)
            
            if result and result.get('is_accumulating'):
                confidence = result.get('confidence', 0)
                symbol = result.get('symbol', pair)
                
                # Evita alertas duplicados
                alert_key = f"cex_{symbol}_{datetime.now().strftime('%Y%m%d%H')}"
                if alert_key in alerted_tokens:
                    continue
                
                print(f"   🎯 {symbol}: Confiança {confidence}%")
                
                for signal in result.get('signals', []):
                    print(f"      • {signal}")
                
                # Envia Telegram se alta confiança
                if confidence >= MIN_CONFIDENCE_TELEGRAM:
                    msg = format_alert_message(result)
                    send_telegram_alert(msg)
                    alerted_tokens.add(alert_key)
                
        except Exception as e:
            print(f"   ❌ Erro em {pair}: {e}")
        
        time.sleep(0.5)  # Rate limiting


def monitor_new_pools():
    """
    Monitora novos pools de liquidez.
    """
    print(f"\n💧 [Pool Monitor] Buscando novos pools...")
    
    for chain in CHAINS_TO_MONITOR:
        try:
            pools = check_liquidity_snipe(chain, min_liquidity=50000)
            
            for pool in pools:
                confidence = pool.get('confidence', 0)
                symbol = pool.get('symbol', 'N/A')
                address = pool.get('address', '')
                
                # Evita alertas duplicados
                alert_key = f"pool_{address}"
                if alert_key in alerted_tokens:
                    continue
                
                if confidence >= MIN_CONFIDENCE_ALERT:
                    print(f"   🆕 {symbol} ({chain}): ${pool.get('liquidity_usd', 0):,.0f} liq, {confidence}% conf")
                    
                    # Envia Telegram se alta confiança
                    if confidence >= MIN_CONFIDENCE_TELEGRAM:
                        msg = format_alert_message(pool)
                        send_telegram_alert(msg)
                        alerted_tokens.add(alert_key)
                
        except Exception as e:
            print(f"   ❌ Erro em {chain}: {e}")
        
        time.sleep(1)  # Rate limiting entre chains


def monitor_smart_money():
    """
    Monitora transações de Smart Money.
    """
    if not any(SMART_MONEY_WALLETS.values()):
        return  # Sem wallets configuradas
    
    print(f"\n🐋 [Smart Money] Monitorando carteiras...")
    
    for chain, wallets in SMART_MONEY_WALLETS.items():
        if not wallets:
            continue
            
        try:
            alerts = check_smart_money({chain: wallets}, chain)
            
            for alert in alerts:
                confidence = alert.get('confidence', 0)
                
                if confidence >= MIN_CONFIDENCE_ALERT:
                    print(f"   🐋 Smart Money Alert: {alert}")
                    
                    if confidence >= MIN_CONFIDENCE_TELEGRAM:
                        msg = format_alert_message(alert)
                        send_telegram_alert(msg)
                
        except Exception as e:
            print(f"   ❌ Erro em {chain}: {e}")


def run_daemon():
    """
    Loop principal do daemon de monitoramento.
    
    Roda indefinidamente, escaneando a cada intervalo configurado.
    """
    print("=" * 60)
    print("🎯 ACCUMULATION SNIPER DAEMON")
    print("=" * 60)
    print(f"⏰ Iniciado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Pares CEX: {len(DEFAULT_CEX_PAIRS)}")
    print(f"🌐 Chains: {', '.join(CHAINS_TO_MONITOR)}")
    print(f"🐋 Wallets: {sum(len(v) for v in SMART_MONEY_WALLETS.values())}")
    print(f"📱 Telegram: {'✅ Configurado' if TELEGRAM_BOT_TOKEN else '❌ Não configurado'}")
    print("=" * 60)
    
    # Envia mensagem de início
    if TELEGRAM_BOT_TOKEN:
        send_telegram_alert("🎯 *Sniper Daemon Iniciado!*\n\nMonitorando mercado 24/7...")
    
    iteration = 0
    last_pool_check = 0
    last_smart_money_check = 0
    
    try:
        while True:
            iteration += 1
            current_time = time.time()
            
            print(f"\n{'='*60}")
            print(f"🔄 Iteração #{iteration} - {datetime.now().strftime('%H:%M:%S')}")
            print(f"{'='*60}")
            
            # Monitor CEX (a cada intervalo padrão)
            monitor_cex_accumulation()
            
            # Monitor Pools (mais frequente)
            if current_time - last_pool_check >= NEW_POOLS_INTERVAL_SECONDS:
                monitor_new_pools()
                last_pool_check = current_time
            
            # Monitor Smart Money (menos frequente)
            if current_time - last_smart_money_check >= SMART_MONEY_INTERVAL_SECONDS:
                monitor_smart_money()
                last_smart_money_check = current_time
            
            # Limpa histórico antigo (manter só últimas 1000 entradas)
            if len(alerted_tokens) > 1000:
                oldest = list(alerted_tokens)[:500]
                for token in oldest:
                    alerted_tokens.discard(token)
            
            # Aguarda próximo ciclo
            print(f"\n⏳ Próximo scan em {SCAN_INTERVAL_SECONDS}s...")
            time.sleep(SCAN_INTERVAL_SECONDS)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Daemon interrompido pelo usuário")
        if TELEGRAM_BOT_TOKEN:
            send_telegram_alert("🛑 *Sniper Daemon Parado*")
    
    except Exception as e:
        print(f"\n\n❌ Erro fatal: {e}")
        if TELEGRAM_BOT_TOKEN:
            send_telegram_alert(f"❌ *Sniper Daemon Erro!*\n\n{str(e)[:200]}")
        raise


# ============================================================================
# MODO DE TESTE
# ============================================================================

def run_single_scan():
    """
    Executa um único scan para teste.
    """
    print("🧪 [TESTE] Executando scan único...")
    
    results = run_accumulation_scan(
        cex_pairs=DEFAULT_CEX_PAIRS[:5],  # Apenas 5 para teste
        chain="solana"
    )
    
    high_conf = results.get('high_confidence', [])
    
    if high_conf:
        print(f"\n🔥 {len(high_conf)} alertas de alta confiança!")
        for alert in high_conf:
            print(f"   • {alert.get('symbol')}: {alert.get('confidence')}%")
            msg = format_alert_message(alert)
            print(msg)
    else:
        print("\n❄️ Nenhum alerta de alta confiança no momento")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Accumulation Sniper Daemon')
    parser.add_argument('--test', action='store_true', help='Executa scan único de teste')
    parser.add_argument('--daemon', action='store_true', help='Inicia daemon 24/7')
    
    args = parser.parse_args()
    
    if args.test:
        run_single_scan()
    elif args.daemon:
        run_daemon()
    else:
        # Default: um scan de teste
        print("Uso: python accumulation_daemon.py [--test | --daemon]")
        print("\nExecutando scan de teste...")
        run_single_scan()
