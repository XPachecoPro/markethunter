###############################################################################
# FILE: favorites_monitor.py - Monitoramento Contínuo de Favoritos
###############################################################################
import time
import json
import requests
import google.generativeai as genai
from datetime import datetime
import os

# Configurações
TELEGRAM_BOT_TOKEN = "8308955598:AAE6bTRBPZKIt8N8KOgHWXR6TNwO7ShePIU"
TELEGRAM_CHAT_ID = "1183036218"
GEMINI_API_KEY = "AIzaSyABrNzrlu_dye66T-TVefG0eHIfOWEsr_A"
FAVORITES_FILE = "favorites_data.json"
ALERTS_FILE = "alerts_data.json"
CHECK_INTERVAL = 30  # 30 segundos

def enviar_telegram(mensagem):
    """Envia mensagem para Telegram."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensagem,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Erro Telegram: {e}")
        return False

def carregar_favoritos():
    """Carrega favoritos do arquivo JSON."""
    try:
        if os.path.exists(FAVORITES_FILE):
            with open(FAVORITES_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return []

def salvar_alerta(alerta):
    """Salva alerta no arquivo para o frontend ler."""
    try:
        alertas = []
        if os.path.exists(ALERTS_FILE):
            with open(ALERTS_FILE, 'r') as f:
                alertas = json.load(f)
        
        alertas.insert(0, alerta)
        alertas = alertas[:20]  # Mantém últimos 20 alertas
        
        with open(ALERTS_FILE, 'w') as f:
            json.dump(alertas, f)
    except Exception as e:
        print(f"❌ Erro ao salvar alerta: {e}")

def atualizar_dados_ativo(favorito):
    """Busca dados atualizados do ativo."""
    plataforma = favorito.get('plataforma', '')
    dados = favorito.get('data', {})
    
    try:
        if "DexScreener" in plataforma:
            pair_address = dados.get('pairAddress', '')
            if pair_address:
                url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{pair_address}"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    result = response.json()
                    if result.get('pairs'):
                        return result['pairs'][0]
        
        elif "Binance" in plataforma:
            import ccxt
            exchange = ccxt.binance({'enableRateLimit': True})
            symbol = dados.get('symbol', '')
            if symbol:
                ticker = exchange.fetch_ticker(symbol)
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=25)
                if ohlcv:
                    import pandas as pd
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['vol_sma'] = df['volume'].rolling(window=20).mean()
                    ultima = df.iloc[-2]
                    vol_ratio = ultima['volume'] / ultima['vol_sma'] if ultima['vol_sma'] > 0 else 0
                    return {
                        'symbol': symbol,
                        'price': ticker.get('last', 0),
                        'vol_ratio': vol_ratio,
                        'change_24h': ticker.get('percentage', 0),
                        'volatilidade': ((ultima['high'] - ultima['low']) / ultima['open']) * 100
                    }
        
        elif "Stocks" in plataforma or "Ações" in plataforma:
            import yfinance as yf
            symbol = dados.get('symbol', '')
            if symbol:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="5d", interval="1h")
                if not hist.empty:
                    return {
                        'symbol': symbol,
                        'price': hist['Close'].iloc[-1],
                        'vol_ratio': hist['Volume'].iloc[-1] / hist['Volume'].mean(),
                        'price_change': ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                    }
    except Exception as e:
        print(f"  ⚠️ Erro ao atualizar {favorito.get('symbol', 'N/A')}: {e}")
    
    return None

def analisar_oportunidade(favorito, dados_atuais):
    """Usa IA para analisar se é momento de comprar/vender."""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        plataforma = favorito.get('plataforma', '')
        
        if "DexScreener" in plataforma:
            texto = f"""
            Token: {dados_atuais.get('baseToken', {}).get('symbol', 'N/A')}
            Preço: ${dados_atuais.get('priceUsd', 0)}
            Variação 1h: {dados_atuais.get('priceChange', {}).get('h1', 0)}%
            Variação 24h: {dados_atuais.get('priceChange', {}).get('h24', 0)}%
            Volume 1h: ${dados_atuais.get('volume', {}).get('h1', 0):,.0f}
            Liquidez: ${dados_atuais.get('liquidity', {}).get('usd', 0):,.0f}
            """
        else:
            texto = f"""
            Ativo: {dados_atuais.get('symbol', 'N/A')}
            Preço: ${dados_atuais.get('price', 0):,.4f}
            Volume: {dados_atuais.get('vol_ratio', 0):.1f}x média
            Variação: {dados_atuais.get('change_24h', dados_atuais.get('price_change', 0)):.2f}%
            """
        
        prompt = f"""
