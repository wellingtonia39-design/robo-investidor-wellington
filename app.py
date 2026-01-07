import streamlit as st
import pandas as pd
import requests
import json
import os
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Robô Investidor Pro 5.2", layout="wide", page_icon="📡")
ARQUIVO_DADOS = 'minha_carteira.json'

# --- SENHA DE ACESSO ---
SENHA_SECRETA = "123456"

# --- CARTEIRAS RECOMENDADAS ---
CARTEIRAS_PRONTAS = {
    "🏆 Carteira Recomendada IA (Equilíbrio Total)": {
        "WEGE3": 10, "ITUB4": 15, "VALE3": 10,  
        "TAEE11": 10, "PSSA3": 5,               
        "IVVB11": 20,                           
        "HGLG11": 10, "KNCR11": 10, "MXRF11": 10 
    },
    "Carteira Dividendos (Rico)": {
        "CURY3": 10, "CXSE3": 10, "DIRR3": 10, "ITSA4": 10, 
        "ITUB4": 10, "PETR4": 10, "POMO4": 10, "RECV3": 10, "VALE3": 10
    },
    "Carteira FIIs (Rico)": {
        "XPML11": 10, "RBRR11": 10, "RBRX11": 9, "XPCI11": 9,
        "BTLG11": 6, "LVBI11": 6, "PCIP11": 6, "PVBI11": 6,
        "KNCR11": 5, "BRCO11": 5, "XPLG11": 4, "KNSC11": 1
    }
}

# --- SISTEMA DE LOGIN ---
def check_password():
    if 'logado' not in st.session_state:
        st.session_state['logado'] = False
    
    if st.session_state['logado']:
        return True
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("## 🔐 Acesso Restrito")
        senha = st.text_input("Digite a senha de acesso:", type="password")
        if st.button("Entrar", type="primary"):
            if senha == SENHA_SECRETA:
                st.session_state['logado'] = True
                st.rerun()
            else:
                st.error("Senha incorreta!")
    return False

# --- FUNÇÕES DE BANCO DE DADOS ---
def carregar_carteira():
    if os.path.exists(ARQUIVO_DADOS):
        try:
            with open(ARQUIVO_DADOS, 'r') as f:
                dados = json.load(f)
                for ticker in dados:
                    # Garante compatibilidade com versões antigas
                    if 'pm' not in dados[ticker]: dados[ticker]['pm'] = 0.0
                    if 'qtde' not in dados[ticker]: dados[ticker]['qtde'] = 0
                    if 'meta_pct' not in dados[ticker]: dados[ticker]['meta_pct'] = 0
                return dados
        except:
            return {}
    else:
        return {}

def salvar_carteira(dados):
    with open(ARQUIVO_DADOS, 'w') as f:
        json.dump(dados, f, indent=4)

# --- COTAÇÃO ---
def obter_preco_atual(ticker):
    if not ticker.endswith(".SA"): ticker = f"{ticker}.SA"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        r = requests.get(url, headers=headers, timeout=3)
        if r.status_code == 200:
            return float(r.json()['chart']['result'][0]['meta']['regularMarketPrice'])
    except: return 0.0
    return 0.0

# --- CÁLCULO INTELIGENTE ---
def calcular_compras(df, aporte):
    caixa = aporte
    df = df.copy()
    df['comprar_qtd'] = 0
    df['custo_total'] = 0.0
    
    if df['meta_pct'].sum() == 0: return df, caixa

    while caixa > 0:
        patrimonio_sim = (df['qtde'] * df['preco_atual']).sum() + \
                         (df['comprar_qtd'] * df['preco_atual']).sum() + caixa
        
        if patrimonio_sim == 0: break

        df['pct_sim'] = ((df['qtde'] + df['comprar_qtd']) * df['preco_atual'] / patrimonio_sim) * 100
        df['gap'] = df['meta_pct'] - df['pct_sim']
        
        candidatos = df[(df['preco_atual'] <= caixa) & (df['gap'] > 0)]
        if candidatos.empty: break
            
        melhor = candidatos['gap'].idxmax()
        preco = df.loc[melhor, 'preco_atual']
        
        df.loc[melhor, 'comprar_qtd'] += 1
        df.loc[melhor, 'custo_total'] += preco
        caixa -= preco
        
    return df, caixa

# ==========================================
#      INÍCIO DO APP
# ==========================================

