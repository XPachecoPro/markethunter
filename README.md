# 🦅 MarketHunter Pro

**Sistema de Análise de Mercado com IA** - Scanner multi-plataforma para detectar oportunidades em criptomoedas e ações.

![Python](https://img.shields.io/badge/Python-3.12+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.52-red)
![Supabase](https://img.shields.io/badge/Supabase-Database-green)
![Gemini AI](https://img.shields.io/badge/Gemini-AI%20Analysis-purple)

## ✨ Funcionalidades

- 🎯 **Scanner Multi-Plataforma**: DexScreener, Binance, Yahoo Finance
- 🧠 **Análise com IA**: Gemini 3-Flash analisa e classifica oportunidades
- ⭐ **Monitor de Favoritos**: Isolamento por usuário via banco relacional
- 📰 **Portal de Notícias**: Feeds em tempo real de crypto, ações e Brasil
- 🔐 **Autenticação**: Login/cadastro com Supabase
- 📱 **Alertas Telegram**: Notificações de compra/venda
- 🇧🇷 **Formatação Inteligente**: Telefone com DDI automático

## 🚀 Como Executar

### Pré-requisitos

- Python 3.12+
- Conta Supabase (opcional para persistência)

### Instalação

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/markethunter.git
cd markethunter

# Crie ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou .venv\Scripts\activate  # Windows

# Instale dependências
pip install -r requirements.txt

# Execute
cd MarketHunter
streamlit run app.py --server.port 8502
```

### Acesse

- **Local**: <http://localhost:8502>

## 📦 Estrutura do Projeto

```text
markethunter/
├── MarketHunter/
│   ├── app.py              # Dashboard principal
│   ├── auth.py             # Autenticação Supabase
│   ├── dex_scanner.py      # Scanner DexScreener
│   ├── binance_scanner.py  # Scanner Binance
│   ├── stock_scanner.py    # Scanner Ações
│   ├── news_fetcher.py     # Agregador de notícias
│   └── favorites_monitor.py # Monitor de alertas
├── requirements.txt
└── README.md
```

## 🔧 Configuração

### Variáveis de Ambiente (opcional)

```env
GEMINI_API_KEY=sua_chave_aqui
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua_anon_key
TELEGRAM_BOT_TOKEN=seu_bot_token
TELEGRAM_CHAT_ID=seu_chat_id
```

## 📊 Screenshots

| Scanner               | Favoritos              | Notícias            |
|-----------------------|------------------------|---------------------|
| Análise IA automática | Monitoramento contínuo | Feeds em tempo real |

## 🛠 Tecnologias

- **Frontend**: Streamlit
- **Backend**: Python
- **Database**: Supabase (PostgreSQL)
- **AI**: Google Gemini
- **APIs**: DexScreener, Binance, Yahoo Finance

## 📄 Licença

MIT License - Uso livre para fins pessoais e comerciais.

---

Desenvolvido com ❤️ por [@xpachecopro](https://github.com/xpachecopro)
