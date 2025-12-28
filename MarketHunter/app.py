###############################################################################
# FILE: app.py - MarketHunter Dashboard v3.6 (Phone Formatting)
###############################################################################
import streamlit as st
import requests
import json
import os
import threading
import time
import re
from datetime import datetime, timedelta

# ============ DIAGNÓSTICO DE SECRETS (remover em produção) ============
def check_secrets_status():
    """Verifica status das configurações de secrets"""
    status = {}
    try:
        status['supabase_url'] = bool(st.secrets.get("supabase", {}).get("url"))
        status['supabase_key'] = bool(st.secrets.get("supabase", {}).get("key"))
        status['telegram_token'] = bool(st.secrets.get("telegram", {}).get("bot_token"))
        status['gemini_key'] = bool(st.secrets.get("gemini", {}).get("api_key"))
    except Exception as e:
        status['error'] = str(e)
    return status

_SECRETS_STATUS = check_secrets_status()
# ======================================================================

# Cache de análises IA (evita chamadas redundantes)
# Estrutura: { "symbol_platform": {"response": str, "forca": int, "timestamp": datetime} }
if 'ia_cache' not in st.session_state:
    st.session_state.ia_cache = {}
IA_CACHE_TTL_MINUTES = 30  # Cache válido por 30 minutos

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

_AUTH_IMPORT_ERROR = None
try:
    from auth import (
        cadastrar_usuario, autenticar_usuario, atualizar_usuario,
        buscar_favoritos_usuario, adicionar_favorito_db, remover_favorito_db,
        buscar_alertas_usuario, salvar_alerta_db
    )
except Exception as e:
    _AUTH_IMPORT_ERROR = f"{type(e).__name__}: {str(e)}"
    # Gerar mensagem de diagnóstico
    _diag = f"Secrets: supabase_url={_SECRETS_STATUS.get('supabase_url')}, supabase_key={_SECRETS_STATUS.get('supabase_key')}"
    _full_error = f"🔴 AUTH FALHOU: {_AUTH_IMPORT_ERROR} | {_diag}"
    def cadastrar_usuario(*args): return False, _full_error
    def autenticar_usuario(*args): return False, None, _full_error
    def atualizar_usuario(*args): return False
    def buscar_favoritos_usuario(*args): return []
    def adicionar_favorito_db(*args): return False, _full_error
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
    """
    Formata número de telefone com detecção inteligente de país.
    
    Detecta automaticamente o país baseado no padrão do número:
    - Brasil: 11 dígitos (DDD 2 + número 9 começando com 9)
    - EUA/Canadá: 10 dígitos
    - Portugal: 9 dígitos começando com 9
    - Argentina: 10-11 dígitos começando com 9 ou 11
    """
    if not numero_raw:
        return "", "", "🌍"
    
    # Remove caracteres não numéricos exceto +
    numero_limpo = ''.join(c for c in numero_raw if c.isdigit() or c == '+')
    
    # Se já tem código de país, usa direto
    if numero_limpo.startswith('+'):
        try:
            parsed = phonenumbers.parse(numero_limpo, default_region)
            if phonenumbers.is_valid_number(parsed):
                formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                country_code = phonenumbers.region_code_for_number(parsed)
                flag = COUNTRY_FLAGS.get(country_code, "🌍")
                return formatted, country_code, flag
        except:
            pass
        return numero_raw, "", "⚠️"
    
    # DETECÇÃO INTELIGENTE DE PAÍS
    # Remove zeros à esquerda
    numero_sem_zero = numero_limpo.lstrip('0')
    
    ddi_detectado = None
    pais_detectado = None
    
    # Brasil: 11 dígitos (DDD 2 dígitos + 9 dígitos começando com 9)
    # Exemplo: 11999999999
    if len(numero_sem_zero) == 11 and numero_sem_zero[2] == '9':
        ddi_detectado = "+55"
        pais_detectado = "BR"
    
    # Brasil: 10 dígitos (DDD 2 + 8 dígitos - telefone fixo)
    elif len(numero_sem_zero) == 10 and numero_sem_zero[0:2].isdigit():
        ddi_detectado = "+55"
        pais_detectado = "BR"
    
    # EUA/Canadá: 10 dígitos
    elif len(numero_sem_zero) == 10:
        ddi_detectado = "+1"
        pais_detectado = "US"
    
    # Portugal: 9 dígitos começando com 9 (móvel)
    elif len(numero_sem_zero) == 9 and numero_sem_zero.startswith('9'):
        ddi_detectado = "+351"
        pais_detectado = "PT"
    
    # Espanha: 9 dígitos começando com 6 ou 7 (móvel)
    elif len(numero_sem_zero) == 9 and numero_sem_zero[0] in ['6', '7']:
        ddi_detectado = "+34"
        pais_detectado = "ES"
    
    # Argentina: 10 dígitos começando com 9 ou 11
    elif len(numero_sem_zero) in [10, 11] and numero_sem_zero.startswith(('9', '11')):
        ddi_detectado = "+54"
        pais_detectado = "AR"
    
    # México: 10 dígitos
    elif len(numero_sem_zero) == 10 and numero_sem_zero[0] in ['1', '2', '3', '4', '5', '6', '7', '8']:
        ddi_detectado = "+52"
        pais_detectado = "MX"
    
    # Default: Brasil
    else:
        ddi_detectado = "+55"
        pais_detectado = "BR"
    
    # Tenta parsear com o DDI detectado
    numero_completo = ddi_detectado + numero_sem_zero
    
    try:
        parsed = phonenumbers.parse(numero_completo, pais_detectado)
        
        if phonenumbers.is_valid_number(parsed):
            # Formata no padrão internacional
            formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
            country_code = phonenumbers.region_code_for_number(parsed)
            flag = COUNTRY_FLAGS.get(country_code, "🌍")
            return formatted, country_code, flag
        else:
            # Número inválido mas mostra o que detectou
            flag = COUNTRY_FLAGS.get(pais_detectado, "⚠️")
            return f"{ddi_detectado} {numero_raw}", pais_detectado, flag
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
            # Campo de telefone com auto-detecção de país
            col_phone, col_flag = st.columns([5, 1])
            
            with col_phone:
                telefone_raw = st.text_input(
                    "📱 Telefone", 
                    key="registro_telefone", 
                    placeholder="+55 11 99999-9999",
                    help="Digite com o código do país (ex: +55 para Brasil, +1 para EUA)"
                )
            
            # Auto-detecta país e formata número
            telefone_formatado, pais_code, bandeira = formatar_telefone(telefone_raw)
            
            with col_flag:
                st.markdown(f"<div style='font-size: 2.5em; text-align: center; margin-top: 25px;'>{bandeira}</div>", unsafe_allow_html=True)
            
            # Mostra número formatado se válido
            if telefone_raw:
                if telefone_formatado and pais_code:
                    st.success(f"✓ {telefone_formatado} ({pais_code})")
                elif not telefone_raw.startswith("+"):
                    st.info("💡 Adicione o código do país: +55 para Brasil, +1 para EUA, +351 para Portugal...")
            
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
            sucesso, msg = adicionar_favorito_db(st.session_state.user['id'], favorito)
            if sucesso:
                st.session_state.favoritos.append(favorito)
                st.toast(f"⭐ {favorito['symbol']} adicionado aos favoritos!")
                return True
            else:
                st.error(f"❌ Erro ao salvar favorito: {msg}")
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
            # Handle liquidity - can be dict or number
            liq = dados.get('liquidity', 0)
            liq_value = liq.get('usd', 0) if isinstance(liq, dict) else (liq if liq else 0)
            
            # Handle volume - can be dict or number
            vol = dados.get('volume', 0)
            vol_value = vol.get('h24', 0) if isinstance(vol, dict) else (vol if vol else 0)
            
            # Handle symbol - can be in baseToken or direct
            token_info = dados.get('baseToken', {})
            symbol = token_info.get('symbol', dados.get('symbol', 'N/A')) if isinstance(token_info, dict) else dados.get('symbol', 'N/A')
            
            texto = f"Token: {symbol}\nLiquidez: ${liq_value:,.0f}\nVolume 24h: ${vol_value:,.0f}"
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
# ANÁLISE TÉCNICA INTELIGENTE
# ============================================================================

