###############################################################################
# FILE: ai_risk_analyzer.py - Análise de Risco com IA (Gemini)
# 
# OBJETIVO:
# ---------
# Usar o Google Gemini para analisar oportunidades detectadas e dar uma
# "Nota de Risco" de 0 a 10, onde 10 = máximo risco de golpe.
#
# LÓGICA:
# -------
# A IA recebe dados numéricos da oportunidade (liquidez, volume, variação)
# e usa seu conhecimento para avaliar padrões suspeitos.
#
# INTEGRAÇÃO:
# -----------
# Chamar analisar_oportunidade_ia(dados) após detectar uma gem.
# A nota de risco será incluída na mensagem do Telegram.
###############################################################################

import os
import re
from typing import Dict, Optional, Tuple

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

# Prompt interno para a IA
RISK_ANALYSIS_PROMPT = """Você é um analista de risco de criptomoedas experiente.

Analise estes dados de uma oportunidade de trading e avalie o RISCO DE GOLPE (Rug Pull/Scam):

{dados}

REGRAS DE ANÁLISE:
1. Liquidez muito baixa (<$10K) = ALTO RISCO
2. Volume muito maior que liquidez (>10x) = SUSPEITO (possível wash trading)
3. Pump extremo (>100% em minutos) = ISCA de golpistas
4. Nome/símbolo com palavras como "Moon", "Elon", "Safe" = BANDEIRA VERMELHA
5. Par muito novo (<30 min) = EXTREMAMENTE ARRISCADO

Responda APENAS no formato:
[RISCO]: 0-10 (0=seguro, 10=golpe provável)
[MOTIVO]: máximo 15 palavras
[VEREDICTO]: SEGURO | MODERADO | PERIGOSO | GOLPE"""

# Cache para evitar chamadas repetidas
_risk_cache = {}


# ============================================================================
# FUNÇÃO PRINCIPAL
# ============================================================================

def analisar_oportunidade_ia(
    dados: Dict,
    api_key: Optional[str] = None
) -> Dict:
    """
    Analisa uma oportunidade com IA e retorna nota de risco.
    
    A IA avalia padrões suspeitos baseados em:
    - Liquidez vs Volume
    - Variação de preço
    - Nome/Símbolo suspeito
    - Idade do par
    
    Args:
        dados: Dict com dados da oportunidade (symbol, liquidity, volume, etc)
        api_key: API key do Gemini (opcional, usa variável de ambiente se não fornecido)
    
    Returns:
        Dict com risk_score (0-10), motivo, veredicto, e explicação
    """
    # Tenta obter API key
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY", "")
    
    if not api_key:
        return {
            'risk_score': 5,
            'motivo': 'API Gemini não configurada',
            'veredicto': 'DESCONHECIDO',
            'source': 'fallback'
        }
    
    # Verifica cache
    cache_key = f"{dados.get('symbol', '')}_{dados.get('pairAddress', '')}"
    if cache_key in _risk_cache:
        cached = _risk_cache[cache_key]
        cached['from_cache'] = True
        return cached
    
    try:
        from google import genai
        
        # Formata dados para o prompt
        dados_formatados = _formatar_dados_para_ia(dados)
        
        # Monta prompt completo
        prompt = RISK_ANALYSIS_PROMPT.format(dados=dados_formatados)
        
        # Chama Gemini
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        
        result_text = response.text.strip()
        
        # Parse da resposta
        result = _parse_risk_response(result_text)
        result['raw_response'] = result_text
        result['source'] = 'gemini'
        result['from_cache'] = False
        
        # Salva no cache
        _risk_cache[cache_key] = result
        
        return result
        
    except ImportError:
        return _analyze_risk_heuristic(dados)
    except Exception as e:
        print(f"❌ [AI Risk] Erro ao analisar: {e}")
        return _analyze_risk_heuristic(dados)


def _formatar_dados_para_ia(dados: Dict) -> str:
    """Formata dados da oportunidade para enviar à IA."""
    
    symbol = dados.get('symbol', 'N/A')
    name = dados.get('name', 'N/A')
    liquidity = dados.get('liquidity', dados.get('liquidity_usd', 0))
    volume = dados.get('vol_h1', dados.get('volume_24h', 0))
    price_change = dados.get('price_change_h1', dados.get('price_change_m5', 0))
    age_minutes = dados.get('pair_age_minutes', 999)
    safety_score = dados.get('safety_score', dados.get('gem_score', 0))
    
    return f"""
DADOS DA OPORTUNIDADE:
- Símbolo: {symbol}
- Nome: {name}
- Liquidez: ${liquidity:,.0f} USD
- Volume 1h: ${volume:,.0f} USD
- Variação Preço: {price_change:+.2f}%
- Idade do Par: {age_minutes:.0f} minutos
- Score de Segurança: {safety_score}/100
"""