Analise rapidamente este ativo que o usuário está monitorando.
Responda APENAS com uma das opções abaixo + justificativa de 1 linha:

🟢 COMPRAR AGORA - [motivo]
🔴 VENDER AGORA - [motivo]  
🟡 MANTER/AGUARDAR - [motivo]

Dados:
{texto}
"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
    
    except Exception as e:
        return f"❌ Erro na análise: {e}"

def verificar_alerta_urgente(analise):
    """Verifica se a análise requer alerta urgente."""
    analise_upper = analise.upper()
    if "COMPRAR AGORA" in analise_upper or "🟢" in analise:
        return "COMPRAR", analise
    elif "VENDER AGORA" in analise_upper or "🔴" in analise:
        return "VENDER", analise
    return None, analise

def monitorar_favoritos():
    """Loop principal de monitoramento."""
    print("🔄 Iniciando Monitor de Favoritos...")
    print(f"📱 Telegram: {TELEGRAM_CHAT_ID}")
    print(f"⏱️ Intervalo: {CHECK_INTERVAL}s")
    print("-" * 50)
    
    # Notifica início
    enviar_telegram("🦅 *MarketHunter Monitor Ativado!*\n\nMonitorando seus favoritos 24/7.\nVocê receberá alertas de COMPRA/VENDA aqui.")
    
    while True:
        favoritos = carregar_favoritos()
        
        if not favoritos:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Nenhum favorito para monitorar.")
        else:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔍 Analisando {len(favoritos)} favoritos...")
            
            for fav in favoritos:
                symbol = fav.get('symbol', 'N/A')
                print(f"  📊 Verificando {symbol}...")
                
                # Atualiza dados
                dados_atuais = atualizar_dados_ativo(fav)
                
                if dados_atuais:
                    # Analisa com IA
                    analise = analisar_oportunidade(fav, dados_atuais)
                    acao, mensagem = verificar_alerta_urgente(analise)
                    
                    if acao:
                        print(f"  🚨 ALERTA: {acao} {symbol}!")
                        
                        # Monta mensagem de alerta
                        alerta_msg = (
                            f"🚨 *ALERTA DE {acao}!*\n\n"
                            f"📊 *{symbol}*\n"
                            f"{mensagem}\n\n"
                            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
                        )
                        
                        # Envia Telegram
                        enviar_telegram(alerta_msg)
                        
                        # Salva para o frontend
                        salvar_alerta({
                            'symbol': symbol,
                            'acao': acao,
                            'mensagem': mensagem,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'plataforma': fav.get('plataforma', '')
                        })
                    else:
                        print(f"    ✓ {symbol}: Manter posição")
                
                time.sleep(2)  # Pausa entre análises
        
        print(f"\n💤 Aguardando {CHECK_INTERVAL}s para próxima verificação...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        monitorar_favoritos()
    except KeyboardInterrupt:
        print("\n👋 Monitor encerrado pelo usuário.")
        enviar_telegram("🔴 *Monitor de Favoritos Desativado*")
    except Exception as e:
        print(f"❌ Erro crítico: {e}")
        enviar_telegram(f"❌ *Erro no Monitor:* {e}")
