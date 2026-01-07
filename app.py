import streamlit as st
import pandas as pd
import requests
import json
import os
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Robô Investidor Pro 4.0", layout="wide")
ARQUIVO_DADOS = 'minha_carteira.json'

# --- DADOS DAS CARTEIRAS RECOMENDADAS ---
CARTEIRAS_RICO = {
    "Carteira Dividendos (Ações)": {
        "CURY3": 10, "CXSE3": 10, "DIRR3": 10, "ITSA4": 10, 
        "ITUB4": 10, "PETR4": 10, "POMO4": 10, "RECV3": 10, "VALE3": 10
    },
    "Carteira FIIs (Renda Mensal)": {
        "XPML11": 10, "RBRR11": 10, "RBRX11": 9, "XPCI11": 9,
        "BTLG11": 6, "LVBI11": 6, "PCIP11": 6, "PVBI11": 6,
        "KNCR11": 5, "BRCO11": 5, "XPLG11": 4, "KNSC11": 1
    }
}

# --- FUNÇÕES DE BANCO DE DADOS ---
def carregar_carteira():
    if os.path.exists(ARQUIVO_DADOS):
        with open(ARQUIVO_DADOS, 'r') as f:
            dados = json.load(f)
            # Migração automática: Garante que o campo 'pm' (Preço Médio) exista
            for ticker in dados:
                if 'pm' not in dados[ticker]:
                    dados[ticker]['pm'] = 0.0
            return dados
    else:
        return {}

def salvar_carteira(dados):
    with open(ARQUIVO_DADOS, 'w') as f:
        json.dump(dados, f, indent=4)

# --- FUNÇÃO DE COTAÇÃO ---
def obter_preco_atual(ticker):
    if not ticker.endswith(".SA"):
        ticker = f"{ticker}.SA"
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    try:
        response = requests.get(url, headers=headers, timeout=3)
        if response.status_code == 200:
            dados = response.json()
            return float(dados['chart']['result'][0]['meta']['regularMarketPrice'])
    except:
        return 0.0
    return 0.0

# --- LÓGICA DE COMPRA INTELIGENTE ---
def calcular_compras_inteligentes(df, aporte):
    caixa_disponivel = aporte
    df = df.copy()
    df['comprar_qtd'] = 0
    df['custo_total'] = 0.0
    
    while caixa_disponivel > 0:
        patrimonio_simulado = (df['qtde'] * df['preco_atual']).sum() + \
                              (df['comprar_qtd'] * df['preco_atual']).sum() + \
                              caixa_disponivel
        
        df['valor_simulado'] = (df['qtde'] + df['comprar_qtd']) * df['preco_atual']
        df['pct_atual_simulado'] = (df['valor_simulado'] / patrimonio_simulado) * 100
        df['gap_pct'] = df['meta_pct'] - df['pct_atual_simulado']
        
        candidatos = df[df['preco_atual'] <= caixa_disponivel]
        if candidatos.empty: break
            
        candidatos_compra = candidatos[candidatos['gap_pct'] > 0]
        if candidatos_compra.empty: break
            
        melhor_ativo = candidatos_compra['gap_pct'].idxmax()
        preco = df.loc[melhor_ativo, 'preco_atual']
        
        df.loc[melhor_ativo, 'comprar_qtd'] += 1
        df.loc[melhor_ativo, 'custo_total'] += preco
        caixa_disponivel -= preco

    return df, caixa_disponivel

# --- INTERFACE ---
st.title("🤖 Robô Investidor Pro 4.0")
st.caption("Rentabilidade | Rebalanceamento | Exportação Excel")

carteira = carregar_carteira()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Carteira")
    
    # Seletor de Carteiras Prontas
    opcao_rec = st.selectbox("Importar Carteira:", ["Selecionar..."] + list(CARTEIRAS_RICO.keys()))
    if st.button("Aplicar Modelo"):
        if opcao_rec != "Selecionar...":
            novos_ativos = CARTEIRAS_RICO[opcao_rec]
            for ticker, meta in novos_ativos.items():
                if ticker not in carteira:
                    carteira[ticker] = {'qtde': 0, 'meta_pct': meta, 'pm': 0.0}
                else:
                    carteira[ticker]['meta_pct'] = meta
            salvar_carteira(carteira)
            st.rerun()

    st.divider()
    
    # Edição Manual com PREÇO MÉDIO
    st.subheader("Meus Ativos")
    
    ativos_remover = []
    mudou = False
    
    for ticker in list(carteira.keys()):
        with st.expander(f"{ticker}", expanded=False):
            # Quantidade e Meta
            c1, c2 = st.columns(2)
            nq = c1.number_input(f"Qtd", value=int(carteira[ticker]['qtde']), key=f"q_{ticker}", min_value=0)
            nm = c2.number_input(f"Meta %", value=int(carteira[ticker]['meta_pct']), key=f"m_{ticker}", min_value=0, max_value=100)
            
            # Preço Médio (NOVO)
            pm = st.number_input(f"Preço Médio (R$)", value=float(carteira[ticker].get('pm', 0.0)), key=f"pm_{ticker}", step=0.01, format="%.2f")
            
            if st.button("Remover", key=f"del_{ticker}"):
                ativos_remover.append(ticker)
                mudou = True
            
            if nq != carteira[ticker]['qtde'] or nm != carteira[ticker]['meta_pct'] or pm != carteira[ticker].get('pm', 0.0):
                carteira[ticker]['qtde'] = nq
                carteira[ticker]['meta_pct'] = nm
                carteira[ticker]['pm'] = pm
                mudou = True
    
    if ativos_remover:
        for t in ativos_remover: del carteira[t]
        salvar_carteira(carteira)
        st.rerun()
        
    if mudou: salvar_carteira(carteira)

    st.divider()
    novo = st.text_input("Novo Ticker (ex: WEGE3)")
    if st.button("Adicionar"):
        if novo:
            novo = novo.upper().strip().replace(".SA", "")
            if novo not in carteira:
                carteira[novo] = {'qtde': 0, 'meta_pct': 10, 'pm': 0.0}
                salvar_carteira(carteira)
                st.rerun()

