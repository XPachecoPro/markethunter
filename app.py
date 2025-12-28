import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="MarketHunter Mobile", page_icon="🦅", layout="wide")

# --- CONEXÃO INTELIGENTE (HÍBRIDA) ---
@st.cache_data(ttl=60)
def carregar_dados_planilha():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        creds = None
        # TENTA MODO NUVEM (SECRETS)
        try:
            if "gcp_service_account" in st.secrets:
                creds_dict = st.secrets["gcp_service_account"]
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        except Exception:
            pass
        
        # TENTA MODO LOCAL (ARQUIVO)
        if creds is None:
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
            
        client = gspread.authorize(creds)
        sheet = client.open("MarketHunter_DB").sheet1
        data = sheet.get_all_records()
        return pd.DataFrame(data)

    except Exception as e:
        st.error(f"Erro de Conexão: {e}")
        return pd.DataFrame()

# --- INTERFACE MOBILE FIRST ---
st.title("🦅 MarketHunter")
st.caption("Monitoramento Cloud 24/7")

if st.button("🔄 Atualizar"):
    st.cache_data.clear()
    st.rerun()

df = carregar_dados_planilha()

if not df.empty:
    # Métricas compactas para celular
    col1, col2 = st.columns(2)
    col1.metric("Gemas", len(df))
    last_coin = df.iloc[-1]['Moeda'] if 'Moeda' in df.columns else "-"
    col2.metric("Última", last_coin)

    # Gráfico
    if 'Moeda' in df.columns and 'Preço' in df.columns:
        fig = px.bar(df, x='Moeda', y='Preço', title="Tendência")
        st.plotly_chart(fig, use_container_width=True)

    # Tabela (Dataframe)
    st.dataframe(df, use_container_width=True)
else:
    st.info("Aguardando dados do robô...")

st.markdown("---")
st.caption(f"Atualizado: {datetime.now().strftime('%H:%M')}")