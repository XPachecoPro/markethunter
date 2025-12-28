###############################################################################
# FILE: app.py - MarketHunter Dashboard v3.6 (Phone Formatting)
###############################################################################
import streamlit as st
import requests
import json
import os
import threading
import time
from datetime import datetime

# Imports com fallback para cloud
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import ccxt
except ImportError:
    ccxt = None

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    import phonenumbers
except ImportError:
    phonenumbers = None

try:
    from news_fetcher import fetch_all_news, get_trending_topics
except ImportError:
    def fetch_all_news(*args, **kwargs): return []
    def get_trending_topics(*args, **kwargs): return []

try:
    from auth import (
        cadastrar_usuario, autenticar_usuario, atualizar_usuario,
        buscar_favoritos_usuario, adicionar_favorito_db, remover_favorito_db,
        buscar_alertas_usuario, salvar_alerta_db
    )
except ImportError:
    def cadastrar_usuario(*args): return False, "Módulo auth não disponível"
    def autenticar_usuario(*args): return False, None, "Módulo auth não disponível"
    def atualizar_usuario(*args): return False
    def buscar_favoritos_usuario(*args): return []
    def adicionar_favorito_db(*args): return False
    def remover_favorito_db(*args): return False
    def buscar_alertas_usuario(*args): return []
    def salvar_alerta_db(*args): return False

# Mapeamento de código de país para bandeira emoji
COUNTRY_FLAGS = {
    "BR": "🇧🇷", "US": "🇺🇸", "PT": "🇵🇹", "ES": "🇪🇸", "FR": "🇫🇷",
    "DE": "🇩🇪", "IT": "🇮🇹", "GB": "🇬🇧", "JP": "🇯🇵", "CN": "🇨🇳",
    "AR": "🇦🇷", "MX": "🇲🇽", "CO": "🇨🇴", "CL": "🇨🇱", "PE": "🇵🇪",
    "UY": "🇺🇾", "PY": "🇵🇾", "BO": "🇧🇴", "EC": "🇪🇨", "VE": "🇻🇪",
    "CA": "🇨🇦", "AU": "🇦🇺", "IN": "🇮🇳", "RU": "🇷🇺", "KR": "🇰🇷",
}

def formatar_telefone(numero_raw, default_region="BR"):
    """Formata número de telefone e detecta país."""
    if not numero_raw:
        return "", "", "🌍"
    
    # Remove caracteres não numéricos exceto +
    numero_limpo = ''.join(c for c in numero_raw if c.isdigit() or c == '+')
    
    # Se não começar com +, assume Brasil
    if not numero_limpo.startswith('+'):
        numero_limpo = '+55' + numero_limpo
    
    try:
        parsed = phonenumbers.parse(numero_limpo, default_region)
        
        if not phonenumbers.is_valid_number(parsed):
            return numero_raw, "", "⚠️"
        
        # Formata no padrão internacional
        formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        
        # Detecta país
        country_code = phonenumbers.region_code_for_number(parsed)
        flag = COUNTRY_FLAGS.get(country_code, "🌍")
        
        return formatted, country_code, flag
    except:
        return numero_raw, "", "⚠️"

# CONFIGURAÇÃO DE PÁGINA
st.set_page_config(page_title="MarketHunter - Sniper AI", page_icon="🦅", layout="wide")

# ============================================================================
# SISTEMA DE LOGIN
# ============================================================================

# Inicializa estados de autenticação
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'auth_mode' not in st.session_state:
    st.session_state.auth_mode = "login"