def calcular_indicadores_tecnicos(df):
    """
    Calcula indicadores técnicos: RSI, MACD, Bollinger Bands.
    Requer DataFrame com coluna 'Close'.
    """
    if df is None or len(df) < 30 or 'Close' not in df.columns:
        return None
    
    try:
        # RSI (14 períodos)
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
        rs = gain / loss.replace(0, 0.0001)  # Evita divisão por zero
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD (12, 26, 9)
        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        
        # Bollinger Bands (20, 2)
        df['BB_Middle'] = df['Close'].rolling(window=20, min_periods=1).mean()
        std = df['Close'].rolling(window=20, min_periods=1).std()
        df['BB_Upper'] = df['BB_Middle'] + 2 * std
        df['BB_Lower'] = df['BB_Middle'] - 2 * std
        df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle']
        
        # SMAs para padrões
        df['SMA_20'] = df['Close'].rolling(window=20, min_periods=1).mean()
        df['SMA_50'] = df['Close'].rolling(window=50, min_periods=1).mean()
        
        return df
    except Exception as e:
        print(f"Erro ao calcular indicadores: {e}")
        return None

def detectar_padroes(df):
    """
    Detecta padrões técnicos relevantes: Golden Cross, Death Cross, RSI Reversal, etc.
    Retorna lista de padrões encontrados.
    """
    if df is None or len(df) < 5:
        return []
    
    padroes = []
    try:
        # RSI Oversold Bounce (< 30 voltando acima)
        if 'RSI' in df.columns and len(df) >= 3:
            rsi_atual = df['RSI'].iloc[-1]
            rsi_anterior = df['RSI'].iloc[-2]
            if rsi_anterior < 30 and rsi_atual > 30:
                padroes.append("📈 RSI REVERSAL")
            elif rsi_atual < 30:
                padroes.append("🟢 OVERSOLD")
            elif rsi_atual > 70:
                padroes.append("🔴 OVERBOUGHT")
        
        # MACD Crossover
        if 'MACD' in df.columns and 'MACD_Signal' in df.columns and len(df) >= 3:
            macd_atual = df['MACD'].iloc[-1]
            macd_sinal_atual = df['MACD_Signal'].iloc[-1]
            macd_anterior = df['MACD'].iloc[-2]
            macd_sinal_anterior = df['MACD_Signal'].iloc[-2]
            
            if macd_anterior < macd_sinal_anterior and macd_atual > macd_sinal_atual:
                padroes.append("🌟 MACD BULLISH CROSS")
            elif macd_anterior > macd_sinal_anterior and macd_atual < macd_sinal_atual:
                padroes.append("💀 MACD BEARISH CROSS")
        
        # Bollinger Squeeze (baixa volatilidade)
        if 'BB_Width' in df.columns and len(df) >= 20:
            bb_width_atual = df['BB_Width'].iloc[-1]
            bb_width_avg = df['BB_Width'].tail(20).mean()
            if bb_width_atual < bb_width_avg * 0.6:
                padroes.append("⚡ VOLATILITY SQUEEZE")
        
        # Preço tocando bandas
        if 'BB_Upper' in df.columns and 'BB_Lower' in df.columns:
            preco = df['Close'].iloc[-1]
            upper = df['BB_Upper'].iloc[-1]
            lower = df['BB_Lower'].iloc[-1]
            if preco >= upper * 0.98:
                padroes.append("📍 NEAR UPPER BB")
            elif preco <= lower * 1.02:
                padroes.append("📍 NEAR LOWER BB")
        
        # Golden Cross / Death Cross (SMA 20 vs SMA 50)
        if 'SMA_20' in df.columns and 'SMA_50' in df.columns and len(df) >= 3:
            sma20_atual = df['SMA_20'].iloc[-1]
            sma50_atual = df['SMA_50'].iloc[-1]
            sma20_anterior = df['SMA_20'].iloc[-2]
            sma50_anterior = df['SMA_50'].iloc[-2]
            
            if sma20_anterior < sma50_anterior and sma20_atual > sma50_atual:
                padroes.append("🌟 GOLDEN CROSS")
            elif sma20_anterior > sma50_anterior and sma20_atual < sma50_atual:
                padroes.append("💀 DEATH CROSS")
        
    except Exception as e:
        print(f"Erro ao detectar padrões: {e}")
    
    return padroes

