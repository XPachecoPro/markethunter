###############################################################################
# FILE: app.py - MarketHunter Dashboard v3.6 (Phone Formatting)
###############################################################################
import streamlit as st
import requests
import json
import os
from datetime import datetime

# Imports com fallback para cloud
try:
    import google.generativeai as genai
except ImportError:
    genai = None

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
    from auth import cadastrar_usuario, autenticar_usuario
except ImportError:
    def cadastrar_usuario(*args): return False, "Módulo auth não disponível"
    def autenticar_usuario(*args): return False, None, "Módulo auth não disponível"

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

# Arquivos de dados
FAVORITES_FILE = "favorites_data.json"
ALERTS_FILE = "alerts_data.json"

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
        st.caption("🔒 Seus dados são armazenados localmente de forma segura.")

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
# FUNÇÕES DE PERSISTÊNCIA
# ============================================================================

def carregar_favoritos_arquivo():
    """Carrega favoritos do arquivo JSON."""
    try:
        if os.path.exists(FAVORITES_FILE):
            with open(FAVORITES_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return []

def salvar_favoritos_arquivo():
    """Salva favoritos no arquivo JSON para o monitor E no Supabase."""
    try:
        # Salva localmente para o monitor
        with open(FAVORITES_FILE, 'w') as f:
            json.dump(st.session_state.favoritos, f, default=str)
        
        # Salva no Supabase
        if st.session_state.user:
            from auth import salvar_favoritos_usuario
            email = st.session_state.user.get('email')
            if email:
                salvar_favoritos_usuario(email, st.session_state.favoritos)
    except Exception as e:
        st.error(f"Erro ao salvar favoritos: {e}")

def carregar_alertas():
    """Carrega alertas do monitor."""
    try:
        if os.path.exists(ALERTS_FILE):
            with open(ALERTS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return []

# Carrega favoritos do usuário (do Supabase se disponível)
if not st.session_state.favoritos and st.session_state.user:
    user_favoritos = st.session_state.user.get('favoritos', [])
    if user_favoritos:
        st.session_state.favoritos = user_favoritos
    else:
        st.session_state.favoritos = carregar_favoritos_arquivo()

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
# API Key interna (não exposta na UI)
api_key = "AIzaSyABrNzrlu_dye66T-TVefG0eHIfOWEsr_A"

# Monitor Status
st.sidebar.markdown("---")
st.sidebar.subheader("📡 Monitor")
st.sidebar.metric("⭐ Favoritos", len(st.session_state.favoritos))

# Verifica alertas do monitor
alertas = carregar_alertas()
alertas_novos = [a for a in alertas if a.get('timestamp') not in st.session_state.alertas_vistos]

if alertas_novos:
    st.sidebar.error(f"🚨 {len(alertas_novos)} alertas!")
else:
    st.sidebar.success("✓ Monitorando")

# ============================================================================
# POPUP DE ALERTAS (TOPO DA PÁGINA)
# ============================================================================

if alertas_novos:
    for alerta in alertas_novos[:3]:  # Mostra até 3 alertas
        acao = alerta.get('acao', '')
        symbol = alerta.get('symbol', 'N/A')
        msg = alerta.get('mensagem', '')
        
        if acao == "COMPRAR":
            st.success(f"""
            🚨 **ALERTA DE COMPRA - {symbol}**
            
            {msg}
            
            ⏰ {alerta.get('timestamp', '')}
            """)
        elif acao == "VENDER":
            st.error(f"""
            🚨 **ALERTA DE VENDA - {symbol}**
            
            {msg}
            
            ⏰ {alerta.get('timestamp', '')}
            """)
        
        # Marca como visto
        st.session_state.alertas_vistos.add(alerta.get('timestamp'))
    
    if st.button("✓ Marcar alertas como lidos", key="dismiss_alerts"):
        st.rerun()

# === TABS PRINCIPAIS ===
tab1, tab2, tab3, tab4 = st.tabs(["🎯 Scanner", "⭐ Favoritos", "🚨 Alertas", "📰 Notícias"])

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def get_asset_key(op, plataforma):
    if "DexScreener" in plataforma:
        return f"dex_{op.get('pairAddress', op.get('baseToken', {}).get('symbol', 'unknown'))}"
    elif "Binance" in plataforma:
        return f"binance_{op.get('symbol', 'unknown')}"
    else:
        return f"stock_{op.get('symbol', 'unknown')}"

def is_favorito(op, plataforma):
    key = get_asset_key(op, plataforma)
    return any(f.get('key') == key for f in st.session_state.favoritos)

def adicionar_favorito(op, plataforma):
    key = get_asset_key(op, plataforma)
    if not is_favorito(op, plataforma):
        favorito = {
            'key': key,
            'data': op,
            'plataforma': plataforma,
            'added_at': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'symbol': op.get('baseToken', {}).get('symbol', op.get('symbol', 'N/A')),
            'name': op.get('baseToken', {}).get('name', op.get('name', op.get('symbol', 'N/A')))
        }
        st.session_state.favoritos.append(favorito)
        salvar_favoritos_arquivo()  # Salva para o monitor
        return True
    return False

def remover_favorito(key):
    st.session_state.favoritos = [f for f in st.session_state.favoritos if f.get('key') != key]
    if key in st.session_state.analise_detalhada:
        del st.session_state.analise_detalhada[key]
    salvar_favoritos_arquivo()  # Atualiza arquivo

def gerar_analise_detalhada(dados, key, plataforma):
    if not api_key:
        return "⚠️ Informe a Gemini API Key."
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
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
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ Erro: {str(e)}"

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

def buscar_dados_stocks(vol_threshold, price_max):
    watchlist = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN", "META", "NVDA", "AMD",
                 "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA"]
    candidatos = []
    for symbol in watchlist:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1mo", interval="1d")
            if hist.empty or len(hist) < 5: continue
            avg_volume = hist['Volume'].rolling(window=20).mean().iloc[-1]
            current_volume = hist['Volume'].iloc[-1]
            price_change = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            vol_ratio = current_volume / avg_volume if avg_volume > 0 else 0
            if vol_ratio >= vol_threshold:
                info = ticker.info
                candidatos.append({
                    'symbol': symbol, 'name': info.get('shortName', symbol),
                    'price': hist['Close'].iloc[-1], 'vol_ratio': vol_ratio,
                    'price_change': price_change, 'market_cap': info.get('marketCap', 0),
                    'url': f"https://finance.yahoo.com/quote/{symbol}"
                })
        except: continue
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
            query = st.text_input("🔍 Busca", value="solana")
            c1, c2 = st.columns(2)
            liquidez_min = c1.number_input("Liquidez Mín ($)", value=1000, min_value=0)
            fdv_max = c2.number_input("FDV Máx ($)", value=100000000, min_value=0)
        elif plataforma == "Cripto (Binance)":
            c1, c2 = st.columns(2)
            volume_mult = c1.slider("Volume Mín (x)", 0.5, 10.0, 1.0)
            volatilidade_max = c2.slider("Volatilidade Máx (%)", 1.0, 20.0, 10.0)
        else:
            c1, c2 = st.columns(2)
            volume_mult = c1.slider("Volume Mín (x)", 0.5, 5.0, 1.0)
            preco_max_var = c2.slider("Variação Máx (%)", 1.0, 20.0, 10.0)

    if st.button("🚀 Iniciar Scanner + Análise IA", type="primary"):
        with st.spinner(f"Varrendo {plataforma}..."):
            if plataforma == "Cripto (DexScreener)":
                raw_oportunidades = buscar_dados_dexscreener(query, liquidez_min, fdv_max)
            elif plataforma == "Cripto (Binance)":
                raw_oportunidades = buscar_dados_binance(volume_mult, volatilidade_max)
            else:
                raw_oportunidades = buscar_dados_stocks(volume_mult, preco_max_var)
        
        # Análise IA automática para cada resultado
        if raw_oportunidades and api_key:
            st.info(f"🧠 Analisando {len(raw_oportunidades[:10])} ativos com IA...")
            progress = st.progress(0)
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            analisados = []
            for i, op in enumerate(raw_oportunidades[:10]):  # Limita a 10 para não sobrecarregar
                progress.progress((i + 1) / len(raw_oportunidades[:10]))
                
                try:
                    # Monta texto do ativo
                    if "DexScreener" in plataforma:
                        txt = f"Token {op.get('baseToken',{}).get('symbol','?')}, Liq ${op.get('liquidity',{}).get('usd',0):,.0f}, FDV ${op.get('fdv',0):,.0f}, Vol 24h ${op.get('volume',{}).get('h24',0):,.0f}"
                    elif "Binance" in plataforma:
                        txt = f"Par {op.get('symbol','?')}, Preço ${op.get('price',0):,.4f}, Volume {op.get('vol_ratio',0):.1f}x média"
                    else:
                        txt = f"Ação {op.get('symbol','?')}, Preço ${op.get('price',0):,.2f}, Volume {op.get('vol_ratio',0):.1f}x média"
                    
                    prompt = f"Analise rapidamente e responda APENAS com: OPORTUNIDADE, OBSERVAR ou RISCO + motivo em 10 palavras. {txt}"
                    response = model.generate_content(prompt)
                    veredito = response.text.strip()[:100]
                    
                    # Classifica para ordenar
                    if "OPORTUNIDADE" in veredito.upper():
                        score = 3
                    elif "OBSERVAR" in veredito.upper():
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
                        st.write(f"**{op.get('baseToken',{}).get('name','N/A')}** | {op.get('dexId','N/A')}")
                        st.write(f"Liquidez: ${op.get('liquidity',{}).get('usd',0):,.0f}")
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
# TAB 3: HISTÓRICO DE ALERTAS
# ============================================================================
with tab3:
    st.title("🚨 Histórico de Alertas")
    
    alertas = carregar_alertas()
    
    if not alertas:
        st.info("Nenhum alerta ainda. Ative o monitor para receber alertas automáticos!")
    else:
        for alerta in alertas[:20]:
            acao = alerta.get('acao', '')
            if acao == "COMPRAR":
                st.success(f"🟢 **{alerta.get('symbol')}** - {alerta.get('mensagem', '')[:100]}... ({alerta.get('timestamp', '')})")
            elif acao == "VENDER":
                st.error(f"🔴 **{alerta.get('symbol')}** - {alerta.get('mensagem', '')[:100]}... ({alerta.get('timestamp', '')})")
            else:
                st.info(f"🟡 **{alerta.get('symbol')}** - {alerta.get('mensagem', '')[:100]}... ({alerta.get('timestamp', '')})")

# ============================================================================
# TAB 4: NOTÍCIAS
# ============================================================================
with tab4:
    st.title("📰 Notícias")
    
    categoria = st.selectbox("📂 Categoria:",
        options=["crypto", "stocks", "brazil"],
        format_func=lambda x: {"crypto": "🪙 Crypto", "stocks": "📈 Global", "brazil": "🇧🇷 Brasil"}[x])
    
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
st.sidebar.caption(f"🦅 v3.4 | {datetime.now().strftime('%H:%M')}")