if check_password():
    st.title("🤖 Robô Investidor Pro 5.2")
    st.caption(f"Usuário Logado | Acesso Seguro | Atualização Automática")

    carteira = carregar_carteira()

    # --- BARRA LATERAL ---
    with st.sidebar:
        st.header("⚙️ Gestão")
        if st.button("🔒 Sair / Logout"):
            st.session_state['logado'] = False
            st.rerun()
            
        st.divider()
        st.subheader("Importar Estratégia")
        modelo = st.selectbox("Escolha um modelo:", ["Selecionar..."] + list(CARTEIRAS_PRONTAS.keys()))
        
        if st.button("Aplicar Modelo"):
            if modelo != "Selecionar...":
                novos = CARTEIRAS_PRONTAS[modelo]
                for t, m in novos.items():
                    if t not in carteira: 
                        carteira[t] = {'qtde': 0, 'meta_pct': m, 'pm': 0.0}
                    else: 
                        carteira[t]['meta_pct'] = m
                salvar_carteira(carteira)
                st.toast(f"Estratégia {modelo} aplicada!")
                time.sleep(1)
                st.rerun()

        st.divider()
        st.subheader("Meus Ativos")
        remover = []
        mudou = False
        
        if not carteira: st.info("Nenhum ativo cadastrado.")

        for t in list(carteira.keys()):
            with st.expander(t, expanded=False):
                c1, c2 = st.columns(2)
                nq = c1.number_input(f"Qtd", value=int(carteira[t]['qtde']), min_value=0, step=1, key=f"q_{t}")
                nm = c2.number_input(f"Meta %", value=int(carteira[t]['meta_pct']), min_value=0, max_value=100, step=1, key=f"m_{t}")
                pm = st.number_input(f"PM (R$)", value=float(carteira[t].get('pm', 0.0)), min_value=0.0, step=0.01, format="%.2f", key=f"p_{t}")
                
                if st.button("Excluir", key=f"d_{t}"): 
                    remover.append(t); mudou = True
                
                if nq!=carteira[t]['qtde'] or nm!=carteira[t]['meta_pct'] or pm!=carteira[t].get('pm',0.0):
                    carteira[t].update({'qtde':nq, 'meta_pct':nm, 'pm':pm})
                    mudou = True
        
        if remover:
            for t in remover: del carteira[t]
            salvar_carteira(carteira)
            st.rerun()
        if mudou: salvar_carteira(carteira)

        st.divider()
        add = st.text_input("Novo Ativo (ex: AAPL34)")
        if st.button("Adicionar"):
            if add:
                t = add.upper().strip().replace(".SA","")
                if t not in carteira: 
                    carteira[t] = {'qtde':0, 'meta_pct':10, 'pm':0.0}
                    salvar_carteira(carteira)
                    st.rerun()
        
        # --- MODO LIVE ---
        st.divider()
        modo_live = st.toggle("🔄 Modo Live (Atualizar a cada 60s)")

    # --- CORPO PRINCIPAL ---
    c1, c2 = st.columns([1, 2])
    aporte = c1.number_input("💰 Aporte (R$)", value=1000.00, step=100.0)
    c2.write(""); c2.write("")
    
    # Se estiver no modo live, o botão fica 'desabilitado' visualmente pois roda sozinho,
    # mas mantemos a funcionalidade manual também.
    executar = c2.button("🚀 Analisar Carteira", type="primary")

    # O código roda se apertar o botão OU se o modo live estiver ligado
    if executar or modo_live:
        if not carteira: 
            st.warning("Carteira vazia! Adicione ativos na barra lateral.")
        else:
            with st.spinner("Consultando Mercado..."):
                df = pd.DataFrame.from_dict(carteira, orient='index')
                precos = {}
                
                # Barra de progresso só aparece se for manual (pra não ficar piscando no live)
                if not modo_live:
                    bar = st.progress(0)
                
                for i, t in enumerate(df.index):
                    precos[t] = obter_preco_atual(t)
                    if not modo_live: bar.progress((i+1)/len(df))
                
                if not modo_live: bar.empty()
                
                df['preco_atual'] = df.index.map(precos)
                df = df[df['preco_atual'] > 0]
                
                if df.empty: 
                    st.error("Erro ao obter cotações. Verifique conexão.")
                else:
                    # Lógica Financeira
                    df['total_atual'] = df['qtde'] * df['preco_atual']
                    df['total_inv'] = df['qtde'] * df['pm']
                    df['lucro_rs'] = df['total_atual'] - df['total_inv']
                    
                    df['lucro_pct'] = df.apply(
                        lambda x: ((x['preco_atual']/x['pm'])-1)*100 if x['pm'] > 0 else 0.0, axis=1
                    )
                    
                    df_fim, sobra = calcular_compras(df, aporte)
                    
                    # Dashboard
                    patr = df_fim['total_atual'].sum()
                    lucro = df_fim['lucro_rs'].sum()
                    custo_compra = aporte - sobra
                    
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Patrimônio", f"R$ {patr:,.2f}")
                    m2.metric("Lucro Total", f"R$ {lucro:,.2f}", 
                              delta=f"{(lucro/patr*100) if patr>0 else 0:.1f}%")
                    m3.metric("Investimento", f"R$ {custo_compra:,.2f}")
                    m4.metric("Sobra", f"R$ {sobra:,.2f}")
                    
                    st.divider()
                    
                    # Performance
                    st.subheader("📈 Performance por Ativo")
                    st.dataframe(df_fim[['qtde','pm','preco_atual','lucro_rs','lucro_pct']]
                                 .sort_values('lucro_pct', ascending=False)
                                 .style.format({'pm':'R$ {:.2f}','preco_atual':'R$ {:.2f}','lucro_rs':'R$ {:.2f}','lucro_pct':'{:.1f}%'})
                                 .applymap(lambda x: 'color: green' if x>0 else 'color: red', subset=['lucro_rs','lucro_pct']), 
                                 use_container_width=True)
                    
                    st.divider()
                    
                    # Compras
                    compras = df_fim[df_fim['comprar_qtd']>0].sort_values('custo_total', ascending=False)
                    if not compras.empty:
                        st.subheader("🛒 Lista de Compras Recomendada")
                        st.dataframe(compras[['preco_atual','meta_pct','comprar_qtd','custo_total']]
                                     .style.format({'preco_atual':'R$ {:.2f}','custo_total':'R$ {:.2f}','meta_pct':'{:.0f}%'}),
                                     use_container_width=True)
                        
                        csv = compras[['preco_atual','comprar_qtd','custo_total']].to_csv().encode('utf-8')
                        st.download_button("📥 Baixar Excel (CSV)", csv, "compras.csv", "text/csv")
                    elif modo_live:
                         st.info("Monitorando mercado... Nenhuma oportunidade nova por enquanto.")
                    else:
                        st.success("Carteira Balanceada! Guarde o dinheiro.")

    # --- LOOP DO MODO LIVE ---
    if modo_live:
        time.sleep(60) # Espera 60 segundos
        st.rerun()     # Recarrega a página