def calcular_smart_score(indicadores, vol_ratio=1.0, price_momentum=0):
    """
    Calcula score inteligente 0-100 baseado em múltiplos critérios técnicos.
    """
    score = 50  # Base neutra
    
    try:
        # RSI Contribution (-25 a +25)
        rsi = indicadores.get('RSI', 50)
        if rsi < 30:
            score += 25  # Muito oversold = oportunidade
        elif rsi < 40:
            score += 15
        elif rsi > 70:
            score -= 25  # Overbought = risco
        elif rsi > 60:
            score -= 10
        
        # MACD Contribution (-15 a +20)
        macd = indicadores.get('MACD', 0)
        macd_signal = indicadores.get('MACD_Signal', 0)
        macd_hist = indicadores.get('MACD_Hist', 0)
        
        if macd > macd_signal:
            score += 15  # MACD bullish
            if macd_hist > 0 and indicadores.get('MACD_Hist_prev', 0) < 0:
                score += 5  # Acabou de cruzar
        else:
            score -= 10  # MACD bearish
        
        # Volume Contribution (-10 a +15)
        if vol_ratio > 2.5:
            score += 15  # Volume muito alto
        elif vol_ratio > 1.5:
            score += 10
        elif vol_ratio > 1.0:
            score += 5
        elif vol_ratio < 0.5:
            score -= 10  # Volume muito baixo
        
        # Momentum Contribution (-10 a +10)
        if price_momentum > 5:
            score += 10
        elif price_momentum > 0:
            score += 5
        elif price_momentum < -5:
            score -= 10
        
        # Bollinger Position (-10 a +15)
        bb_pos = indicadores.get('BB_Position', 'middle')
        if bb_pos == 'lower':
            score += 15  # Perto da banda inferior = oversold
        elif bb_pos == 'upper':
            score -= 10  # Perto da banda superior = overbought
        
        # Padrões Bonus/Penalty
        padroes = indicadores.get('padroes', [])
        for p in padroes:
            if 'GOLDEN CROSS' in p or 'RSI REVERSAL' in p or 'MACD BULLISH' in p:
                score += 10
            elif 'DEATH CROSS' in p or 'MACD BEARISH' in p:
                score -= 10
            elif 'OVERSOLD' in p:
                score += 5
            elif 'OVERBOUGHT' in p:
                score -= 5
        
    except Exception as e:
        print(f"Erro ao calcular smart score: {e}")
    
    return max(0, min(100, score))

def extrair_indicadores_resumo(df):
    """Extrai valores atuais dos indicadores para exibição."""
    if df is None or len(df) < 1:
        return {}
    
    try:
        ultimo = df.iloc[-1]
        preco = ultimo.get('Close', 0)
        
        # Posição Bollinger
        bb_pos = 'middle'
        if 'BB_Upper' in df.columns and 'BB_Lower' in df.columns:
            if preco >= ultimo.get('BB_Upper', preco) * 0.98:
                bb_pos = 'upper'
            elif preco <= ultimo.get('BB_Lower', preco) * 1.02:
                bb_pos = 'lower'
        
        return {
            'RSI': ultimo.get('RSI', 50),
            'MACD': ultimo.get('MACD', 0),
            'MACD_Signal': ultimo.get('MACD_Signal', 0),
            'MACD_Hist': ultimo.get('MACD_Hist', 0),
            'MACD_Hist_prev': df['MACD_Hist'].iloc[-2] if 'MACD_Hist' in df.columns and len(df) > 1 else 0,
            'BB_Upper': ultimo.get('BB_Upper', 0),
            'BB_Middle': ultimo.get('BB_Middle', 0),
            'BB_Lower': ultimo.get('BB_Lower', 0),
            'BB_Position': bb_pos,
            'SMA_20': ultimo.get('SMA_20', 0),
            'SMA_50': ultimo.get('SMA_50', 0),
            'Close': preco
        }
    except:
        return {}

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
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🎯 Scanner", "🔮 Gem Hunter", "⭐ Favoritos", "📈 Ambiente", 
    "🧮 Simulador", "🚨 Alertas", "📰 Notícias"
])

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
            hist = ticker.history(period="3mo", interval="1d")  # 3 meses para indicadores
            if hist.empty or len(hist) < 30: continue
            
            # Calcula indicadores técnicos
            hist = calcular_indicadores_tecnicos(hist)
            if hist is None: continue
            
            # Detecta padrões
            padroes = detectar_padroes(hist)
            
            # Extrai resumo dos indicadores
            indicadores = extrair_indicadores_resumo(hist)
            indicadores['padroes'] = padroes
            
            # Métricas básicas
            avg_volume = hist['Volume'].rolling(window=20).mean().iloc[-1]
            current_volume = hist['Volume'].iloc[-1]
            vol_ratio = current_volume / avg_volume if avg_volume > 0 else 0
            
            price_change_1d = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            price_change_5d = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5]) * 100 if len(hist) >= 5 else 0
            
            # Smart Score (0-100)
            smart_score = calcular_smart_score(indicadores, vol_ratio, price_change_5d)
            
            # Verifica threshold
            if vol_ratio >= vol_threshold:
                info = ticker.info
                candidatos.append({
                    'symbol': symbol, 
                    'name': info.get('shortName', symbol),
                    'price': hist['Close'].iloc[-1], 
                    'vol_ratio': vol_ratio,
                    'price_change': price_change_1d, 
                    'price_change_5d': price_change_5d,
                    'market_cap': info.get('marketCap', 0), 
                    'acima_sma': hist['Close'].iloc[-1] > hist['SMA_20'].iloc[-1],
                    # Novos campos inteligentes
                    'smart_score': smart_score,
                    'rsi': indicadores.get('RSI', 50),
                    'macd': indicadores.get('MACD', 0),
                    'macd_signal': indicadores.get('MACD_Signal', 0),
                    'bb_position': indicadores.get('BB_Position', 'middle'),
                    'padroes': padroes,
                    'momentum_score': min(4, len([p for p in padroes if 'BULLISH' in p or 'OVERSOLD' in p or 'GOLDEN' in p or 'RSI REVERSAL' in p])),
                    'url': f"https://finance.yahoo.com/quote/{symbol}"
                })
        except: continue
    
    # Ordena por Smart Score (mais inteligente que momentum)
    candidatos.sort(key=lambda x: x.get('smart_score', 0), reverse=True)
    return candidatos

