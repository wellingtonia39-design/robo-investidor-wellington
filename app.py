import streamlit as st
import pandas as pd
import requests
import json
import os
import time
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Robô Investidor Pro 7.0", layout="wide", page_icon="💰")
ARQUIVO_DADOS = 'minha_carteira.json'

# --- SENHA DE ACESSO ---
SENHA_SECRETA = "123456"

# --- MAPEAMENTO DE SETORES ---
SETORES = {
    "WEGE3": "Indústria", "VALE3": "Mineração", "PSSA3": "Seguros",
    "ITUB4": "Bancos", "ITSA4": "Bancos", "BBAS3": "Bancos",
    "TAEE11": "Elétrica", "CPLE6": "Elétrica", "EGIE3": "Elétrica",
    "IVVB11": "Dólar/Exterior", "BTLG11": "FII Logística",
    "HGLG11": "FII Logística", "KNCR11": "FII Papel",
    "MXRF11": "FII Híbrido", "XPML11": "FII Shopping",
    "PETR4": "Petróleo", "CURY3": "Construção", "CXSE3": "Seguros",
    "DIRR3": "Construção", "POMO4": "Indústria", "RECV3": "Petróleo"
}

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
    if 'logado' not in st.session_state: st.session_state['logado'] = False
    if st.session_state['logado']: return True
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("## 🔐 Acesso Restrito")
        senha = st.text_input("Digite a senha:", type="password")
        if st.button("Entrar", type="primary"):
            if senha == SENHA_SECRETA:
                st.session_state['logado'] = True; st.rerun()
            else: st.error("Senha incorreta!")
    return False

# --- FUNÇÕES DE DADOS ---
def carregar_carteira():
    if os.path.exists(ARQUIVO_DADOS):
        try:
            with open(ARQUIVO_DADOS, 'r') as f:
                dados = json.load(f)
                for t in dados:
                    if 'pm' not in dados[t]: dados[t]['pm'] = 0.0
                    if 'qtde' not in dados[t]: dados[t]['qtde'] = 0
                    if 'meta_pct' not in dados[t]: dados[t]['meta_pct'] = 0
                    if 'divs' not in dados[t]: dados[t]['divs'] = 0.0 # Novo Campo
                return dados
        except: return {}
    else: return {}

def salvar_carteira(dados):
    with open(ARQUIVO_DADOS, 'w') as f: json.dump(dados, f, indent=4)

def obter_setor(ticker):
    t_limpo = ticker.replace(".SA", "").strip()
    return SETORES.get(t_limpo, "Outros")

# --- COTAÇÃO ---
def obter_preco_atual(ticker):
    if not ticker.endswith(".SA"): ticker = f"{ticker}.SA"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers, timeout=3)
        if r.status_code == 200:
            return float(r.json()['chart']['result'][0]['meta']['regularMarketPrice'])
    except: return 0.0
    return 0.0

# --- CÁLCULO ---
def calcular_compras(df, aporte):
    caixa = aporte
    df = df.copy()
    df['comprar_qtd'] = 0
    df['custo_total'] = 0.0
    
    if df['meta_pct'].sum() == 0: return df, caixa

    while caixa > 0:
        patr_sim = (df['qtde']*df['preco_atual']).sum() + (df['comprar_qtd']*df['preco_atual']).sum() + caixa
        if patr_sim == 0: break

        df['pct_sim'] = ((df['qtde']+df['comprar_qtd'])*df['preco_atual']/patr_sim)*100
        df['gap'] = df['meta_pct'] - df['pct_sim']
        
        cand = df[(df['preco_atual'] <= caixa) & (df['gap'] > 0)]
        if cand.empty: break
            
        melhor = cand['gap'].idxmax()
        preco = df.loc[melhor, 'preco_atual']
        
        df.loc[melhor, 'comprar_qtd'] += 1
        df.loc[melhor, 'custo_total'] += preco
        caixa -= preco
    return df, caixa

# ==========================================
#      INÍCIO DO APP
# ==========================================

