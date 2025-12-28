###############################################################################
# FILE: dex_scanner.py - Scanner DexScreener com Escudo Anti-Golpe
# 
# LÓGICA FINANCEIRA - ESCUDO ANTI-GOLPE (RUG PULL PROTECTION):
# -------------------------------------------------------------
# O mercado cripto é repleto de golpes. Este scanner implementa filtros
# rigorosos para proteger contra as táticas mais comuns de scammers:
#
# 1. LIQUIDEZ MÍNIMA ($5,000):
#    - Golpistas geralmente criam pools com pouca liquidez
#    - Liquidez baixa = fácil manipulação de preço
#    - Exigimos $5K mínimo como barreira básica
#
# 2. VOLUME MÍNIMO ($10,000/hora):
#    - Projetos falsos têm pouco volume real
#    - Volume mínimo garante interesse genuíno
#    - Evita "wash trading" de baixo volume
#
# 3. VARIAÇÃO DE PREÇO MÁXIMA (<300% em 5min):
#    - Pumps extremos (>300% em minutos) são iscas
#    - Golpistas inflam preço para atrair vítimas
#    - Depois vendem tudo (dump) e somem
#
# 4. IDADE MÍNIMA DO PAR (>10 minutos):
#    - Pares muito novos são extremamente arriscados
#    - Primeiros 10min são caóticos e manipulados
#    - Aguardar estabilização inicial
#
# AVISO: Mesmo com esses filtros, NÃO há garantia contra golpes.
# Faça sempre sua própria pesquisa (DYOR) antes de investir.
###############################################################################

import requests
import json
import time
from datetime import datetime
from typing import List, Dict, Optional

# ============================================================================
# CONFIGURAÇÃO DE FILTROS ANTI-GOLPE
# ============================================================================

# Filtro 1: Liquidez Mínima
MIN_LIQUIDITY_USD = 5_000         # $5,000 USD mínimo de liquidez

# Filtro 2: Volume Mínimo por Hora
MIN_VOLUME_H1_USD = 10_000        # $10,000 USD mínimo de volume/hora

# Filtro 3: Variação de Preço Máxima
MAX_PRICE_CHANGE_M5 = 300         # Máximo 300% em 5 minutos (acima = isca)

# Filtro 4: Idade Mínima do Par
MIN_PAIR_AGE_MINUTES = 10         # Mínimo 10 minutos de existência

# Outros filtros
MAX_FDV_USD = 50_000_000          # FDV máximo (evitar grandes caps)
MAX_PRICE_CHANGE_H1 = 3.0         # Variação máxima 1h para detectar acumulação

# ============================================================================
# REDES SUPORTADAS
# ============================================================================

SUPPORTED_CHAINS = {
    "solana": {"name": "Solana", "icon": "☀️", "query": "solana"},
    "ethereum": {"name": "Ethereum", "icon": "⟠", "query": "ethereum"},
    "bsc": {"name": "BNB Chain", "icon": "🟡", "query": "bsc"},
    "arbitrum": {"name": "Arbitrum", "icon": "🔵", "query": "arbitrum"},
    "base": {"name": "Base", "icon": "🔷", "query": "base"},
    "polygon": {"name": "Polygon", "icon": "🟣", "query": "polygon"},
    "avalanche": {"name": "Avalanche", "icon": "🔺", "query": "avalanche"},
}


# ============================================================================
# FUNÇÃO PRINCIPAL DE SCAN
# ============================================================================

