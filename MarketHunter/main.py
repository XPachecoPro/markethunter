###############################################################################
# FILE: main.py (Versão Multi-Plataforma: DexScreener + Binance + Ações)
###############################################################################
import time
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Importa todos os scanners disponíveis
from dex_scanner import scan_dexscreener
from binance_scanner import scan_binance, scan_binance_gainers
from stock_scanner import scan_stocks

# --- CONFIGURAÇÕES ---
TELEGRAM_BOT_TOKEN = "8308955598:AAE6bTRBPZKIt8N8KOgHWXR6TNwO7ShePIU" 
TELEGRAM_CHAT_ID = "1183036218"
SHEET_NAME = "MarketHunter_DB"

# Plataformas disponíveis
PLATFORMS = {
    "dexscreener": {"name": "DexScreener (Solana)", "scanner": lambda: scan_dexscreener("solana")},
    "binance": {"name": "Binance Spot", "scanner": scan_binance},
    "binance_gainers": {"name": "Binance Gainers", "scanner": scan_binance_gainers},
    "stocks": {"name": "Ações (Yahoo Finance)", "scanner": scan_stocks},
}

# Plataformas ativas (o usuário pode configurar)
ACTIVE_PLATFORMS = ["dexscreener", "binance", "stocks"]

# --- CONEXÃO PLANILHA ---
def conectar_planilha():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

def registrar_na_planilha(dados, plataforma=""):
    """Escreve uma nova linha no Google Sheets"""
    try:
        sheet = conectar_planilha()
        linha = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            plataforma,
            dados.get('symbol', '-'),
            dados.get('price', 0),
            dados.get('volume', dados.get('vol_ratio', 0)),
            dados.get('reason', '-'),
            dados.get('url', '-')
        ]
        sheet.append_row(linha)
        print(f"📝 [{plataforma}] Registrado: {dados.get('symbol')}")
    except Exception as e:
        print(f"❌ Erro ao salvar na planilha: {e}")

# --- TELEGRAM ---
def enviar_telegram(mensagem):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID, 
            "text": mensagem, 
            "parse_mode": "Markdown", 
            "disable_web_page_preview": True
        }
        requests.post(url, json=payload, timeout=5)
    except Exception:
        pass

# --- LOOP PRINCIPAL ---
def run_scanner():
    print("🚀 MarketHunter Multi-Plataforma Ativado!")
    print(f"📊 Plataformas ativas: {', '.join([PLATFORMS[p]['name'] for p in ACTIVE_PLATFORMS])}")
    print("-" * 60)
    
    # Mensagem de boas-vindas no Telegram
    enviar_telegram(f"🦅 *MarketHunter Iniciado!*\nMonitorando: {', '.join([PLATFORMS[p]['name'] for p in ACTIVE_PLATFORMS])}")
    
    while True:
        for platform_key in ACTIVE_PLATFORMS:
            platform = PLATFORMS.get(platform_key)
            if not platform:
                continue
            
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔎 Varrendo {platform['name']}...")
            
            try:
                opportunities = platform['scanner']()
                
                if opportunities:
                    print(f"   🎯 {len(opportunities)} oportunidades encontradas!")
                    
                    for opp in opportunities[:5]:  # Limita a 5 por plataforma para não floodar
                        # Monta mensagem para Telegram
                        msg = (
                            f"🎯 *{platform['name']}*\n"
                            f"💎 `{opp.get('symbol', 'N/A')}`\n"
                            f"📈 {opp.get('reason', 'Oportunidade detectada')}\n"
                            f"🔗 [Ver mais]({opp.get('url', '#')})"
                        )
                        enviar_telegram(msg)
                        
                        # Salva na planilha
                        registrar_na_planilha(opp, platform['name'])
                        
                        time.sleep(1)  # Pequena pausa entre mensagens
                else:
                    print(f"   ✓ Nenhuma oportunidade detectada.")
                    
            except Exception as e:
                print(f"   ❌ Erro em {platform['name']}: {e}")
        
        print(f"\n{'='*60}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 💤 Aguardando 5 minutos para próximo ciclo...")
        time.sleep(300)

if __name__ == "__main__":
    try:
        run_scanner()
    except KeyboardInterrupt:
        print("\n👋 Bot parado pelo usuário.")
    except Exception as e:
        print(f"❌ Erro crítico: {e}")
