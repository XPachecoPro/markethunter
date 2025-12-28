###############################################################################
# FILE: auth.py - Sistema de Autenticação com Supabase
###############################################################################
import hashlib
from datetime import datetime
from supabase import create_client, Client

# Configurações do Supabase
SUPABASE_URL = "https://hqlcsdjipnaijqgtadcc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhxbGNzZGppcG5haWpxZ3RhZGNjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY4ODcwMTIsImV4cCI6MjA4MjQ2MzAxMn0.kE5cnqHN-7AOCfLIDVjnygro2gKuaTtYZnyzxjgThQA"

def get_supabase_client() -> Client:
    """Retorna cliente Supabase."""
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