def scan_dexscreener(
    chain: str = "solana", 
    min_liquidity: int = MIN_LIQUIDITY_USD, 
    max_fdv: int = MAX_FDV_USD,
    min_volume_h1: int = MIN_VOLUME_H1_USD,
    max_price_change_m5: float = MAX_PRICE_CHANGE_M5,
    min_pair_age_minutes: int = MIN_PAIR_AGE_MINUTES
) -> List[Dict]:
    """
    Varre pares no DexScreener com ESCUDO ANTI-GOLPE ativado.
    
    Aplica 4 filtros de segurança rigorosos antes de alertar:
    1. Liquidez Mínima: $5,000 USD
    2. Volume Mínimo: $10,000 USD/hora
    3. Variação de Preço: Ignora >300% em 5 minutos (isca)
    4. Idade do Par: Ignora pares <10 minutos (muito arriscado)
    
    Além disso, aplica filtro de "Acumulação Silenciosa" para detectar gemas.
    
    Args:
        chain: Rede a ser escaneada (solana, ethereum, bsc, etc)
        min_liquidity: Liquidez mínima em USD
        max_fdv: FDV máximo em USD
        min_volume_h1: Volume mínimo por hora em USD
        max_price_change_m5: Variação máxima em 5 minutos (%)
        min_pair_age_minutes: Idade mínima do par em minutos
    
    Returns:
        Lista de oportunidades que passaram em TODOS os filtros
    """
    chain_info = SUPPORTED_CHAINS.get(chain, SUPPORTED_CHAINS["solana"])
    query = chain_info["query"]
    url = f"https://api.dexscreener.com/latest/dex/search?q={query}"
    
    # Estatísticas de filtragem
    stats = {
        'total_pairs': 0,
        'rejected_liquidity': 0,
        'rejected_volume': 0,
        'rejected_pump': 0,
        'rejected_age': 0,
        'rejected_fdv': 0,
        'passed_all': 0
    }
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            print(f"❌ Erro ao acessar DexScreener: {response.status_code}")
            return []
            
        data = response.json()
        pairs = data.get('pairs', [])
        opportunities = []
        
        stats['total_pairs'] = len(pairs)
        
        for pair in pairs:
            rejection_reasons = []
            
            # ================================================================
            # FILTRO 1: LIQUIDEZ MÍNIMA
            # Lógica: Golpistas criam pools com liquidez baixa para manipular
            # ================================================================
            liquidity = float(pair.get('liquidity', {}).get('usd', 0) or 0)
            
            if liquidity < min_liquidity:
                stats['rejected_liquidity'] += 1
                continue  # REJEITADO: Liquidez insuficiente
            
            # ================================================================
            # FILTRO 2: VOLUME MÍNIMO POR HORA
            # Lógica: Volume baixo = falta de interesse real ou wash trading
            # ================================================================
            vol_h1 = float(pair.get('volume', {}).get('h1', 0) or 0)
            
            if vol_h1 < min_volume_h1:
                stats['rejected_volume'] += 1
                continue  # REJEITADO: Volume insuficiente
            
            # ================================================================
            # FILTRO 3: VARIAÇÃO DE PREÇO EM 5 MINUTOS (PUMP DETECTION)
            # Lógica: Pump >300% em 5min é ISCA de golpistas
            # Eles inflam o preço para atrair vítimas, depois dump
            # ================================================================
            price_change_m5 = float(pair.get('priceChange', {}).get('m5', 0) or 0)
            
            if abs(price_change_m5) > max_price_change_m5:
                stats['rejected_pump'] += 1
                continue  # REJEITADO: Pump suspeitoso (possível isca)
            
            # ================================================================
            # FILTRO 4: IDADE MÍNIMA DO PAR
            # Lógica: Pares muito novos são caóticos e manipulados
            # Primeiros minutos = sniper bots e manipulação
            # ================================================================
            pair_created_at = pair.get('pairCreatedAt', 0)
            
            if pair_created_at:
                created_time = datetime.fromtimestamp(pair_created_at / 1000)
                age_minutes = (datetime.now() - created_time).total_seconds() / 60
                
                if age_minutes < min_pair_age_minutes:
                    stats['rejected_age'] += 1
                    continue  # REJEITADO: Par muito novo (arriscado)
            else:
                age_minutes = 999  # Desconhecido = assume antigo
            
            # ================================================================
            # FILTRO 5: FDV MÁXIMO (Opcional)
            # Lógica: FDV muito alto = menos potencial de multiplicação
            # ================================================================
            fdv = float(pair.get('fdv', 0) or 0)
            
            if fdv > max_fdv and fdv > 0:
                stats['rejected_fdv'] += 1
                continue  # REJEITADO: FDV muito alto
            
            # ================================================================
            # DETECÇÃO DE ACUMULAÇÃO SILENCIOSA
            # Volume alto + Preço estável = Smart Money comprando
            # ================================================================
            vol_h24 = float(pair.get('volume', {}).get('h24', 0) or 0)
            price_change_h1 = float(pair.get('priceChange', {}).get('h1', 0) or 0)
            
            # Média esperada de volume por hora
            avg_vol_h1 = vol_h24 / 24 if vol_h24 > 0 else 0
            
            if avg_vol_h1 == 0:
                continue
            
            # Ratio de anomalia de volume
            vol_anomaly_ratio = vol_h1 / avg_vol_h1
            
            # Preço estável durante acumulação?
            price_stability = abs(price_change_h1) < MAX_PRICE_CHANGE_H1
            
            # Critério final: Volume 3x+ E Preço estável
            if vol_anomaly_ratio > 3.0 and price_stability:
                stats['passed_all'] += 1
                
                # ============================================================
                # CALCULAR SAFETY SCORE (0-100)
                # Quanto mais seguro, maior o score
                # ============================================================
                safety_score = 0
                safety_flags = []
                
                # Liquidez alta = +25
                if liquidity >= 50_000:
                    safety_score += 25
                    safety_flags.append("💎 Liquidez alta")
                elif liquidity >= 10_000:
                    safety_score += 15
                    safety_flags.append("💧 Liquidez OK")
                else:
                    safety_score += 5
                
                # Volume alto = +25
                if vol_h1 >= 100_000:
                    safety_score += 25
                    safety_flags.append("📈 Volume muito alto")
                elif vol_h1 >= 30_000:
                    safety_score += 15
                    safety_flags.append("📊 Volume bom")
                else:
                    safety_score += 5
                
                # Par antigo = +25
                if age_minutes >= 60:
                    safety_score += 25
                    safety_flags.append("⏰ Par estabelecido")
                elif age_minutes >= 30:
                    safety_score += 15
                    safety_flags.append("🕐 Par maduro")
                else:
                    safety_score += 5
                    safety_flags.append("🆕 Par novo")
                
                # Sem pump extremo = +25
                if abs(price_change_m5) < 50:
                    safety_score += 25
                    safety_flags.append("💤 Preço estável")
                elif abs(price_change_m5) < 100:
                    safety_score += 15
                    safety_flags.append("🔄 Preço variante")
                else:
                    safety_score += 5
                    safety_flags.append("⚠️ Preço volátil")
                
                opportunities.append({
                    "chain": chain,
                    "chain_icon": chain_info["icon"],
                    "symbol": pair.get('baseToken', {}).get('symbol'),
                    "name": pair.get('baseToken', {}).get('name'),
                    "address": pair.get('baseToken', {}).get('address', ''),
                    "pairAddress": pair.get('pairAddress'),
                    "dex": pair.get('dexId'),
                    "url": pair.get('url'),
                    "liquidity": liquidity,
                    "fdv": fdv,
                    "vol_h1": vol_h1,
                    "vol_h24": vol_h24,
                    "vol_anomaly": vol_anomaly_ratio,
                    "price_change_m5": price_change_m5,
                    "price_change_h1": price_change_h1,
                    "pair_age_minutes": age_minutes,
                    "safety_score": safety_score,
                    "safety_flags": safety_flags,
                    "reason": f"Volume 1h (${vol_h1:,.0f}) é {vol_anomaly_ratio:.1f}x maior que a média, preço variou apenas {price_change_h1:.2f}%."
                })
        
        # Log de estatísticas
        if stats['total_pairs'] > 0:
            print(f"📊 [{chain}] Estatísticas de filtragem:")
            print(f"   Total: {stats['total_pairs']} pares")
            print(f"   ❌ Liquidez baixa: {stats['rejected_liquidity']}")
            print(f"   ❌ Volume baixo: {stats['rejected_volume']}")
            print(f"   ❌ Pump suspeito: {stats['rejected_pump']}")
            print(f"   ❌ Par muito novo: {stats['rejected_age']}")
            print(f"   ❌ FDV alto: {stats['rejected_fdv']}")
            print(f"   ✅ Aprovados: {stats['passed_all']}")
        
        # Ordena por safety_score
        opportunities.sort(key=lambda x: x.get('safety_score', 0), reverse=True)
        
        return opportunities
        
    except Exception as e:
        print(f"❌ Erro no scanner DexScreener ({chain}): {e}")
        return []