# ============================================================================
# TAB 1: SCANNER
# ============================================================================
with tab1:
    st.title("🎯 Scanner")
    
    # ========== SNIPER MODE ==========
    with st.expander("🎯 **SNIPER MODE** - Detecção de Acumulação PRÉ-PUMP", expanded=False):
        st.caption("Detecta quando Smart Money está acumulando antes do preço explodir")
        
        # Importa módulos do sniper
        try:
            from sniper_logic import (
                check_accumulation_pattern_cex,
                check_liquidity_snipe,
                classify_alert
            )
            sniper_loaded = True
        except ImportError as e:
            st.error(f"❌ Erro ao carregar sniper: {e}")
            sniper_loaded = False
        
        if sniper_loaded:
            # Configurações
            col_sniper1, col_sniper2 = st.columns(2)
            with col_sniper1:
                sniper_vol_threshold = st.slider(
                    "📈 Volume Spike Mínimo", 
                    min_value=2.0, max_value=10.0, value=3.0, step=0.5,
                    help="Volume deve ser Xx acima da média 24h"
                )
            with col_sniper2:
                sniper_price_max = st.slider(
                    "💤 Variação Preço Máx (%)",
                    min_value=1.0, max_value=10.0, value=5.0, step=0.5,
                    help="Preço deve ter variado menos que X%"
                )
            
            # Pares para analisar
            sniper_pairs = st.multiselect(
                "🔍 Pares para Sniper",
                options=['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
                         'ADA/USDT', 'AVAX/USDT', 'DOGE/USDT', 'PEPE/USDT', 'WIF/USDT',
                         'BONK/USDT', 'ARB/USDT', 'OP/USDT', 'SUI/USDT', 'INJ/USDT'],
                default=['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'PEPE/USDT']
            )
            
            if st.button("🎯 Executar Sniper Scan", type="primary", key="sniper_scan"):
                with st.spinner("🔍 Analisando padrões de acumulação..."):
                    sniper_results = []
                    progress = st.progress(0)
                    
                    for i, pair in enumerate(sniper_pairs):
                        progress.progress((i + 1) / len(sniper_pairs))
                        result = check_accumulation_pattern_cex(
                            pair, 
                            volume_threshold=sniper_vol_threshold,
                            price_threshold=sniper_price_max
                        )
                        if result:
                            sniper_results.append(result)
                        time.sleep(0.3)
                    
                    progress.empty()
                    st.session_state.sniper_results = sniper_results
            
            # Exibe resultados
            if 'sniper_results' in st.session_state and st.session_state.sniper_results:
                results = st.session_state.sniper_results
                
                # Separa por status
                accumulating = [r for r in results if r.get('is_accumulating')]
                not_accumulating = [r for r in results if not r.get('is_accumulating')]
                
                if accumulating:
                    st.success(f"🔥 **{len(accumulating)} OPORTUNIDADES DETECTADAS!**")
                    for r in accumulating:
                        classification, emoji, action = classify_alert(r['confidence'])
                        with st.container():
                            st.markdown(f"""
**{emoji} {r['symbol']}** | Confiança: **{r['confidence']}%**
- 📈 Volume: **{r['volume_ratio']:.1f}x** acima da média
- 💲 Preço: **{r['price_change_pct']:+.2f}%**
                            """)
                            for signal in r.get('signals', []):
                                st.write(f"  • {signal}")
                            st.divider()
                else:
                    st.info("❄️ Nenhum padrão de acumulação detectado no momento")
                
                # Resumo de todos
                with st.expander("📊 Ver todos os pares analisados"):
                    for r in results:
                        status = "✅" if r.get('is_accumulating') else "⚪"
                        st.write(f"{status} **{r['symbol']}**: Vol {r['volume_ratio']:.2f}x, Preço {r['price_change_pct']:+.2f}%, Conf {r['confidence']}%")
            
            st.divider()
            st.caption("💡 **Para monitoramento 24/7**, rode: `python accumulation_daemon.py --daemon`")
    
    st.divider()
    
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
            cache_hits = 0
            for i, op in enumerate(raw_oportunidades[:15]):  # Aumentado para 15
                progress.progress((i + 1) / len(raw_oportunidades[:15]))
                
                # Gera chave única para cache
                symbol = op.get('symbol', op.get('baseToken', {}).get('symbol', 'unknown'))
                cache_key = f"{symbol}_{plataforma}"
                
                # Verifica cache existente e válido
                cached = st.session_state.ia_cache.get(cache_key)
                if cached:
                    cache_age = datetime.now() - cached.get('timestamp', datetime.min)
                    if cache_age < timedelta(minutes=IA_CACHE_TTL_MINUTES):
                        # Usa resultado do cache
                        op['ia_veredito'] = f"📦 {cached['response']}"
                        op['ia_score'] = cached['score']
                        op['ia_forca'] = cached['forca']
                        op['cached'] = True
                        analisados.append(op)
                        cache_hits += 1
                        continue
                
                try:
                    # Monta texto do ativo com dados relevantes
                    if "DexScreener" in plataforma:
                        liq = op.get('liquidity', 0) if isinstance(op.get('liquidity'), (int, float)) else op.get('liquidity', {}).get('usd', 0)
                        vol = op.get('vol_anomaly', 0)
                        txt = f"Token: {op.get('symbol', '?')}, Rede: {op.get('chain', '?')}, Liquidez: ${liq:,.0f}, Vol Anomaly: {vol:.1f}x, Motivo: {op.get('reason', 'N/A')[:100]}"
                    elif "Binance" in plataforma:
                        txt = f"Par: {op.get('symbol','?')}, Preço: ${op.get('price',0):,.4f}, Volume: {op.get('vol_ratio',0):.1f}x média, Volatilidade: {op.get('volatilidade',0):.2f}%"
                    else:
                        # Ações - Prompt aprimorado com indicadores técnicos
                        rsi = op.get('rsi', 50)
                        macd = op.get('macd', 0)
                        macd_signal = op.get('macd_signal', 0)
                        bb_pos = op.get('bb_position', 'middle')
                        padroes = op.get('padroes', [])
                        smart_score = op.get('smart_score', 50)
                        
                        # Status dos indicadores
                        rsi_status = 'SOBRECOMPRADO' if rsi > 70 else 'SOBREVENDIDO' if rsi < 30 else 'NEUTRO'
                        macd_dir = 'BULLISH' if macd > macd_signal else 'BEARISH'
                        bb_status = 'TOPO BOLLINGER' if bb_pos == 'upper' else 'FUNDO BOLLINGER' if bb_pos == 'lower' else 'MEIO DAS BANDAS'
                        
                        txt = f"""Ação: {op.get('symbol','?')}, Preço: ${op.get('price',0):,.2f}
📊 INDICADORES TÉCNICOS:
- RSI(14): {rsi:.1f} ({rsi_status})
- MACD: {macd:.4f} vs Sinal: {macd_signal:.4f} ({macd_dir})
- Bollinger: {bb_status}
- Volume: {op.get('vol_ratio',0):.1f}x média
- Variação 1D: {op.get('price_change',0):.2f}%, 5D: {op.get('price_change_5d',0):.2f}%
- Smart Score: {smart_score}/100
- Padrões: {', '.join(padroes) if padroes else 'Nenhum'}"""
                    
                    prompt = f"""Você é um analista quantitativo profissional. Analise este ativo:

{txt}

⚡ REGRAS DE DECISÃO:
- COMPRAR: RSI < 35 OU padrão bullish (Golden Cross, RSI Reversal, MACD Bullish) OU Smart Score > 70
- EVITAR: RSI > 70 OU padrão bearish (Death Cross, MACD Bearish) OU Smart Score < 30
- AGUARDAR: Sinais mistos ou neutros

Responda APENAS no formato:
[SINAL]: COMPRAR | AGUARDAR | EVITAR
[FORÇA]: 1-10 (baseado na convergência dos indicadores)
[MOTIVO]: máximo 20 palavras citando indicadores específicos
[RISCO]: BAIXO | MÉDIO | ALTO

Seja preciso e técnico."""
                    
                    response = client.models.generate_content(
                        model='gemini-3-flash-preview',
                        contents=prompt
                    )
                    veredito = response.text.strip()[:200]
                    
                    # Extrai força do sinal (1-10) da resposta
                    forca_match = re.search(r'\[FORÇA\]:\s*(\d+)', veredito, re.IGNORECASE)
                    forca = int(forca_match.group(1)) if forca_match else 5
                    forca = max(1, min(10, forca))  # Garante range 1-10
                    
                    # Classifica para ordenar baseado na força e no sinal
                    if "COMPRAR" in veredito.upper():
                        score = 100 + forca  # 101-110
                    elif "AGUARDAR" in veredito.upper():
                        score = 50 + forca   # 51-60
                    else:
                        score = forca         # 1-10
                    
                    # Salva no cache
                    st.session_state.ia_cache[cache_key] = {
                        'response': veredito,
                        'score': score,
                        'forca': forca,
                        'timestamp': datetime.now()
                    }
                    
                    op['ia_veredito'] = veredito
                    op['ia_score'] = score
                    op['ia_forca'] = forca
                    op['cached'] = False
                    analisados.append(op)
                except Exception as e:
                    op['ia_veredito'] = f"Erro: {str(e)[:30]}"
                    op['ia_score'] = 0
                    op['ia_forca'] = 0
                    analisados.append(op)
            
            # Ordena por score (melhores primeiro)
            analisados.sort(key=lambda x: x.get('ia_score', 0), reverse=True)
            st.session_state.oportunidades = analisados
            progress.empty()
        else:
            st.session_state.oportunidades = raw_oportunidades

    oportunidades = st.session_state.oportunidades
    if oportunidades:
        # Contagem de cache hits
        cached_count = sum(1 for op in oportunidades if op.get('cached', False))
        fresh_count = len(oportunidades) - cached_count
        
        col_stats1, col_stats2, col_stats3 = st.columns([2, 2, 1])
        with col_stats1:
            st.success(f"🎯 {len(oportunidades)} ativos analisados")
        with col_stats2:
            st.info(f"📦 Cache: {cached_count} | 🔄 Novos: {fresh_count} | TTL: {IA_CACHE_TTL_MINUTES}min")
        with col_stats3:
            if st.button("🗑️ Limpar Cache", help="Força nova análise IA"):
                st.session_state.ia_cache = {}
                st.session_state.oportunidades = []
                st.rerun()
        
        for idx, op in enumerate(oportunidades[:15]):
            symbol_display = op.get('baseToken', {}).get('symbol', op.get('symbol', 'N/A'))
            is_fav = is_favorito(op, plataforma)
            veredito = op.get('ia_veredito', '')
            score = op.get('ia_score', 0)
            forca = op.get('ia_forca', 0)
            
            # Emoji e cor baseado na força do sinal
            if forca >= 8:
                badge = "🟢"
                cor = "success"
            elif forca >= 5:
                badge = "🟡"
                cor = "warning"
            else:
                badge = "🔴"
                cor = "error"
            
            # Barra visual de força
            barra_cheia = "█" * forca
            barra_vazia = "░" * (10 - forca)
            barra_visual = f"{barra_cheia}{barra_vazia}"
            
            with st.expander(f"{badge} {'⭐' if is_fav else ''} **{symbol_display}** | Força: {forca}/10", expanded=(forca >= 8)):
                # Score visual em destaque
                st.markdown(f"### 📊 Força do Sinal: `{barra_visual}` **{forca}/10**")
                
                # Veredito da IA em destaque
                if veredito:
                    if cor == "success":
                        st.success(f"🧠 **{veredito}**")
                    elif cor == "warning":
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
                        # === STOCKS - Display com indicadores técnicos ===
                        st.write(f"**{op.get('name', op.get('symbol', 'N/A'))}** | ${op.get('price', 0):,.2f}")
                        
                        # Mini-cards com indicadores
                        ind_col1, ind_col2, ind_col3, ind_col4 = st.columns(4)
                        
                        with ind_col1:
                            rsi = op.get('rsi', 50)
                            rsi_icon = "🟢" if rsi < 40 else "🔴" if rsi > 60 else "🟡"
                            st.metric("RSI", f"{rsi:.0f}", delta=rsi_icon)
                        
                        with ind_col2:
                            macd = op.get('macd', 0)
                            macd_signal = op.get('macd_signal', 0)
                            macd_dir = "↗️ BULL" if macd > macd_signal else "↘️ BEAR"
                            st.metric("MACD", f"{macd:.4f}", delta=macd_dir)
                        
                        with ind_col3:
                            smart = op.get('smart_score', 50)
                            smart_icon = "🔥" if smart > 70 else "⚠️" if smart < 30 else "📊"
                            st.metric("Smart", f"{smart}/100", delta=smart_icon)
                        
                        with ind_col4:
                            vol = op.get('vol_ratio', 1)
                            vol_icon = "📈" if vol > 1.5 else "📉"
                            st.metric("Volume", f"{vol:.1f}x", delta=vol_icon)
                        
                        # Padrões detectados
                        padroes = op.get('padroes', [])
                        if padroes:
                            st.info(f"🎯 **Padrões:** {' | '.join(padroes)}")
                        
                        # Link
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
# TAB 2: GEM HUNTER (Scanner Algorítmico Avançado)
# ============================================================================
with tab2:
    st.title("🔮 Gem Hunter")
    st.caption("Scanner algorítmico: Gems + Notícias + Score de Oportunidade")
    
    # Importa módulos
    try:
        from gem_scanner import scan_coingecko_gems
        from news_hunter import fetch_crypto_news
        from brain_analyzer import generate_opportunity_signals, format_signal_alert
        modules_loaded = True
    except ImportError as e:
        st.error(f"❌ Erro ao carregar módulos: {e}")
        modules_loaded = False
    
    if modules_loaded:
        st.divider()
        
        # Filtros
        col_filter1, col_filter2, col_filter3 = st.columns(3)
        
        with col_filter1:
            max_mcap = st.number_input(
                "💰 Market Cap Máx ($)", 
                value=50_000_000, 
                min_value=1_000_000, 
                max_value=500_000_000,
                step=5_000_000,
                help="Moedas com market cap menor têm maior potencial de multiplicação"
            )
        
        with col_filter2:
            min_vol = st.number_input(
                "📊 Volume Mín 24h ($)", 
                value=500_000, 
                min_value=100_000, 
                max_value=10_000_000,
                step=100_000,
                help="Volume garante liquidez para entrada/saída"
            )
        
        with col_filter3:
            num_gems = st.slider("🔢 Quantidade", min_value=5, max_value=20, value=10)
        
        # Botão de scan
        if st.button("🚀 Iniciar Gem Hunter", type="primary", use_container_width=True):
            with st.spinner("🧠 Analisando mercado... (pode levar 30-60s)"):
                try:
                    # Gera sinais de oportunidade
                    opportunities = generate_opportunity_signals(
                        max_market_cap=max_mcap,
                        min_volume=min_vol,
                        gemini_api_key=api_key if api_key else None,
                        limit=num_gems
                    )
                    
                    st.session_state.gem_opportunities = opportunities
                    
                except Exception as e:
                    st.error(f"❌ Erro no scanner: {e}")
                    import traceback
                    st.code(traceback.format_exc())
        
        # Exibe resultados
        if 'gem_opportunities' in st.session_state and st.session_state.gem_opportunities:
            opportunities = st.session_state.gem_opportunities
            
            # Estatísticas
            hot_count = sum(1 for o in opportunities if o['classification'] == 'HOT')
            warm_count = sum(1 for o in opportunities if o['classification'] == 'WARM')
            cold_count = len(opportunities) - hot_count - warm_count
            
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            col_stat1.metric("🔮 Total", len(opportunities))
            col_stat2.metric("🔥 HOT", hot_count)
            col_stat3.metric("⚡ WARM", warm_count)
            col_stat4.metric("❄️ COLD", cold_count)
            
            st.divider()
            
            for i, opp in enumerate(opportunities):
                gem = opp.get('gem_data', {})
                classification = opp['classification']
                
                # Estilo baseado na classificação
                if classification == 'HOT':
                    expander_icon = "🔥"
                    expanded = True
                elif classification == 'WARM':
                    expander_icon = "⚡"
                    expanded = False
                else:
                    expander_icon = "❄️"
                    expanded = False
                
                with st.expander(
                    f"{expander_icon} **{opp['symbol']}** | Score: {opp['total_score']}/{opp['max_score']} | {classification}",
                    expanded=expanded
                ):
                    # Header com métricas
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("💰 Preço", f"${gem.get('price', 0):.6f}")
                    col2.metric("📊 MCap", f"${gem.get('market_cap', 0)/1_000_000:.1f}M")
                    col3.metric("📈 Vol 24h", f"${gem.get('volume_24h', 0)/1_000_000:.1f}M")
                    col4.metric("🔄 Var 24h", f"{gem.get('price_change_24h', 0):+.1f}%")
                    
                    # Barra de score visual
                    score_pct = (opp['total_score'] / opp['max_score']) * 100
                    st.progress(min(1.0, score_pct / 100), text=f"Score: {opp['total_score']:.1f}/{opp['max_score']}")
                    
                    # Fatores
                    if opp.get('explanations'):
                        st.markdown("**📋 Fatores identificados:**")
                        for exp in opp['explanations']:
                            st.write(f"• {exp}")
                    
                    # Notícias relacionadas
                    if opp.get('related_news'):
                        st.markdown("**📰 Notícias relacionadas:**")
                        for news in opp['related_news'][:3]:
                            st.write(f"• [{news.get('title', '')[:60]}...]({news.get('url', '#')})")
                    
                    # Ação recomendada
                    if classification == 'HOT':
                        st.success(f"⚡ **Ação:** {opp['action']}")
                    elif classification == 'WARM':
                        st.warning(f"👀 **Ação:** {opp['action']}")
                    else:
                        st.info(f"💭 **Ação:** {opp['action']}")
                    
                    # Botões de ação
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("⭐ Monitorar", key=f"gem_fav_{i}"):
                            # Adiciona aos favoritos
                            gem_fav = {
                                'symbol': gem.get('symbol', ''),
                                'name': gem.get('name', ''),
                                'price': gem.get('price', 0),
                                'market_cap': gem.get('market_cap', 0),
                                'volume_24h': gem.get('volume_24h', 0)
                            }
                            adicionar_favorito(gem_fav, "Cripto (CoinGecko)")
                            st.toast(f"⭐ {gem.get('symbol')} adicionado!")
                    
                    with col_b:
                        # Link CoinGecko
                        coin_id = gem.get('id', '')
                        if coin_id:
                            st.link_button("🔗 CoinGecko", f"https://www.coingecko.com/en/coins/{coin_id}")
        else:
            # Estado inicial
            st.info("👆 Clique em 'Iniciar Gem Hunter' para buscar oportunidades")
            
            with st.expander("ℹ️ Como funciona o Gem Hunter"):
                st.markdown("""
**🔮 Módulo A: Gem Scanner**
Busca moedas novas com Market Cap baixo e volume crescente via CoinGecko.

**📰 Módulo B: News Hunter**  
Monitora notícias de criptomoedas e detecta keywords de alto impacto.

**🧠 Módulo C: The Brain**
Cruza gems + notícias e calcula um Score de Oportunidade (0-20):

| Score | Classificação | Ação |
|-------|---------------|------|
| 15-20 | 🔥 HOT | Alerta imediato |
| 10-14 | ⚡ WARM | Monitorar |
| 0-9 | ❄️ COLD | Observar |
                """)

# ============================================================================
# TAB 3: FAVORITOS
# ============================================================================
with tab3:
    st.title("⭐ Favoritos Monitorados")
    
    if not st.session_state.favoritos:
        st.info("Nenhum favorito. Use o Scanner e clique ⭐ para monitorar!")
    else:
        st.success(f"📊 {len(st.session_state.favoritos)} ativos monitorados")
        st.caption("💡 Execute o monitor em segundo plano para receber alertas no Telegram")
        
        # Comando para iniciar o monitor e teste de Telegram
        with st.expander("📡 Configurar Alertas Telegram"):
            st.code("./.venv/bin/python MarketHunter/favorites_monitor.py", language="bash")
            st.write("Execute este comando em um terminal separado para receber alertas de COMPRA/VENDA no Telegram.")
            
            st.divider()
            
            # Verificar configuração do Telegram
            try:
                tg_token = st.secrets.get("telegram", {}).get("bot_token", "")
                tg_chat = st.secrets.get("telegram", {}).get("chat_id", "")
                
                if tg_token and tg_chat:
                    st.success(f"✅ Telegram configurado: Chat ID `{tg_chat[:6]}...`")
                    
                    if st.button("🧪 Testar Notificação Telegram", type="primary"):
                        with st.spinner("Enviando mensagem de teste..."):
                            try:
                                import requests
                                url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
                                payload = {
                                    "chat_id": tg_chat,
                                    "text": f"🦅 *MarketHunter Test*\n\nSua configuração de alertas está funcionando!\n\n⏰ {datetime.now().strftime('%H:%M:%S')}",
                                    "parse_mode": "Markdown"
                                }
                                response = requests.post(url, json=payload, timeout=10)
                                if response.status_code == 200:
                                    st.success("✅ Mensagem enviada! Verifique seu Telegram.")
                                else:
                                    st.error(f"❌ Erro: {response.text}")
                            except Exception as e:
                                st.error(f"❌ Erro ao enviar: {str(e)}")
                else:
                    st.warning("⚠️ Telegram não configurado!")
                    st.markdown("""
Configure no arquivo `secrets.toml`:
```toml
[telegram]
bot_token = "SEU_BOT_TOKEN"
chat_id = "SEU_CHAT_ID"
```

**Como obter:**
1. Crie um bot no [@BotFather](https://t.me/BotFather) e copie o token
2. Inicie conversa com seu bot
3. Acesse `https://api.telegram.org/bot<TOKEN>/getUpdates` para pegar o chat_id
                    """)
            except Exception as e:
                st.error(f"⚠️ Erro ao verificar configuração: {e}")
        
        for fav in st.session_state.favoritos:
            key = fav['key']
            dados = fav['data']
            plat = fav['plataforma']
            
            with st.expander(f"⭐ **{fav['symbol']}** - {fav['name']}", expanded=True):
                col_info, col_actions = st.columns([2, 1])
                
                with col_info:
                    st.caption(f"📍 {plat} | Adicionado: {fav['added_at']}")
                    if "DexScreener" in plat:
                        liq = dados.get('liquidity', 0)
                        liq_value = liq.get('usd', 0) if isinstance(liq, dict) else (liq if liq else 0)
                        st.write(f"Liquidez: ${liq_value:,.0f}")
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
with tab4:
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
with tab5:
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
# TAB 5: HISTÓRICO DE ALERTAS + DASHBOARD DE PERFORMANCE
# ============================================================================
with tab6:
    st.title("🚨 Dashboard de Alertas")
    
    # Inicializa tracking de outcomes na session_state
    if 'alert_outcomes' not in st.session_state:
        st.session_state.alert_outcomes = {}  # {alert_id: "acerto" | "erro"}
    
    alertas = carregar_alertas()
    
    if not alertas:
        st.info("Nenhum alerta ainda. Ative o monitor para receber alertas automáticos!")
    else:
        # ===== SEÇÃO DE PERFORMANCE =====
        st.subheader("📊 Performance dos Alertas")
        
        # Calcula métricas
        total_alertas = len(alertas)
        compras = [a for a in alertas if a.get('acao') == 'COMPRAR']
        vendas = [a for a in alertas if a.get('acao') == 'VENDER']
        aguardar = [a for a in alertas if a.get('acao') not in ['COMPRAR', 'VENDER']]
        
        # Outcomes
        outcomes = st.session_state.alert_outcomes
        acertos = sum(1 for v in outcomes.values() if v == 'acerto')
        erros = sum(1 for v in outcomes.values() if v == 'erro')
        total_avaliados = acertos + erros
        taxa_acerto = (acertos / total_avaliados * 100) if total_avaliados > 0 else 0
        
        # Métricas em cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📈 Total Alertas", total_alertas)
        with col2:
            st.metric("🟢 COMPRAR", len(compras))
        with col3:
            st.metric("🔴 VENDER", len(vendas))
        with col4:
            st.metric("🎯 Taxa Acerto", f"{taxa_acerto:.1f}%", 
                     delta=f"{acertos}/{total_avaliados} avaliados" if total_avaliados > 0 else "0 avaliados")
        
        # Barra de progresso visual para taxa de acerto
        if total_avaliados > 0:
            st.progress(taxa_acerto / 100)
            if taxa_acerto >= 70:
                st.success(f"🏆 Excelente taxa de acerto! {acertos} corretos de {total_avaliados}")
            elif taxa_acerto >= 50:
                st.warning(f"📊 Taxa moderada. {acertos} corretos de {total_avaliados}")
            else:
                st.error(f"⚠️ Taxa baixa. Revise sua estratégia. {acertos} corretos de {total_avaliados}")
        
        st.divider()
        
        # ===== HISTÓRICO COM AVALIAÇÃO =====
        st.subheader("📜 Histórico de Alertas")
        st.caption("💡 Marque os alertas como ✅ Acertou ou ❌ Errou para calcular sua taxa de acerto")
        
        for idx, alerta in enumerate(alertas[:30]):
            alert_id = f"{alerta.get('symbol')}_{alerta.get('timestamp', idx)}"
            acao = alerta.get('acao', '')
            symbol = alerta.get('symbol', 'N/A')
            mensagem = alerta.get('mensagem', '')[:100]
            outcome = outcomes.get(alert_id)
            
            # Escolhe cor baseada na ação
            if acao == "COMPRAR":
                color = "🟢"
                container_type = st.success
            elif acao == "VENDER":
                color = "🔴"
                container_type = st.error
            else:
                color = "🟡"
                container_type = st.info
            
            # Indicador de outcome
            if outcome == 'acerto':
                outcome_badge = "✅"
            elif outcome == 'erro':
                outcome_badge = "❌"
            else:
                outcome_badge = "⏳"
            
            with st.container():
                col_alert, col_outcome = st.columns([4, 1])
                
                with col_alert:
                    st.markdown(f"{color} {outcome_badge} **{symbol}** - {mensagem}...")
                
                with col_outcome:
                    if outcome is None:
                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            if st.button("✅", key=f"acerto_{alert_id}", help="Marcar como acerto"):
                                st.session_state.alert_outcomes[alert_id] = 'acerto'
                                st.rerun()
                        with btn_col2:
                            if st.button("❌", key=f"erro_{alert_id}", help="Marcar como erro"):
                                st.session_state.alert_outcomes[alert_id] = 'erro'
                                st.rerun()
                    else:
                        if st.button("↩️", key=f"reset_{alert_id}", help="Resetar avaliação"):
                            del st.session_state.alert_outcomes[alert_id]
                            st.rerun()

# ============================================================================
# TAB 6: NOTÍCIAS
# ============================================================================
with tab7:
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