def _parse_risk_response(response: str) -> Dict:
    """Parse da resposta da IA para extrair risco, motivo e veredicto."""
    
    result = {
        'risk_score': 5,
        'motivo': 'Não foi possível analisar',
        'veredicto': 'DESCONHECIDO'
    }
    
    # Extrai RISCO (0-10)
    risk_match = re.search(r'\[RISCO\]:\s*(\d+)', response, re.IGNORECASE)
    if risk_match:
        result['risk_score'] = min(10, max(0, int(risk_match.group(1))))
    
    # Extrai MOTIVO
    motivo_match = re.search(r'\[MOTIVO\]:\s*(.+?)(?:\n|\[|$)', response, re.IGNORECASE)
    if motivo_match:
        result['motivo'] = motivo_match.group(1).strip()[:100]
    
    # Extrai VEREDICTO
    veredicto_match = re.search(r'\[VEREDICTO\]:\s*(\w+)', response, re.IGNORECASE)
    if veredicto_match:
        result['veredicto'] = veredicto_match.group(1).upper()
    
    return result


def _analyze_risk_heuristic(dados: Dict) -> Dict:
    """
    Análise de risco usando heurísticas (fallback quando IA não disponível).
    """
    risk_score = 0
    motivos = []
    
    liquidity = dados.get('liquidity', dados.get('liquidity_usd', 0))
    volume = dados.get('vol_h1', dados.get('volume_24h', 0))
    price_change = dados.get('price_change_h1', dados.get('price_change_m5', 0))
    age_minutes = dados.get('pair_age_minutes', 999)
    symbol = dados.get('symbol', '').lower()
    name = dados.get('name', '').lower()
    
    # Regra 1: Liquidez baixa
    if liquidity < 5000:
        risk_score += 3
        motivos.append("Liquidez muito baixa")
    elif liquidity < 10000:
        risk_score += 1
    
    # Regra 2: Volume vs Liquidez suspeito
    if liquidity > 0 and volume > liquidity * 10:
        risk_score += 2
        motivos.append("Volume/liquidez suspeito")
    
    # Regra 3: Pump extremo
    if abs(price_change) > 100:
        risk_score += 2
        motivos.append("Pump extremo detectado")
    
    # Regra 4: Idade muito nova
    if age_minutes < 10:
        risk_score += 2
        motivos.append("Par muito novo")
    elif age_minutes < 30:
        risk_score += 1
    
    # Regra 5: Nome suspeito
    red_flags = ['moon', 'elon', 'safe', 'inu', 'shib', 'pepe', 'doge', '100x', '1000x']
    for flag in red_flags:
        if flag in symbol or flag in name:
            risk_score += 1
            motivos.append(f"Nome suspeito: {flag}")
            break
    
    risk_score = min(10, risk_score)
    
    if risk_score >= 8:
        veredicto = "GOLPE"
    elif risk_score >= 5:
        veredicto = "PERIGOSO"
    elif risk_score >= 3:
        veredicto = "MODERADO"
    else:
        veredicto = "SEGURO"
    
    return {
        'risk_score': risk_score,
        'motivo': "; ".join(motivos) if motivos else "Parece legítimo",
        'veredicto': veredicto,
        'source': 'heuristic'
    }


# ============================================================================
# FORMATAÇÃO PARA TELEGRAM
# ============================================================================

def format_risk_for_telegram(risk_result: Dict) -> str:
    """
    Formata a análise de risco para incluir na mensagem do Telegram.
    
    Returns:
        String formatada para Markdown
    """
    score = risk_result.get('risk_score', 5)
    motivo = risk_result.get('motivo', '')
    veredicto = risk_result.get('veredicto', 'DESCONHECIDO')
    
    # Emoji baseado no score
    if score <= 2:
        emoji = "🟢"
    elif score <= 4:
        emoji = "🟡"
    elif score <= 6:
        emoji = "🟠"
    else:
        emoji = "🔴"
    
    # Barra visual
    filled = "█" * score
    empty = "░" * (10 - score)
    bar = f"{filled}{empty}"
    
    return f"""
🤖 *Análise de Risco IA*
{emoji} *Risco:* {score}/10 `{bar}`
📋 *Veredicto:* {veredicto}
💬 *Motivo:* {motivo}
"""


# ============================================================================
# CLEAR CACHE
# ============================================================================

def clear_risk_cache():
    """Limpa o cache de análises."""
    global _risk_cache
    _risk_cache = {}


# ============================================================================
# TESTE STANDALONE
# ============================================================================

if __name__ == "__main__":
    print("🤖 AI RISK ANALYZER - Teste")
    print("=" * 50)
    
    # Teste com dados fictícios
    test_data = {
        'symbol': 'TESTCOIN',
        'name': 'Test Coin',
        'liquidity': 25000,
        'vol_h1': 50000,
        'price_change_h1': 15.5,
        'pair_age_minutes': 45
    }
    
    print("\nDados de teste:")
    for k, v in test_data.items():
        print(f"   {k}: {v}")
    
    print("\nAnalisando com heurísticas...")
    result = _analyze_risk_heuristic(test_data)
    
    print(f"\n📊 Resultado:")
    print(f"   Risco: {result['risk_score']}/10")
    print(f"   Veredicto: {result['veredicto']}")
    print(f"   Motivo: {result['motivo']}")
    
    print("\n" + format_risk_for_telegram(result))