def scan_all_chains(
    min_liquidity: int = MIN_LIQUIDITY_USD, 
    max_fdv: int = MAX_FDV_USD,
    min_volume_h1: int = MIN_VOLUME_H1_USD
) -> List[Dict]:
    """
    Varre TODAS as redes suportadas com filtros anti-golpe.
    
    Returns:
        Lista combinada de gemas de todas as redes, ordenadas por safety_score
    """
    all_gems = []
    
    print("🛡️ ESCUDO ANTI-GOLPE ATIVADO!")
    print(f"   • Liquidez mín: ${min_liquidity:,}")
    print(f"   • Volume mín/h: ${min_volume_h1:,}")
    print(f"   • Pump máx 5min: {MAX_PRICE_CHANGE_M5}%")
    print(f"   • Idade mín: {MIN_PAIR_AGE_MINUTES} minutos")
    print("-" * 50)
    
    for chain_id in SUPPORTED_CHAINS.keys():
        gems = scan_dexscreener(
            chain_id, 
            min_liquidity=min_liquidity,
            max_fdv=max_fdv,
            min_volume_h1=min_volume_h1
        )
        all_gems.extend(gems)
        time.sleep(0.5)  # Rate limiting
    
    # Ordena globalmente por safety_score
    all_gems.sort(key=lambda x: x.get('safety_score', 0), reverse=True)
    
    return all_gems