# --- ÁREA PRINCIPAL ---
c_aporte, c_btn = st.columns([1, 2])
aporte = c_aporte.number_input("💰 Aporte (R$)", value=1000.00, step=100.0)
c_btn.write(""); c_btn.write("")
calcular = c_btn.button("🚀 Analisar Carteira", type="primary")

if calcular:
    if not carteira:
        st.warning("Carteira vazia!")
    else:
        with st.spinner("Conectando na B3..."):
            df = pd.DataFrame.from_dict(carteira, orient='index')
            
            # Cotações
            precos = {}
            prog = st.progress(0)
            for i, ticker in enumerate(df.index):
                precos[ticker] = obter_preco_atual(ticker)
                prog.progress((i+1)/len(df))
            prog.empty()
            
            df['preco_atual'] = df.index.map(precos)
            df = df[df['preco_atual'] > 0]
            
            if df.empty:
                st.error("Erro de conexão.")
            else:
                # 1. Cálculo de Rentabilidade
                df['total_atual'] = df['qtde'] * df['preco_atual']
                df['total_investido'] = df['qtde'] * df['pm']
                df['lucro_reais'] = df['total_atual'] - df['total_investido']
                df['lucro_pct'] = ((df['preco_atual'] / df['pm']) - 1) * 100
                df['lucro_pct'] = df['lucro_pct'].fillna(0.0) # Evita erro se PM for 0

                # 2. Algoritmo de Compra
                df_final, sobra = calcular_compras_inteligentes(df, aporte)
                custo_total = aporte - sobra
                patrimonio_total = df_final['total_atual'].sum()
                lucro_total = df_final['lucro_reais'].sum()

                # --- DASHBOARD ---
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Patrimônio", f"R$ {patrimonio_total:,.2f}")
                m2.metric("Lucro/Prejuízo Total", f"R$ {lucro_total:,.2f}", 
                          delta=f"{(lucro_total/patrimonio_total*100) if patrimonio_total > 0 else 0:.2f}%")
                m3.metric("Aporte Sugerido", f"R$ {custo_total:,.2f}")
                m4.metric("Sobra", f"R$ {sobra:,.2f}")
                
                st.divider()
                
                # --- TABELA DE RENTABILIDADE ---
                st.subheader("📈 Sua Performance")
                st.dataframe(
                    df_final[['qtde', 'pm', 'preco_atual', 'lucro_reais', 'lucro_pct']].sort_values('lucro_pct', ascending=False).style.format({
                        'pm': 'R$ {:.2f}', 'preco_atual': 'R$ {:.2f}', 
                        'lucro_reais': 'R$ {:.2f}', 'lucro_pct': '{:.2f}%'
                    }).applymap(lambda x: 'color: green' if x > 0 else 'color: red', subset=['lucro_reais', 'lucro_pct']),
                    use_container_width=True
                )

                st.divider()

                # --- LISTA DE COMPRAS + EXCEL ---
                compras = df_final[df_final['comprar_qtd'] > 0].sort_values('custo_total', ascending=False)
                
                if not compras.empty:
                    st.subheader("🛒 Lista de Compras")
                    st.dataframe(
                        compras[['preco_atual', 'meta_pct', 'comprar_qtd', 'custo_total']].style.format({
                            'preco_atual': 'R$ {:.2f}', 'custo_total': 'R$ {:.2f}', 'meta_pct': '{:.0f}%'
                        }), use_container_width=True
                    )
                    
                    # --- BOTÃO DE DOWNLOAD (NOVIDADE) ---
                    csv = compras[['preco_atual', 'comprar_qtd', 'custo_total']].to_csv().encode('utf-8')
                    st.download_button(
                        label="📥 Baixar Lista para Excel (CSV)",
                        data=csv,
                        file_name='minha_lista_compras.csv',
                        mime='text/csv',
                    )
                else:
                    st.success("Carteira equilibrada! Nenhuma compra necessária.")