def mostrar_tela_login():
    """Exibe tela de login/cadastro."""
    st.markdown("""
    <style>
    .auth-container { max-width: 400px; margin: 0 auto; padding: 40px; }
    .auth-title { text-align: center; font-size: 2.5em; margin-bottom: 10px; }
    .auth-subtitle { text-align: center; color: #888; margin-bottom: 30px; }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h1 class='auth-title'>🦅 MarketHunter</h1>", unsafe_allow_html=True)
        st.markdown("<p class='auth-subtitle'>Sistema de Análise de Mercado com IA</p>", unsafe_allow_html=True)
        
        # Tabs de Login/Cadastro
        tab_login, tab_registro = st.tabs(["🔐 Entrar", "📝 Criar Conta"])
        
        with tab_login:
            st.subheader("Entrar na sua conta")
            email_login = st.text_input("Email", key="login_email", placeholder="seu@email.com")
            senha_login = st.text_input("Senha", type="password", key="login_senha", placeholder="••••••••")
            
            if st.button("🚀 Entrar", type="primary", use_container_width=True):
                if email_login and senha_login:
                    sucesso, user, msg = autenticar_usuario(email_login, senha_login)
                    if sucesso:
                        st.session_state.logged_in = True
                        st.session_state.user = user
                        st.success(f"✅ Bem-vindo(a), {user['nome']}!")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
                else:
                    st.warning("Preencha todos os campos!")
        
        with tab_registro:
            st.subheader("Criar nova conta")
            nome_registro = st.text_input("Nome completo", key="registro_nome", placeholder="Seu nome")
            email_registro = st.text_input("Email", key="registro_email", placeholder="seu@email.com")
            
            # Campo de telefone com formatação automática
            col_phone, col_flag = st.columns([4, 1])
            with col_phone:
                telefone_raw = st.text_input("📱 Celular", key="registro_telefone", placeholder="11 99999-9999")
            
            # Formata e exibe bandeira
            telefone_formatado, pais_code, bandeira = formatar_telefone(telefone_raw)
            with col_flag:
                st.markdown(f"<div style='font-size: 2.5em; text-align: center; margin-top: 25px;'>{bandeira}</div>", unsafe_allow_html=True)
            
            if telefone_formatado and telefone_raw:
                st.success(f"✓ {telefone_formatado}")
            
            senha_registro = st.text_input("Senha", type="password", key="registro_senha", placeholder="Mínimo 6 caracteres")
            senha_confirma = st.text_input("Confirme a senha", type="password", key="registro_confirma", placeholder="••••••••")
            
            st.caption("📱 O DDI é adicionado automaticamente. Alertas serão enviados via Telegram.")
            
            if st.button("📝 Criar Conta", type="primary", use_container_width=True):
                if nome_registro and email_registro and senha_registro and telefone_raw:
                    if len(senha_registro) < 6:
                        st.error("Senha deve ter no mínimo 6 caracteres!")
                    elif senha_registro != senha_confirma:
                        st.error("As senhas não coincidem!")
                    elif "@" not in email_registro:
                        st.error("Email inválido!")
                    else:
                        # Salva o telefone já formatado
                        sucesso, msg = cadastrar_usuario(nome_registro, email_registro, senha_registro, telefone_formatado)
                        if sucesso:
                            st.success(f"✅ {msg} Faça login para continuar.")
                        else:
                            st.error(f"❌ {msg}")
                else:
                    st.warning("Preencha todos os campos!")
        
        st.markdown("---")
        st.caption("🔒 Seus dados são armazenados na nuvem de forma segura e privada.")

# Verifica se está logado
if not st.session_state.logged_in:
    mostrar_tela_login()
    st.stop()

# ============================================================================
# CONTEÚDO PRINCIPAL (APÓS LOGIN)
# ============================================================================

# Inicializa session state
if 'oportunidades' not in st.session_state:
    st.session_state.oportunidades = []
if 'analise_resultado' not in st.session_state:
    st.session_state.analise_resultado = {}
if 'news_cache' not in st.session_state:
    st.session_state.news_cache = {}
if 'favoritos' not in st.session_state:
    st.session_state.favoritos = []
if 'analise_detalhada' not in st.session_state:
    st.session_state.analise_detalhada = {}
if 'alertas_vistos' not in st.session_state:
    st.session_state.alertas_vistos = set()

# ============================================================================
# INTERFACE PRINCIPAL
# ============================================================================

# Carrega favoritos do usuário via Supabase
if not st.session_state.favoritos and st.session_state.user:
    try:
        db_favs = buscar_favoritos_usuario(st.session_state.user['id'])
        loaded_favs = []
        for f in db_favs:
            asset_data = f['asset_data']
            plat = f['plataforma']
            
            # Deriva o nome baseado na plataforma
            if "DexScreener" in plat:
                name = asset_data.get('baseToken', {}).get('name', asset_data.get('symbol', 'N/A'))
            else:
                name = asset_data.get('name', asset_data.get('symbol', 'N/A'))
                
            loaded_favs.append({
                'key': f['asset_key'],
                'data': asset_data,
                'plataforma': plat,
                'symbol': f['symbol'],
                'name': name,
                'added_at': f['created_at'].split('T')[0] if 'T' in f['created_at'] else f['created_at']
            })
        st.session_state.favoritos = loaded_favs
    except Exception as e:
        print(f"Erro ao carregar favoritos: {e}")

# === SIDEBAR - CONFIGURAÇÕES ===
st.sidebar.title("🦅 MarketHunter")
st.sidebar.markdown("---")

# Info do usuário logado
st.sidebar.success(f"👤 {st.session_state.user['nome']}")

# Menu do Perfil
with st.sidebar.expander("⚙️ Meu Perfil", expanded=False):
    user = st.session_state.user
    
    st.write(f"**Email:** {user.get('email', 'N/A')}")
    st.write(f"**Telefone:** {user.get('telefone', 'Não informado')}")
    st.write(f"**Cadastrado em:** {user.get('created_at', 'N/A')[:10] if user.get('created_at') else 'N/A'}")
    
    st.markdown("---")
    st.subheader("✏️ Editar Dados")
    
    novo_nome = st.text_input("Nome", value=user.get('nome', ''), key="edit_nome")
    novo_telefone = st.text_input("Telefone", value=user.get('telefone', ''), key="edit_telefone")
    
    if st.button("💾 Salvar Alterações", key="save_profile"):
        from auth import atualizar_usuario
        dados_atualizados = {
            "nome": novo_nome,
            "telefone": novo_telefone
        }
        if atualizar_usuario(user.get('email'), dados_atualizados):
            st.session_state.user['nome'] = novo_nome
            st.session_state.user['telefone'] = novo_telefone
            st.success("✅ Dados atualizados!")
            st.rerun()
        else:
            st.error("❌ Erro ao atualizar dados.")

if st.sidebar.button("🚪 Sair", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.user = None
    st.rerun()

st.sidebar.markdown("---")
# API Key (lendo de st.secrets para segurança)
try:
    api_key = st.secrets["gemini"]["api_key"]
except:
    api_key = ""
    st.sidebar.error("⚠️ Gemini API Key não encontrada nos Secrets!")

# Monitor Status
st.sidebar.markdown("---")
st.sidebar.subheader("📡 Monitor")
st.sidebar.metric("⭐ Favoritos", len(st.session_state.favoritos))

def carregar_alertas():
    """Busca alertas do usuário via Supabase."""
    if st.session_state.user:
        return buscar_alertas_usuario(st.session_state.user['id'])
    return []

# Verifica alertas do monitor
alertas = carregar_alertas()

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def enviar_sms(destinatario, mensagem):
    """
    Placeholder para envio de SMS. 
    Para ativar, integre com Twilio, Vonage ou similar.
    """
    # Exemplo Twilio (requer pip install twilio):
    # from twilio.rest import Client
    # client = Client(ACCOUNT_SID, AUTH_TOKEN)
    # client.messages.create(body=mensagem, from_='+1234567', to=destinatario)
    print(f"📱 [SMS Placeholder] Enviando para {destinatario}: {mensagem}")

def get_asset_key(op, plataforma):
    if "DexScreener" in plataforma:
        return f"dex_{op.get('pairAddress', op.get('baseToken', {}).get('symbol', 'unknown'))}"
    elif "Binance" in plataforma:
        return f"binance_{op.get('symbol', 'unknown')}"
    else:
        return f"stock_{op.get('symbol', 'unknown')}"

def is_favorito(op, plataforma):
    key = get_asset_key(op, plataforma)
    return any(f.get('key') == key for f in st.session_state.get('favoritos', []))

def adicionar_favorito(op, plataforma):
    key = get_asset_key(op, plataforma)
    if not is_favorito(op, plataforma):
        favorito = {
            'key': key,
            'data': op,
            'plataforma': plataforma,
            'symbol': op.get('baseToken', {}).get('symbol', op.get('symbol', 'N/A')),
            'name': op.get('baseToken', {}).get('name', op.get('name', op.get('symbol', 'N/A'))),
            'added_at': datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        if st.session_state.user:
            sucesso = adicionar_favorito_db(st.session_state.user['id'], favorito)
            if sucesso:
                st.session_state.favoritos.append(favorito)
                st.toast(f"⭐ {favorito['symbol']} adicionado aos favoritos!")
                return True
            else:
                st.error("❌ Erro ao salvar favorito. Verifique se a tabela 'favorites' existe no Supabase.")
                return False
    return False

def remover_favorito(key):
    if st.session_state.user:
        if remover_favorito_db(st.session_state.user['id'], key):
            st.session_state.favoritos = [f for f in st.session_state.favoritos if f.get('key') != key]
            if key in st.session_state.analise_detalhada:
                del st.session_state.analise_detalhada[key]

def gerar_analise_detalhada(dados, key, plataforma):
    if not api_key:
        return "⚠️ Informe a Gemini API Key."
    if not genai:
        return "⚠️ SDK da Google AI não carregado."
    try:
        client = genai.Client(api_key=api_key)
        
        if "DexScreener" in plataforma:
            texto = f"Token: {dados.get('baseToken',{}).get('symbol','N/A')}\nLiquidez: ${dados.get('liquidity',{}).get('usd',0):,.0f}\nVolume 24h: ${dados.get('volume',{}).get('h24',0):,.0f}"
        elif "Binance" in plataforma:
            texto = f"Par: {dados.get('symbol','N/A')}\nPreço: ${dados.get('price',0):,.4f}\nVolume: {dados.get('vol_ratio',0):.1f}x"
        else:
            texto = f"Ação: {dados.get('symbol','N/A')}\nPreço: ${dados.get('price',0):,.2f}\nVolume: {dados.get('vol_ratio',0):.1f}x"
        
        prompt = f"""
Analise este ativo e dê recomendação DETALHADA de COMPRA ou VENDA.

{texto}

Formato:
## 🎯 RECOMENDAÇÃO: [COMPRAR/VENDER/AGUARDAR]
## 📊 Análise: [2-3 pontos]
## ⚠️ Riscos: [2-3 pontos]
## 💡 Estratégia: Entry, Stop Loss, Take Profit

Máximo 150 palavras.
"""
        response = client.models.generate_content(
            model='gemini-3-flash-preview',
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"❌ Erro: {str(e)}"

# ============================================================================
# MONITOR DE BACKGROUND (THREAD)
# ============================================================================

def monitor_thread_task(user_id):
    """Tarefa executada em background para monitorar favoritos de um usuário."""
    from auth import buscar_favoritos_usuario, salvar_alerta_db
    
    # Configura variáveis de ambiente ANTES de importar o monitor
    try:
        monitor_tg_token = st.secrets.get("telegram", {}).get("bot_token", "")
        monitor_tg_id = st.secrets.get("telegram", {}).get("chat_id", "")
        monitor_api_key = st.secrets.get("gemini", {}).get("api_key", "")
    except:
        monitor_tg_token = ""
        monitor_tg_id = ""
        monitor_api_key = ""
    
    os.environ["TELEGRAM_BOT_TOKEN"] = monitor_tg_token
    os.environ["TELEGRAM_CHAT_ID"] = monitor_tg_id
    os.environ["GEMINI_API_KEY"] = monitor_api_key
    
    # Agora importa o módulo que usa as variáveis de ambiente
    from favorites_monitor import atualizar_dados_ativo, analisar_oportunidade, verificar_alerta_urgente, enviar_telegram
    
    print(f"🚀 [Monitor] Iniciado para user_id={user_id}")
    print(f"📱 [Monitor] Telegram configurado: {bool(monitor_tg_token)}")
    
    while True:
        try:
            # Busca favoritos do banco relacional
            favoritos = buscar_favoritos_usuario(user_id)
            
            if favoritos:
                print(f"🔍 [Monitor] Analisando {len(favoritos)} favoritos...")
                for f in favoritos:
                    # Converte formato do DB para o formato do monitor
                    fav = {
                        'key': f['asset_key'],
                        'plataforma': f['plataforma'],
                        'data': f['asset_data'],
                        'symbol': f['symbol']
                    }
                    
                    dados_atuais = atualizar_dados_ativo(fav)
                    if dados_atuais:
                        analise = analisar_oportunidade(fav, dados_atuais)
                        acao, mensagem = verificar_alerta_urgente(analise)
                        
                        if acao:
                            # Notifica Telegram
                            msg_tg = f"🚨 *ALERTA DE {acao}!*\n\n📊 *{fav.get('symbol')}*\n{mensagem}"
                            sucesso_tg = enviar_telegram(msg_tg)
                            print(f"📱 [Monitor] Telegram enviado: {sucesso_tg}")
                            
                            # Salva alerta no banco relacional
                            salvar_alerta_db(user_id, {
                                'symbol': fav.get('symbol'),
                                'acao': acao,
                                'mensagem': mensagem
                            })
                    time.sleep(2)
            time.sleep(60)
        except Exception as e:
            print(f"❌ [Monitor] Erro: {e}")
            time.sleep(10)

if 'monitor_running' not in st.session_state:
    st.session_state.monitor_running = False

if not st.session_state.monitor_running and st.session_state.user:
    thread = threading.Thread(target=monitor_thread_task, args=(st.session_state.user['id'],), daemon=True)
    thread.start()
    st.session_state.monitor_running = True
    st.sidebar.info("📡 Scanner Background Ativado")

# ============================================================================
# POPUP DE ALERTAS (AUTO-REFRESH)
# ============================================================================

@st.fragment(run_every="30s")
def mostrar_alertas_dinamicos():
    alertas = carregar_alertas()
    alertas_novos = [a for a in alertas if a.get('timestamp') not in st.session_state.alertas_vistos]
    
    if alertas_novos:
        for alerta in alertas_novos[:2]:
            acao = alerta.get('acao', '')
            symbol = alerta.get('symbol', 'N/A')
            msg = alerta.get('mensagem', '')
            
            if acao == "COMPRAR":
                st.success(f"🚀 **COMPRA: {symbol}**\n\n{msg}")
            else:
                st.error(f"📉 **VENDA: {symbol}**\n\n{msg}")
            
            # Tenta SMS se o usuário tiver telefone (Placeholder)
            if st.session_state.user.get('telefone'):
                enviar_sms(st.session_state.user.get('telefone'), f"Eagle Alert {acao}: {symbol}")
            
            st.session_state.alertas_vistos.add(alerta.get('timestamp'))

mostrar_alertas_dinamicos()

# === TABS PRINCIPAIS ===
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🎯 Scanner", "⭐ Favoritos", "📈 Ambiente", "🧮 Simulador", "🚨 Alertas", "📰 Notícias"])

# Scanner functions
def buscar_dados_dexscreener(termo_busca, liq_min, f_max):
    url = f"https://api.dexscreener.com/latest/dex/search?q={termo_busca}"
    try:
        response = requests.get(url)
        pairs = response.json().get('pairs', [])
        candidatos = []
        for pair in pairs[:50]:
            try:
                liquidez = float(pair.get('liquidity', {}).get('usd', 0))
                fdv = float(pair.get('fdv', 0))
                vol_24h = float(pair.get('volume', {}).get('h24', 0))
                if liquidez < liq_min or (f_max > 0 and fdv > f_max) or vol_24h == 0:
                    continue
                candidatos.append(pair)
            except:
                continue
        return candidatos[:20]
    except Exception as e:
        st.error(f"Erro: {e}")
        return []

def buscar_dados_binance(vol_threshold, vol_max):
    pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
             'ADA/USDT', 'AVAX/USDT', 'DOGE/USDT', 'DOT/USDT', 'MATIC/USDT',
             'PEPE/USDT', 'WIF/USDT', 'BONK/USDT', 'SHIB/USDT', 'ARB/USDT']
    exchange = ccxt.binance({'enableRateLimit': True})
    candidatos = []
    for symbol in pairs:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=25)
            if len(ohlcv) < 20: continue
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['vol_sma'] = df['volume'].rolling(window=20).mean()
            df['volatilidade'] = ((df['high'] - df['low']) / df['open']) * 100
            ultima = df.iloc[-2]
            vol_ratio = ultima['volume'] / ultima['vol_sma'] if ultima['vol_sma'] > 0 else 0
            if vol_ratio >= vol_threshold:
                ticker = exchange.fetch_ticker(symbol)
                candidatos.append({
                    'symbol': symbol, 'price': df.iloc[-1]['close'], 'vol_ratio': vol_ratio,
                    'volatilidade': ultima['volatilidade'], 'change_24h': ticker.get('percentage', 0),
                    'url': f"https://www.binance.com/pt-BR/trade/{symbol.replace('/', '_')}"
                })
        except: continue
    return candidatos

def buscar_dados_stocks(vol_threshold, price_max, custom_symbol=None):
    # Watchlist expandida: EUA, Brasil, ETFs
    watchlist = [
        # Big Tech
        "AAPL", "GOOGL", "MSFT", "TSLA", "AMZN", "META", "NVDA", "AMD", "NFLX", "ORCL",
        # Semicondutores
        "INTC", "QCOM", "AVGO", "MU", "ASML",
        # Financeiro EUA
        "JPM", "BAC", "GS", "V", "MA",
        # Energia
        "XOM", "CVX", "COP",
        # Brasil
        "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "B3SA3.SA", "WEGE3.SA", "RENT3.SA", 
        "MGLU3.SA", "BBAS3.SA", "ABEV3.SA", "SUZB3.SA", "JBSS3.SA", "ELET3.SA",
        # ETFs
        "SPY", "QQQ", "IWM", "BOVA11.SA", "SMAL11.SA"
    ]
    
    # Adiciona símbolo customizado se fornecido
    if custom_symbol and custom_symbol.strip():
        symbol_upper = custom_symbol.strip().upper()
        if symbol_upper not in watchlist:
            watchlist.insert(0, symbol_upper)
    
    candidatos = []
    for symbol in watchlist:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1mo", interval="1d")
            if hist.empty or len(hist) < 5: continue
            
            # Métricas
            avg_volume = hist['Volume'].rolling(window=20).mean().iloc[-1]
            current_volume = hist['Volume'].iloc[-1]
            vol_ratio = current_volume / avg_volume if avg_volume > 0 else 0
            
            price_change_1d = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            price_change_5d = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5]) * 100 if len(hist) >= 5 else 0
            
            # SMA para tendência
            sma_20 = hist['Close'].rolling(20).mean().iloc[-1] if len(hist) >= 20 else hist['Close'].mean()
            acima_sma = hist['Close'].iloc[-1] > sma_20
            
            # Score de momentum
            momentum_score = 0
            if vol_ratio >= 1.5: momentum_score += 1
            if price_change_1d > 0: momentum_score += 1
            if price_change_5d > 0: momentum_score += 1
            if acima_sma: momentum_score += 1
            
            if vol_ratio >= vol_threshold:
                info = ticker.info
                candidatos.append({
                    'symbol': symbol, 'name': info.get('shortName', symbol),
                    'price': hist['Close'].iloc[-1], 'vol_ratio': vol_ratio,
                    'price_change': price_change_1d, 'price_change_5d': price_change_5d,
                    'market_cap': info.get('marketCap', 0), 'acima_sma': acima_sma,
                    'momentum_score': momentum_score,
                    'url': f"https://finance.yahoo.com/quote/{symbol}"
                })
        except: continue
    
    # Ordena por momentum score
    candidatos.sort(key=lambda x: x.get('momentum_score', 0), reverse=True)
    return candidatos

# ============================================================================
# TAB 1: SCANNER
# ============================================================================
with tab1:
    st.title("🎯 Scanner")
    
    col_plat, col_filter = st.columns([1, 2])
    with col_plat:
        plataforma = st.selectbox("📊 Plataforma:", 
            options=["Cripto (DexScreener)", "Cripto (Binance)", "Ações (Stocks)"], index=0)
    
    with col_filter:
        if plataforma == "Cripto (DexScreener)":
            # Seletor de rede multi-chain
            chain_options = {
                "☀️ Solana": "solana",
                "⟠ Ethereum": "ethereum", 
                "🟡 BNB Chain": "bsc",
                "🔵 Arbitrum": "arbitrum",
                "🔷 Base": "base",
                "🟣 Polygon": "polygon",
                "🔺 Avalanche": "avalanche",
            }
            selected_chain = st.selectbox("🌐 Rede:", options=list(chain_options.keys()), index=0)
            chain_id = chain_options[selected_chain]
            
            c1, c2 = st.columns(2)
            liquidez_min = c1.number_input("Liquidez Mín ($)", value=1000, min_value=0)
            fdv_max = c2.number_input("FDV Máx ($)", value=100000000, min_value=0)
            
            auto_save_gems = st.toggle("💎 Salvar gemas automaticamente no banco", value=True)

        elif plataforma == "Cripto (Binance)":
            c1, c2 = st.columns(2)
            volume_mult = c1.slider("Volume Mín (x)", 0.5, 10.0, 1.0)
            volatilidade_max = c2.slider("Volatilidade Máx (%)", 1.0, 20.0, 10.0)
            
            # Autocomplete para pares Binance
            pares_binance = [
                "", "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
                "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT", "LINKUSDT", "LTCUSDT",
                "SHIBUSDT", "TRXUSDT", "ATOMUSDT", "UNIUSDT", "XLMUSDT", "NEARUSDT",
                "APTUSDT", "ARBUSDT", "OPUSDT", "SUIUSDT", "SEIUSDT", "INJUSDT",
                "BTCBRL", "ETHBRL", "SOLUSDT", "PEPEUSDT", "WIFUSDT", "BONKUSDT"
            ]
            busca_customizada = st.selectbox("🔍 Buscar par:", pares_binance, index=0, 
                help="Selecione um par ou deixe vazio para varrer todos")
        else:
            c1, c2 = st.columns(2)
            volume_mult = c1.slider("Volume Mín (x)", 0.5, 5.0, 1.0)
            preco_max_var = c2.slider("Variação Máx (%)", 1.0, 20.0, 10.0)
            
            # Autocomplete para ações
            acoes_disponiveis = [
                "", 
                # Big Tech
                "AAPL - Apple", "GOOGL - Alphabet", "MSFT - Microsoft", "AMZN - Amazon", 
                "META - Meta", "NVDA - NVIDIA", "TSLA - Tesla", "NFLX - Netflix", 
                # Semicondutores
                "AMD - AMD", "INTC - Intel", "QCOM - Qualcomm", "AVGO - Broadcom", "ASML - ASML",
                # Financeiro
                "JPM - JPMorgan", "BAC - Bank of America", "GS - Goldman Sachs", "V - Visa", "MA - Mastercard",
                # Energia
                "XOM - Exxon", "CVX - Chevron", "COP - ConocoPhillips",
                # Brasil
                "PETR4.SA - Petrobras", "VALE3.SA - Vale", "ITUB4.SA - Itaú", "BBDC4.SA - Bradesco",
                "B3SA3.SA - B3", "WEGE3.SA - WEG", "RENT3.SA - Localiza", "MGLU3.SA - Magazine Luiza",
                "BBAS3.SA - Banco do Brasil", "ABEV3.SA - Ambev", "SUZB3.SA - Suzano", 
                "JBSS3.SA - JBS", "ELET3.SA - Eletrobras", "CSAN3.SA - Cosan",
                "RADL3.SA - RaiaDrogasil", "RAIL3.SA - Rumo", "VBBR3.SA - Vibra",
                # ETFs
                "SPY - S&P 500 ETF", "QQQ - Nasdaq ETF", "IWM - Russell 2000",
                "BOVA11.SA - Ibovespa ETF", "SMAL11.SA - Small Caps BR"
            ]
            busca_selecionada = st.selectbox("🔍 Buscar ativo:", acoes_disponiveis, index=0,
                help="Selecione um ativo ou deixe vazio para usar watchlist completa")
            # Extrai só o símbolo (antes do " - ")
            busca_customizada = busca_selecionada.split(" - ")[0] if busca_selecionada else ""
    
    # Campo de busca para DexScreener
    if plataforma == "Cripto (DexScreener)":
        tokens_populares = [
            "", "solana", "ethereum", "bitcoin", "pepe", "shiba", "dogecoin",
            "bonk", "wif", "jup", "ray", "pyth", "jito", "orca", "marinade",
            "uniswap", "aave", "compound", "maker", "curve", "lido",
            "arbitrum", "optimism", "polygon", "avalanche", "fantom"
        ]
        busca_token = st.selectbox("🔍 Buscar token:", tokens_populares, index=0,
            help="Selecione um token popular ou deixe vazio para varrer a rede")
    else:
        busca_token = ""


    if st.button("🚀 Iniciar Scanner + Análise IA", type="primary"):
        with st.spinner(f"Varrendo {plataforma}..."):
            if plataforma == "Cripto (DexScreener)":
                from dex_scanner import scan_dexscreener
                if busca_token and busca_token.strip():
                    # Busca direta por token
                    raw_oportunidades = scan_dexscreener(busca_token.strip(), liquidez_min, fdv_max)
                else:
                    raw_oportunidades = scan_dexscreener(chain_id, liquidez_min, fdv_max)
                
                # Auto-salva gemas identificadas
                if auto_save_gems and raw_oportunidades:
                    from auth import salvar_gema_db
                    gems_salvas = 0
                    for gem in raw_oportunidades:
                        if salvar_gema_db(gem):
                            gems_salvas += 1
                    if gems_salvas > 0:
                        st.toast(f"💎 {gems_salvas} gemas salvas no banco!")
            elif plataforma == "Cripto (Binance)":
                raw_oportunidades = buscar_dados_binance(volume_mult, volatilidade_max)
            else:
                raw_oportunidades = buscar_dados_stocks(volume_mult, preco_max_var, busca_customizada)
        
        # Análise IA automática para cada resultado
        if raw_oportunidades and api_key and genai:
            st.info(f"🧠 Analisando {len(raw_oportunidades[:15])} ativos com IA...")
            progress = st.progress(0)
            
            client = genai.Client(api_key=api_key)
            
            analisados = []
            for i, op in enumerate(raw_oportunidades[:15]):  # Aumentado para 15
                progress.progress((i + 1) / len(raw_oportunidades[:15]))
                
                try:
                    # Monta texto do ativo com dados relevantes
                    if "DexScreener" in plataforma:
                        liq = op.get('liquidity', 0) if isinstance(op.get('liquidity'), (int, float)) else op.get('liquidity', {}).get('usd', 0)
                        vol = op.get('vol_anomaly', 0)
                        txt = f"Token: {op.get('symbol', '?')}, Rede: {op.get('chain', '?')}, Liquidez: ${liq:,.0f}, Vol Anomaly: {vol:.1f}x, Motivo: {op.get('reason', 'N/A')[:100]}"
                    elif "Binance" in plataforma:
                        txt = f"Par: {op.get('symbol','?')}, Preço: ${op.get('price',0):,.4f}, Volume: {op.get('vol_ratio',0):.1f}x média, Volatilidade: {op.get('volatilidade',0):.2f}%"
                    else:
                        momentum = op.get('momentum_score', 0)
                        acima_sma = "ACIMA" if op.get('acima_sma', False) else "ABAIXO"
                        txt = f"Ação: {op.get('symbol','?')}, Preço: ${op.get('price',0):,.2f}, Volume: {op.get('vol_ratio',0):.1f}x, Var 1D: {op.get('price_change',0):.2f}%, Var 5D: {op.get('price_change_5d',0):.2f}%, {acima_sma} da SMA20, Momentum: {momentum}/4"
                    
                    prompt = f"""Você é um analista quantitativo. Analise este ativo de forma DIRETA:

{txt}

Responda APENAS no formato:
[SINAL]: COMPRAR | AGUARDAR | EVITAR
[FORÇA]: 1-10
[MOTIVO]: máximo 15 palavras

Seja preciso. Zero rodeios."""
                    
                    response = client.models.generate_content(
                        model='gemini-3-flash-preview',
                        contents=prompt
                    )
                    veredito = response.text.strip()[:150]
                    
                    # Classifica para ordenar (novo formato)
                    if "COMPRAR" in veredito.upper():
                        score = 3
                    elif "AGUARDAR" in veredito.upper():
                        score = 2
                    else:
                        score = 1
                    
                    op['ia_veredito'] = veredito
                    op['ia_score'] = score
                    analisados.append(op)
                except Exception as e:
                    op['ia_veredito'] = f"Erro: {str(e)[:30]}"
                    op['ia_score'] = 0
                    analisados.append(op)
            
            # Ordena por score (melhores primeiro)
            analisados.sort(key=lambda x: x.get('ia_score', 0), reverse=True)
            st.session_state.oportunidades = analisados
            progress.empty()
        else:
            st.session_state.oportunidades = raw_oportunidades

    oportunidades = st.session_state.oportunidades
    if oportunidades:
        st.success(f"🎯 {len(oportunidades)} ativos analisados | Ordenados por oportunidade")
        
        for idx, op in enumerate(oportunidades[:15]):
            symbol_display = op.get('baseToken', {}).get('symbol', op.get('symbol', 'N/A'))
            is_fav = is_favorito(op, plataforma)
            veredito = op.get('ia_veredito', '')
            score = op.get('ia_score', 0)
            
            # Emoji baseado no score
            if score == 3:
                badge = "🟢"
            elif score == 2:
                badge = "🟡"
            else:
                badge = "🔴"
            
            with st.expander(f"{badge} {'⭐' if is_fav else ''} **{symbol_display}**", expanded=(score == 3)):
                # Veredito da IA em destaque
                if veredito:
                    if score == 3:
                        st.success(f"🧠 **{veredito}**")
                    elif score == 2:
                        st.warning(f"🧠 {veredito}")
                    else:
                        st.error(f"🧠 {veredito}")
                
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    if plataforma == "Cripto (DexScreener)":
                        # Nome do token
                        token_name = op.get('name', op.get('baseToken', {}).get('name', 'N/A')) if isinstance(op.get('baseToken'), dict) else op.get('symbol', 'N/A')
                        st.write(f"**{token_name}** | {op.get('dex', op.get('dexId', 'N/A'))}")
                        
                        # Liquidez - handle both dict and number formats
                        liq = op.get('liquidity', 0)
                        if isinstance(liq, dict):
                            liq_value = liq.get('usd', 0)
                        else:
                            liq_value = liq if liq else 0
                        st.write(f"Liquidez: ${liq_value:,.0f}")
                        st.write(f"🔗 [DexScreener]({op.get('url','#')})")
                    elif plataforma == "Cripto (Binance)":
                        st.write(f"**{op.get('symbol','N/A')}** | ${op.get('price',0):,.4f}")
                        st.write(f"Volume: {op.get('vol_ratio',0):.1f}x | Vol: {op.get('volatilidade',0):.2f}%")
                        st.write(f"🔗 [Binance]({op.get('url','#')})")
                    else:
                        st.write(f"**{op.get('name', op.get('symbol', 'N/A'))}** | ${op.get('price', 0):,.2f}")
                        st.write(f"Volume: {op.get('vol_ratio', 0):.1f}x média")
                        st.write(f"🔗 [Yahoo Finance]({op.get('url', '#')})")
                
                with col2:
                    if is_fav:
                        st.success("⭐ Monitorando")
                    else:
                        if st.button("⭐ Monitorar", key=f"fav_{idx}"):
                            adicionar_favorito(op, plataforma)
                            st.rerun()
    else:
        st.info("👆 Clique em 'Iniciar Scanner + Análise IA'")

# ============================================================================
# TAB 2: FAVORITOS
# ============================================================================
with tab2:
    st.title("⭐ Favoritos Monitorados")
    
    if not st.session_state.favoritos:
        st.info("Nenhum favorito. Use o Scanner e clique ⭐ para monitorar!")
    else:
        st.success(f"📊 {len(st.session_state.favoritos)} ativos monitorados")
        st.caption("💡 Execute o monitor em segundo plano para receber alertas no Telegram")
        
        # Comando para iniciar o monitor
        with st.expander("📡 Como ativar alertas automáticos"):
            st.code("./.venv/bin/python MarketHunter/favorites_monitor.py", language="bash")
            st.write("Execute este comando em um terminal separado para receber alertas de COMPRA/VENDA no Telegram.")
        
        for fav in st.session_state.favoritos:
            key = fav['key']
            dados = fav['data']
            plat = fav['plataforma']
            
            with st.expander(f"⭐ **{fav['symbol']}** - {fav['name']}", expanded=True):
                col_info, col_actions = st.columns([2, 1])
                
                with col_info:
                    st.caption(f"📍 {plat} | Adicionado: {fav['added_at']}")
                    if "DexScreener" in plat:
                        st.write(f"Liquidez: ${dados.get('liquidity',{}).get('usd',0):,.0f}")
                    else:
                        st.write(f"Preço: ${dados.get('price',0):,.4f}")
                
                with col_actions:
                    if st.button("🗑️", key=f"rem_{key}"):
                        remover_favorito(key)
                        st.rerun()
                
                if st.button("🧠 Análise Detalhada", key=f"analise_{key}", type="primary"):
                    with st.spinner("Analisando..."):
                        resultado = gerar_analise_detalhada(dados, key, plat)
                        st.session_state.analise_detalhada[key] = resultado
                
                if key in st.session_state.analise_detalhada:
                    resultado = st.session_state.analise_detalhada[key]
                    if "COMPRAR" in resultado.upper():
                        st.success(resultado)
                    elif "VENDER" in resultado.upper():
                        st.error(resultado)
                    else:
                        st.warning(resultado)

# ============================================================================
# TAB 3: AMBIENTE (Trading Dashboard)
# ============================================================================
with tab3:
    st.title("📈 Ambiente de Trading")
    st.caption("Gráficos interativos e indicadores técnicos em tempo real")
    
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        
        col_asset, col_period = st.columns([2, 1])
        with col_asset:
            asset_options = {
                "📊 Índices": ["^BVSP", "^GSPC", "^DJI", "^IXIC"],
                "🪙 Crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"],
                "🇧🇷 Brasil": ["PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA"],
                "🇺🇸 EUA": ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA"]
            }
            categoria_ativo = st.selectbox("📂 Categoria:", list(asset_options.keys()))
            ativo_chart = st.selectbox("🎯 Ativo:", asset_options[categoria_ativo])
        
        with col_period:
            periodo = st.selectbox("📅 Período:", ["1mo", "3mo", "6mo", "1y"], index=1)
        
        if st.button("📊 Carregar Gráfico", type="primary", key="load_chart"):
            with st.spinner(f"Carregando {ativo_chart}..."):
                try:
                    ticker = yf.Ticker(ativo_chart)
                    hist = ticker.history(period=periodo)
                    
                    if not hist.empty:
                        hist['SMA_20'] = hist['Close'].rolling(20).mean()
                        hist['SMA_50'] = hist['Close'].rolling(50).mean()
                        delta = hist['Close'].diff()
                        gain = delta.where(delta > 0, 0).rolling(14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                        hist['RSI'] = 100 - (100 / (1 + gain / loss))
                        
                        fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                                          vertical_spacing=0.05, row_heights=[0.6, 0.2, 0.2])
                        
                        fig.add_trace(go.Candlestick(
                            x=hist.index, open=hist['Open'], high=hist['High'],
                            low=hist['Low'], close=hist['Close'], name='Preço'), row=1, col=1)
                        fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_20'], 
                                               line=dict(color='orange', width=1), name='SMA 20'), row=1, col=1)
                        fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_50'],
                                               line=dict(color='blue', width=1), name='SMA 50'), row=1, col=1)
                        
                        colors = ['green' if c >= o else 'red' for c, o in zip(hist['Close'], hist['Open'])]
                        fig.add_trace(go.Bar(x=hist.index, y=hist['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
                        fig.add_trace(go.Scatter(x=hist.index, y=hist['RSI'], line=dict(color='purple'), name='RSI'), row=3, col=1)
                        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
                        fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
                        
                        fig.update_layout(height=600, showlegend=True, xaxis_rangeslider_visible=False)
                        st.plotly_chart(fig, use_container_width=True)
                        
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Preço", f"${hist['Close'].iloc[-1]:,.2f}")
                        change_pct = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2] * 100)
                        col2.metric("Variação", f"{change_pct:+.2f}%")
                        col3.metric("RSI", f"{hist['RSI'].iloc[-1]:.1f}")
                        col4.metric("Volume", f"{hist['Volume'].iloc[-1]:,.0f}")
                except Exception as e:
                    st.error(f"Erro: {e}")
    except ImportError:
        st.error("📦 Plotly não instalado.")


# ============================================================================
# TAB 4: SIMULADOR INTELIGENTE
# ============================================================================
with tab4:
    st.title("🧮 Simulador de Operações")
    
    if not st.session_state.favoritos:
        st.info("⭐ Adicione ativos aos favoritos no Scanner para usar o simulador.")
    else:
        favoritos_opcoes = {f"{fav['symbol']} ({fav.get('plataforma', '')[:10]})": fav for fav in st.session_state.favoritos}
        ativo_sim = st.selectbox("🎯 Selecione um favorito:", list(favoritos_opcoes.keys()), key="sim_asset")
        fav = favoritos_opcoes[ativo_sim]
        
        # Extrai preço atual dos dados do favorito
        dados = fav.get('data', {})
        plat = fav.get('plataforma', '')
        
        if "DexScreener" in plat:
            preco_atual = float(dados.get('priceUsd', 0) or dados.get('priceNative', 0) or 0.0001)
        elif "Binance" in plat:
            preco_atual = float(dados.get('price', 0) or 0.0001)
        else:
            preco_atual = float(dados.get('price', 0) or 0.0001)
        
        # Valores sugeridos baseados no preço
        preco_default = preco_atual if preco_atual > 0 else 1.0
        stop_default = preco_default * 0.95  # -5%
        target_default = preco_default * 1.10  # +10%
        
        st.markdown("---")
        st.subheader("💰 Calculadora de Posição")
        
        # Exibe preço atual do ativo
        if preco_atual > 0:
            st.info(f"📊 **Preço atual de {fav['symbol']}**: ${preco_atual:,.6f}")
        
        # Toggle: Comprar por valor ou por quantidade
        modo_compra = st.radio("📝 Modo de compra:", ["💵 Por capital ($)", "📦 Por quantidade"], horizontal=True)
        
        col1, col2 = st.columns(2)
        with col1:
            preco_entrada = st.number_input("📈 Preço de entrada ($)", value=preco_default, min_value=0.0000001, format="%.6f")
            
            if modo_compra == "💵 Por capital ($)":
                capital = st.number_input("💵 Capital a investir ($)", value=1000.0, min_value=0.01)
                quantidade = capital / preco_entrada if preco_entrada > 0 else 0
            else:
                quantidade = st.number_input("📦 Quantidade de unidades", value=100.0, min_value=0.01)
                capital = quantidade * preco_entrada
                
        with col2:
            stop_loss = st.number_input("🛑 Stop Loss ($)", value=stop_default, min_value=0.0000001, format="%.6f")
            take_profit = st.number_input("🎯 Take Profit ($)", value=target_default, min_value=0.0000001, format="%.6f")
        
        # Cálculos
        valor_investido = quantidade * preco_entrada
        ganho_por_unidade = take_profit - preco_entrada
        perda_por_unidade = preco_entrada - stop_loss
        ganho_total = ganho_por_unidade * quantidade
        perda_total = perda_por_unidade * quantidade
        ganho_pct = (ganho_por_unidade / preco_entrada) * 100 if preco_entrada > 0 else 0
        perda_pct = (perda_por_unidade / preco_entrada) * 100 if preco_entrada > 0 else 0
        rr_ratio = ganho_por_unidade / perda_por_unidade if perda_por_unidade > 0 else 0
        
        # Métricas adicionais
        breakeven = preco_entrada
        target_move = ((take_profit - preco_entrada) / preco_entrada) * 100
        stop_move = ((preco_entrada - stop_loss) / preco_entrada) * 100
        
        st.markdown("---")
        st.subheader("📊 Análise da Operação")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📦 Quantidade", f"{quantidade:,.4f}")
        c2.metric("💵 Valor Investido", f"${valor_investido:,.2f}")
        c3.metric("🎯 Ganho Potencial", f"${ganho_total:,.2f}", delta=f"+{ganho_pct:.2f}%")
        c4.metric("🛑 Perda Potencial", f"${perda_total:,.2f}", delta=f"-{perda_pct:.2f}%")
        
        # Métricas de risco
        st.markdown("### 📈 Métricas de Risco")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("⚖️ R/R Ratio", f"{rr_ratio:.2f}:1")
        m2.metric("📉 Distância Stop", f"-{stop_move:.2f}%")
        m3.metric("📈 Distância Target", f"+{target_move:.2f}%")
        m4.metric("💰 Breakeven", f"${breakeven:,.6f}")
        
        if rr_ratio >= 3:
            st.success(f"✅ Risco/Recompensa: {rr_ratio:.2f}:1 - **Operação favorável**")
        elif rr_ratio >= 2:
            st.info(f"🟡 Risco/Recompensa: {rr_ratio:.2f}:1 - **Aceitável**")
        elif rr_ratio >= 1:
            st.warning(f"⚠️ Risco/Recompensa: {rr_ratio:.2f}:1 - **Marginal**")
        else:
            st.error(f"❌ Risco/Recompensa: {rr_ratio:.2f}:1 - **Operação desfavorável**")
        
        st.markdown("---")
        st.subheader("🧠 Análise Técnica IA")
        
        if st.button("📊 Analisar Operação", type="primary", key="sim_predict"):
            if api_key and genai:
                with st.spinner("Processando análise..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        dados_fav = fav.get('data', {})
                        prompt = f"""
Você é um analista quantitativo. Analise esta operação de forma objetiva e direta:

DADOS DA OPERAÇÃO:
- Ativo: {fav['symbol']}
- Quantidade: {quantidade:.4f} unidades
- Capital: ${valor_investido:,.2f}
- Entrada: ${preco_entrada:.6f}
- Stop Loss: ${stop_loss:.6f} (-{perda_pct:.2f}%, perda: ${perda_total:,.2f})
- Take Profit: ${take_profit:.6f} (+{ganho_pct:.2f}%, ganho: ${ganho_total:,.2f})
- Risco/Recompensa: {rr_ratio:.2f}:1

DADOS DO ATIVO:
{json.dumps(dados_fav, default=str)[:800]}

Forneça análise DIRETA e TÉCNICA:

## 📊 PARECER DA OPERAÇÃO
[FAVORÁVEL/NEUTRO/DESFAVORÁVEL] - Justificativa matemática

## 📈 PONTOS DE ENTRADA/SAÍDA
- Avalie se os níveis estão bem posicionados

## ⚠️ RISCOS IDENTIFICADOS
- Liste riscos objetivos baseados nos dados

## 🎯 RECOMENDAÇÃO
- Ação clara: ENTRAR, AGUARDAR ou EVITAR
- Se ENTRAR, ajustes sugeridos nos níveis

Seja direto. Máximo 180 palavras.
"""
                        response = client.models.generate_content(model='gemini-3-flash-preview', contents=prompt)
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"Erro: {e}")
            else:
                st.error("⚠️ Configure a Gemini API Key.")

# ============================================================================
# TAB 5: HISTÓRICO DE ALERTAS
# ============================================================================
with tab5:
    st.title("🚨 Histórico de Alertas")
    
    alertas = carregar_alertas()
    
    if not alertas:
        st.info("Nenhum alerta ainda. Ative o monitor para receber alertas automáticos!")
    else:
        for alerta in alertas[:20]:
            acao = alerta.get('acao', '')
            if acao == "COMPRAR":
                st.success(f"🟢 **{alerta.get('symbol')}** - {alerta.get('mensagem', '')[:100]}...")
            elif acao == "VENDER":
                st.error(f"🔴 **{alerta.get('symbol')}** - {alerta.get('mensagem', '')[:100]}...")
            else:
                st.info(f"🟡 **{alerta.get('symbol')}** - {alerta.get('mensagem', '')[:100]}...")

# ============================================================================
# TAB 6: NOTÍCIAS
# ============================================================================
with tab6:
    st.title("📰 Notícias")
    
    categoria = st.selectbox("📂 Categoria:", options=["crypto", "stocks", "brazil"],
        format_func=lambda x: {"crypto": "🪙 Crypto", "stocks": "📈 Global", "brazil": "🇧🇷 Brasil"}[x], key="news_cat")
    
    if categoria not in st.session_state.news_cache:
        with st.spinner("Carregando..."):
            st.session_state.news_cache[categoria] = fetch_all_news(categoria, max_per_source=5)
    
    news_list = st.session_state.news_cache.get(categoria, [])
    
    if news_list:
        for news in news_list[:10]:
            st.markdown(f"**{news.get('icon', '📰')} [{news['title']}]({news['link']})**")
            st.caption(f"📍 {news['source_name']} • ⏰ {news['published']}")
            st.markdown("---")

# Rodapé
st.sidebar.markdown("---")
st.sidebar.caption(f"🦅 v4.0 | {datetime.now().strftime('%H:%M')}")

