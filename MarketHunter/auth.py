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

def salvar_favoritos_usuario(email: str, favoritos: list):
    """Salva favoritos do usuário no Supabase."""
    return atualizar_usuario(email, {"favoritos": favoritos})