# ============================================================================
# TESTE STANDALONE
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🔎 SCANNER DEX COM ESCUDO ANTI-GOLPE")
    print("=" * 60)
    print()
    print("🛡️ FILTROS DE SEGURANÇA:")
    print(f"   1️⃣ Liquidez Mínima: ${MIN_LIQUIDITY_USD:,}")
    print(f"   2️⃣ Volume Mínimo/h: ${MIN_VOLUME_H1_USD:,}")
    print(f"   3️⃣ Pump Máx 5min: {MAX_PRICE_CHANGE_M5}%")
    print(f"   4️⃣ Idade Mínima: {MIN_PAIR_AGE_MINUTES} minutos")
    print()
    
    for chain_id, chain_info in SUPPORTED_CHAINS.items():
        print(f"\n{chain_info['icon']} Buscando em {chain_info['name']}...")
        results = scan_dexscreener(chain_id)
        
        if results:
            print(f"  🎯 {len(results)} oportunidades SEGURAS encontradas!")
            for r in results[:3]:
                score = r.get('safety_score', 0)
                emoji = "🟢" if score >= 75 else "🟡" if score >= 50 else "🔴"
                print(f"    {emoji} {r['symbol']} | Safety: {score}/100 | Liq: ${r['liquidity']:,.0f}")
                for flag in r.get('safety_flags', []):
                    print(f"       • {flag}")
        else:
            print("  ❄️ Nenhuma oportunidade segura detectada.")
    
    print("\n" + "=" * 60)
    print("✅ Scan completo!")
