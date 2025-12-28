import streamlit as st
import hashlib
from supabase import create_client, Client

# Configurações do Supabase (lendo de st.secrets para segurança)
try:
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
except:
    # Fallback para evitar erro imediato, mas pedirá configuração
    SUPABASE_URL = ""
    SUPABASE_KEY = ""

def get_supabase_client() -> Client:
    """Retorna cliente Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("⚠️ Configurações do Supabase não encontradas nos Secrets!")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def cadastrar_usuario(nome: str, email: str, password: str, telefone: str = ""):
    """Registra novo usuário no Supabase."""
    try:
        supabase = get_supabase_client()
        
        # Verifica se email já existe
        existing = supabase.table("users").select("email").eq("email", email).execute()
        if existing.data:
            return False, "Email já cadastrado!"
        
        # Insere novo usuário
        user_data = {
            "nome": nome,
            "email": email,
            "telefone": telefone,
            "password_hash": hash_password(password),
            "favoritos": [],
            "config": {}
        }
        
        result = supabase.table("users").insert(user_data).execute()
        
        if result.data:
            return True, "Cadastro realizado com sucesso!"
        else:
            return False, "Erro ao criar conta."
    
    except Exception as e:
        return False, f"Erro: {str(e)}"

def autenticar_usuario(email: str, password: str):
    """Autentica usuário pelo email e senha."""
    try:
        supabase = get_supabase_client()
        
        # Busca usuário pelo email
        result = supabase.table("users").select("*").eq("email", email).execute()
        
        if not result.data:
            return False, None, "Email não encontrado!"
        
        user = result.data[0]
        
        # Verifica senha
        if user["password_hash"] != hash_password(password):
            return False, None, "Senha incorreta!"
        
        return True, user, "Login realizado com sucesso!"
    
    except Exception as e:
        return False, None, f"Erro: {str(e)}"

def atualizar_usuario(email: str, dados: dict):
    """Atualiza dados do usuário."""
    try:
        supabase = get_supabase_client()
        result = supabase.table("users").update(dados).eq("email", email).execute()
        return bool(result.data)
    except:
        return False

# ============================================================================
# NOVAS FUNÇÕES RELACIONAIS (MULTI-USUÁRIO)
# ============================================================================

def buscar_favoritos_usuario(user_id: str):
    """Busca todos os favoritos de um usuário específico."""
    try:
        supabase = get_supabase_client()
        result = supabase.table("favorites").select("*").eq("user_id", user_id).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Erro ao buscar favoritos: {e}")
        return []

def adicionar_favorito_db(user_id: str, fav: dict):
    """Adiciona um favorito ao banco de dados relacional."""
    try:
        supabase = get_supabase_client()
        data = {
            "user_id": user_id,
            "asset_key": fav.get('key'),
            "symbol": fav.get('symbol'),
            "plataforma": fav.get('plataforma'),
            "asset_data": fav.get('data')
        }
        result = supabase.table("favorites").insert(data).execute()
        return bool(result.data)
    except Exception as e:
        print(f"Erro ao adicionar favorito: {e}")
        return False

def remover_favorito_db(user_id: str, asset_key: str):
    """Remove um favorito do banco de dados relacional."""
    try:
        supabase = get_supabase_client()
        result = supabase.table("favorites").delete().eq("user_id", user_id).eq("asset_key", asset_key).execute()
        return bool(result.data)
    except Exception as e:
        print(f"Erro ao remover favorito: {e}")
        return False

def buscar_alertas_usuario(user_id: str):
    """Busca alertas recentes de um usuário específico."""
    try:
        supabase = get_supabase_client()
        result = supabase.table("alerts").select("*").eq("user_id", user_id).order("timestamp", desc=True).limit(20).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Erro ao buscar alertas: {e}")
        return []

def salvar_alerta_db(user_id: str, alerta: dict):
    """Salva um alerta no banco de dados relacional."""
    try:
        supabase = get_supabase_client()
        data = {
            "user_id": user_id,
            "symbol": alerta.get('symbol'),
            "acao": alerta.get('acao'),
            "mensagem": alerta.get('mensagem')
        }
        result = supabase.table("alerts").insert(data).execute()
        return bool(result.data)
    except Exception as e:
        print(f"Erro ao salvar alerta: {e}")
        return False

def salvar_gema_db(gem: dict):
    """
    Salva uma gema identificada no banco de dados.
    Ignora duplicatas baseado no pair_address.
    """
    try:
        supabase = get_supabase_client()
        data = {
            "chain": gem.get('chain'),
            "symbol": gem.get('symbol'),
            "name": gem.get('name'),
            "pair_address": gem.get('pairAddress'),
            "liquidity": gem.get('liquidity'),
            "fdv": gem.get('fdv'),
            "vol_anomaly": gem.get('vol_anomaly'),
            "dex": gem.get('dex'),
            "url": gem.get('url'),
            "reason": gem.get('reason')
        }
        # Usa upsert para ignorar duplicatas
        result = supabase.table("gems").upsert(data, on_conflict="pair_address").execute()
        return bool(result.data)
    except Exception as e:
        print(f"Erro ao salvar gema: {e}")
        return False

def buscar_gemas_recentes(limit=50):
    """Busca as gemas mais recentes do banco de dados."""
    try:
        supabase = get_supabase_client()
        result = supabase.table("gems").select("*").order("discovered_at", desc=True).limit(limit).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Erro ao buscar gemas: {e}")
        return []

