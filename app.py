import streamlit as st
import pandas as pd
import requests
import json
import os
import time
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Robô Investidor Pro 8.0", layout="wide", page_icon="🦅")
ARQUIVO_DADOS = 'minha_carteira.json'
ARQUIVO_CONFIG = 'config.json'

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

# --- GERENCIAMENTO DE CONFIGURAÇÕES (SENHA E META) ---
def carregar_config():
    padrao = {"senha": "123456", "meta_mensal": 1000.00}
    if os.path.exists(ARQUIVO_CONFIG):
        try:
            with open(ARQUIVO_CONFIG, 'r') as f:
                return json.load(f)
        except: return padrao
    return padrao

def salvar_config(conf):
    with open(ARQUIVO_CONFIG, 'w') as f:
        json.dump(conf, f, indent=4)

# --- SISTEMA DE LOGIN ---
def check_password():
    conf = carregar_config()
    if 'logado' not in st.session_state: st.session_state['logado'] = False
    if st.session_state['logado']: return True
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("## 🔐 Robô Investidor Pro")
        senha = st.text_input("Digite sua senha:", type="password")
        if st.button("Entrar", type="primary"):
            if senha == conf['senha']:
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
                    if 'divs' not in dados[t]: dados[t]['divs'] = 0.0
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
    conf = carregar_config()
    carteira = carregar_carteira()

    # --- MENU LATERAL DE NAVEGAÇÃO ---
    with st.sidebar:
        st.title("🦅 Painel de Controle")
        menu = st.radio("Navegação", ["🏠 Minha Carteira", "⚙️ Configurações"])
        
        if st.button("🔒 Sair"): st.session_state['logado'] = False; st.rerun()
        
        st.divider()
        modo_live = st.toggle("🔄 Modo Live (60s)")

    # ==========================================
    #      TELA 1: CARTEIRA (PRINCIPAL)
    # ==========================================
    if menu == "🏠 Minha Carteira":
        st.title("Minha Carteira")

        if not carteira:
            st.warning("Sua carteira está vazia! Vá em 'Configurações' para importar um modelo ou adicione abaixo.")
            
        # --- PAINEL DA LIBERDADE FINANCEIRA ---
        # Estimativa simples: Carteira rende média 0.7% ao mês (conservador)
        patrimonio_estimado = sum([d['qtde'] * d.get('pm', 0) for d in carteira.values()]) # Usa PM se não tiver cotação ainda
        renda_estimada = patrimonio_estimado * 0.007 
        meta = conf['meta_mensal']
        progresso = min(renda_estimada / meta, 1.0)
        
        st.container()
        col_meta1, col_meta2 = st.columns([3, 1])
        with col_meta1:
            st.subheader(f"🚀 Rumo à Liberdade: R$ {renda_estimada:.2f} / R$ {meta:.2f} (mês)")
            st.progress(progresso)
        with col_meta2:
            st.metric("Concluído", f"{progresso*100:.1f}%")
        st.divider()

        # INPUTS E AÇÃO
        c1, c2 = st.columns([1, 2])
        aporte = c1.number_input("💰 Aporte Nubank (R$)", value=1000.00, step=100.0)
        c2.write(""); c2.write("")
        executar = c2.button("🚀 Analisar Oportunidades", type="primary")

        # BARRA DE EDIÇÃO RÁPIDA (ADD/REMOVE)
        with st.expander("📝 Editar Ativos / Adicionar Novo"):
            add = st.text_input("Adicionar Ticker (ex: KLBN11)")
            if st.button("Adicionar") and add:
                t = add.upper().strip().replace(".SA","")
                if t not in carteira: 
                    carteira[t]={'qtde':0,'meta_pct':10,'pm':0.0,'divs':0.0}
                    salvar_carteira(carteira); st.rerun()
            
            st.divider()
            for t in list(carteira.keys()):
                cols = st.columns([1, 1, 1, 1, 0.5])
                cols[0].write(f"**{t}**")
                nq = cols[1].number_input(f"Qtd", int(carteira[t]['qtde']), key=f"q_{t}", label_visibility="collapsed")
                nm = cols[2].number_input(f"Meta", int(carteira[t]['meta_pct']), key=f"m_{t}", label_visibility="collapsed")
                divs = cols[3].number_input(f"Divs", float(carteira[t].get('divs',0)), key=f"d_{t}", label_visibility="collapsed")
                if cols[4].button("🗑️", key=f"del_{t}"):
                    del carteira[t]; salvar_carteira(carteira); st.rerun()
                
                # Atualiza em tempo real
                if nq!=carteira[t]['qtde'] or nm!=carteira[t]['meta_pct'] or divs!=carteira[t].get('divs',0):
                    carteira[t].update({'qtde':nq, 'meta_pct':nm, 'divs':divs})
                    salvar_carteira(carteira)

        if executar or modo_live:
            if not carteira: st.info("Adicione ativos para começar.")
            else:
                with st.spinner("Processando..."):
                    df = pd.DataFrame.from_dict(carteira, orient='index')
                    precos = {}
                    if not modo_live: bar = st.progress(0)
                    for i, t in enumerate(df.index):
                        precos[t] = obter_preco_atual(t)
                        if not modo_live: bar.progress((i+1)/len(df))
                    if not modo_live: bar.empty()
                    
                    df['preco_atual'] = df.index.map(precos)
                    df = df[df['preco_atual'] > 0]
                    
                    if df.empty: st.error("Erro de conexão com a Bolsa.")
                    else:
                        df['total_atual'] = df['qtde'] * df['preco_atual']
                        df['total_inv'] = df['qtde'] * df['pm']
                        df['lucro_cota'] = df['total_atual'] - df['total_inv']
                        df['lucro_real'] = df['lucro_cota'] + df['divs']
                        df['setor'] = df.index.map(obter_setor)
                        
                        df_fim, sobra = calcular_compras(df, aporte)
                        
                        # DASHBOARD
                        patr = df_fim['total_atual'].sum()
                        lucro = df_fim['lucro_real'].sum()
                        custo = aporte - sobra
                        
                        k1, k2, k3, k4 = st.columns(4)
                        k1.metric("Patrimônio", f"R$ {patr:,.2f}")
                        k2.metric("Rentabilidade Real", f"R$ {lucro:,.2f}", delta=f"{(lucro/patr*100) if patr>0 else 0:.1f}%")
                        k3.metric("Aporte Sugerido", f"R$ {custo:,.2f}")
                        k4.metric("Caixa/Sobra", f"R$ {sobra:,.2f}")
                        
                        st.divider()
                        g1, g2 = st.columns(2)
                        with g1: st.plotly_chart(px.pie(df_fim, values='total_atual', names=df_fim.index, hole=0.5, title="Por Ativo"), use_container_width=True)
                        with g2: 
                            df_s = df_fim.groupby('setor')['total_atual'].sum().reset_index()
                            st.plotly_chart(px.pie(df_s, values='total_atual', names='setor', hole=0.5, title="Por Setor"), use_container_width=True)

                        st.subheader("🛒 Ordem de Compra")
                        compra = df_fim[df_fim['comprar_qtd']>0].sort_values('custo_total', ascending=False)
                        if not compra.empty:
                            st.dataframe(compra[['preco_atual','meta_pct','comprar_qtd','custo_total']].style.format({'preco_atual':'R$ {:.2f}','custo_total':'R$ {:.2f}','meta_pct':'{:.0f}%'}), use_container_width=True)
                        else: st.success("Nada para comprar hoje!")

    # ==========================================
    #      TELA 2: CONFIGURAÇÕES
    # ==========================================
    elif menu == "⚙️ Configurações":
        st.title("Configurações do Robô")
        
        with st.container():
            st.subheader("🎯 Meta Financeira")
            nova_meta = st.number_input("Qual sua meta de renda mensal passiva? (R$)", value=float(conf['meta_mensal']), step=100.0)
            if nova_meta != conf['meta_mensal']:
                conf['meta_mensal'] = nova_meta
                salvar_config(conf)
                st.success("Meta atualizada!")

        st.divider()
        
        with st.container():
            st.subheader("🔑 Alterar Senha")
            c_s1, c_s2 = st.columns(2)
            nova_senha = c_s1.text_input("Nova Senha")
            confirmar = c_s2.text_input("Confirme a Senha")
            if st.button("Salvar Nova Senha"):
                if nova_senha == confirm:
                    if len(nova_senha) > 3:
                        conf['senha'] = nova_senha
                        salvar_config(conf)
                        st.success("Senha alterada com sucesso! Faça login novamente.")
                        time.sleep(2)
                        st.session_state['logado'] = False
                        st.rerun()
                    else: st.warning("A senha deve ter pelo menos 4 caracteres.")
                else: st.error("As senhas não coincidem.")

        st.divider()
        
        with st.container():
            st.subheader("💾 Backup e Restauração")
            # Download
            if os.path.exists(ARQUIVO_DADOS):
                with open(ARQUIVO_DADOS, "r") as f:
                    st.download_button("📥 Baixar Backup da Carteira (.json)", f, "minha_carteira.json")
            
            # Modelos
            st.write("---")
            st.write("**Resetar ou Importar Modelo**")
            modelo = st.selectbox("Escolha um modelo:", ["Selecionar..."] + list(CARTEIRAS_PRONTAS.keys()))
            if st.button("Aplicar Modelo (Cuidado: Mescla com atuais)"):
                if modelo != "Selecionar...":
                    novos = CARTEIRAS_PRONTAS[modelo]
                    for t, m in novos.items():
                        if t not in carteira: carteira[t] = {'qtde':0, 'meta_pct':m, 'pm':0.0, 'divs':0.0}
                        else: carteira[t]['meta_pct'] = m
                    salvar_carteira(carteira)
                    st.toast("Modelo aplicado!")

    if modo_live: time.sleep(60); st.rerun()