if check_password():
    st.title("🤖 Robô Investidor Pro 7.0")
    st.caption("Dividendos | Yield on Cost | Backup | Nubank")

    carteira = carregar_carteira()

    # --- BARRA LATERAL ---
    with st.sidebar:
        st.header("⚙️ Controle")
        if st.button("🔒 Logout"): st.session_state['logado'] = False; st.rerun()

        # BACKUP
        st.divider()
        with st.expander("💾 Backup e Modelos"):
            if os.path.exists(ARQUIVO_DADOS):
                with open(ARQUIVO_DADOS, "r") as f:
                    st.download_button("Baixar Dados (.json)", f, "carteira.json")
            
            modelo = st.selectbox("Carregar:", ["Selecionar..."] + list(CARTEIRAS_PRONTAS.keys()))
            if st.button("Aplicar"):
                if modelo != "Selecionar...":
                    novos = CARTEIRAS_PRONTAS[modelo]
                    for t, m in novos.items():
                        if t not in carteira: carteira[t] = {'qtde':0, 'meta_pct':m, 'pm':0.0, 'divs':0.0}
                        else: carteira[t]['meta_pct'] = m
                    salvar_carteira(carteira); st.rerun()

        st.divider()
        st.subheader("Meus Ativos (Edição)")
        remover = []; mudou = False
        if not carteira: st.info("Vazia.")
        
        for t in carteira:
            with st.expander(f"{t}"):
                c1, c2 = st.columns(2)
                nq = c1.number_input(f"Qtd", value=int(carteira[t]['qtde']), min_value=0, key=f"q_{t}")
                nm = c2.number_input(f"% Meta", value=int(carteira[t]['meta_pct']), key=f"m_{t}")
                pm = st.number_input(f"PM (R$)", value=float(carteira[t].get('pm',0.0)), step=0.01, format="%.2f", key=f"p_{t}")
                # NOVO CAMPO DE DIVIDENDOS
                dv = st.number_input(f"Div. Recebidos (R$)", value=float(carteira[t].get('divs',0.0)), step=0.01, format="%.2f", key=f"d_{t}", help="Total histórico recebido")
                
                if st.button("Excluir", key=f"del_{t}"): remover.append(t); mudou=True
                
                if nq!=carteira[t]['qtde'] or nm!=carteira[t]['meta_pct'] or pm!=carteira[t].get('pm',0.0) or dv!=carteira[t].get('divs',0.0):
                    carteira[t].update({'qtde':nq, 'meta_pct':nm, 'pm':pm, 'divs':dv})
                    mudou=True
        
        if remover:
            for t in remover: del carteira[t]
            salvar_carteira(carteira); st.rerun()
        if mudou: salvar_carteira(carteira)
        
        st.divider()
        add = st.text_input("Novo (ex: BBAS3)"); 
        if st.button("Add") and add:
            t = add.upper().strip().replace(".SA","")
            if t not in carteira: 
                carteira[t]={'qtde':0,'meta_pct':10,'pm':0.0,'divs':0.0}; salvar_carteira(carteira); st.rerun()
        
        st.divider()
        modo_live = st.toggle("🔄 Modo Live (60s)")

    # --- CORPO PRINCIPAL ---
    c1, c2 = st.columns([1, 2])
    aporte = c1.number_input("💰 Aporte Nubank (R$)", value=1000.00, step=100.0)
    c2.write(""); c2.write("")
    executar = c2.button("🚀 Analisar Carteira", type="primary")

    if executar or modo_live:
        if not carteira: st.warning("Adicione ativos!")
        else:
            with st.spinner("Calculando Rentabilidade..."):
                df = pd.DataFrame.from_dict(carteira, orient='index')
                precos = {}
                if not modo_live: bar = st.progress(0)
                
                for i, t in enumerate(df.index):
                    precos[t] = obter_preco_atual(t)
                    if not modo_live: bar.progress((i+1)/len(df))
                if not modo_live: bar.empty()
                
                df['preco_atual'] = df.index.map(precos)
                df = df[df['preco_atual'] > 0]
                
                if df.empty: st.error("Erro na conexão.")
                else:
                    # CÁLCULOS AVANÇADOS
                    df['total_atual'] = df['qtde'] * df['preco_atual']
                    df['total_inv'] = df['qtde'] * df['pm']
                    
                    # Lucro Apenas da Cota (Valorização)
                    df['lucro_cota'] = df['total_atual'] - df['total_inv']
                    
                    # Lucro Real (Cota + Dividendos)
                    df['lucro_real'] = df['lucro_cota'] + df['divs']
                    
                    # Rentabilidade % (Considerando Dividendos)
                    df['rentab_pct'] = df.apply(lambda x: (x['lucro_real']/x['total_inv'])*100 if x['total_inv']>0 else 0, axis=1)

                    # Yield on Cost (Quanto o dividendo representa do custo)
                    df['yoc_pct'] = df.apply(lambda x: (x['divs']/x['total_inv'])*100 if x['total_inv']>0 else 0, axis=1)
                    
                    df['setor'] = df.index.map(obter_setor)
                    df_fim, sobra = calcular_compras(df, aporte)
                    
                    # --- DASHBOARD ---
                    patr = df_fim['total_atual'].sum()
                    lucro_total = df_fim['lucro_real'].sum() # Agora soma divs
                    total_divs = df_fim['divs'].sum()
                    custo_compra = aporte - sobra
                    
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("Patrimônio Total", f"R$ {patr:,.2f}")
                    k2.metric("Lucro Real (com Divs)", f"R$ {lucro_total:,.2f}", delta=f"{(lucro_total/patr*100) if patr>0 else 0:.1f}%")
                    k3.metric("💰 Só Proventos", f"R$ {total_divs:,.2f}", delta="Já Recebidos")
                    k4.metric("Sugestão Aporte", f"R$ {custo_compra:,.2f}")
                    
                    st.divider()

                    # --- GRÁFICOS ---
                    g1, g2 = st.columns(2)
                    with g1:
                        st.caption("Distribuição por Ativo")
                        if patr > 0: st.plotly_chart(px.pie(df_fim, values='total_atual', names=df_fim.index, hole=0.4), use_container_width=True)
                    with g2:
                        st.caption("Distribuição por Setor")
                        if patr > 0:
                            df_setor = df_fim.groupby('setor')['total_atual'].sum().reset_index()
                            st.plotly_chart(px.pie(df_setor, values='total_atual', names='setor', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu), use_container_width=True)

                    st.divider()
                    
                    # --- LISTA DE COMPRAS ---
                    compras = df_fim[df_fim['comprar_qtd']>0].sort_values('custo_total', ascending=False)
                    if not compras.empty:
                        st.subheader("🛒 Lista de Compras (Ordem Nubank)")
                        st.dataframe(compras[['preco_atual','meta_pct','comprar_qtd','custo_total']]
                                     .style.format({'preco_atual':'R$ {:.2f}','custo_total':'R$ {:.2f}','meta_pct':'{:.0f}%'}),
                                     use_container_width=True)
                    elif modo_live: st.info("Monitorando...")
                    else: st.success("Carteira OK! Nada para comprar.")
                    
                    # --- TABELA DE RENTABILIDADE REAL ---
                    st.divider()
                    with st.expander("🔎 Ver Detalhes (Lucro Real + Yield on Cost)", expanded=True):
                        st.caption("YoC = Quanto o dividendo representa sobre o preço que você pagou.")
                        cols_mostrar = ['qtde','pm','preco_atual','divs','lucro_real','rentab_pct', 'yoc_pct']
                        st.dataframe(df_fim[cols_mostrar]
                                     .sort_values('rentab_pct', ascending=False)
                                     .style.format({
                                         'pm':'R$ {:.2f}',
                                         'preco_atual':'R$ {:.2f}',
                                         'divs':'R$ {:.2f}',
                                         'lucro_real':'R$ {:.2f}',
                                         'rentab_pct':'{:.1f}%',
                                         'yoc_pct':'{:.1f}%'
                                     })
                                     .applymap(lambda x: 'color: green' if x>0 else 'color: red', subset=['lucro_real','rentab_pct']), 
                                     use_container_width=True)

    if modo_live: time.sleep(60); st.rerun()