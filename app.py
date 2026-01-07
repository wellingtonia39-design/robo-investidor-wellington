import streamlit as st
import pandas as pd
import requests
import json
import time
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Robô Investidor Pro 9.4", layout="wide", page_icon="🦅")

# --- CONSTANTES ---
NOME_PLANILHA_GOOGLE = "carteira_robo_db"

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

# --- ESTRATÉGIAS ---
CARTEIRAS_PRONTAS = {
    "🏆 Carteira Recomendada IA": {
        "WEGE3": 10, "ITUB4": 15, "VALE3": 10, "TAEE11": 10, "PSSA3": 5, 
        "IVVB11": 20, "HGLG11": 10, "KNCR11": 10, "MXRF11": 10
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

# --- CONEXÃO COM GOOGLE SHEETS ---
def conectar_google_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        # Abre o arquivo da planilha
        sh = client.open(NOME_PLANILHA_GOOGLE)
        return sh
    except Exception as e:
        st.error(f"Erro ao conectar no Google: {e}")
        return None

# --- GERENCIAMENTO DE ABAS (CARTEIRA E CONFIG) ---
def pegar_aba_carteira(sh):
    # Tenta pegar a primeira aba, ou cria se não existir
    try: return sh.get_worksheet(0)
    except: return sh.add_worksheet(title="Carteira", rows=100, cols=10)

def pegar_aba_config(sh):
    # Tenta pegar aba 'Config', se não existir, cria
    try: 
        ws = sh.worksheet("Config")
        return ws
    except: 
        ws = sh.add_worksheet(title="Config", rows=5, cols=5)
        ws.update([["Senha", "MetaMensal"], ["123456", 1000.0]]) # Valor Inicial
        return ws

# --- CARREGAR/SALVAR CARTEIRA ---
def carregar_carteira():
    sh = conectar_google_sheets()
    if sh:
        try:
            ws = pegar_aba_carteira(sh)
            dados = ws.get_all_records()
            carteira = {}
            for linha in dados:
                t = linha['Ticker']
                if not t: continue
                qtde = linha['Qtd'] if linha['Qtd'] != '' else 0
                meta = linha['Meta'] if linha['Meta'] != '' else 0
                try: pm = float(str(linha['PM']).replace(',', '.'))
                except: pm = 0.0
                try: divs = float(str(linha['Divs']).replace(',', '.'))
                except: divs = 0.0
                carteira[t] = {'qtde': qtde, 'meta_pct': meta, 'pm': pm, 'divs': divs}
            return carteira
        except: return {}
    return {}

def salvar_carteira(carteira):
    sh = conectar_google_sheets()
    if sh:
        ws = pegar_aba_carteira(sh)
        linhas = [["Ticker", "Qtd", "Meta", "PM", "Divs"]]
        for t, dados in carteira.items():
            linhas.append([t, dados['qtde'], dados['meta_pct'], dados.get('pm', 0.0), dados.get('divs', 0.0)])
        ws.clear()
        ws.update(linhas)

# --- CARREGAR/SALVAR CONFIGURAÇÕES (AGORA NA NUVEM) ---
def carregar_config():
    padrao = {"senha": "123456", "meta_mensal": 1000.00}
    sh = conectar_google_sheets()
    if sh:
        try:
            ws = pegar_aba_config(sh)
            dados = ws.get_all_records()
            if dados:
                # Pega a primeira linha de dados
                return {
                    "senha": str(dados[0]['Senha']),
                    "meta_mensal": float(str(dados[0]['MetaMensal']).replace(',', '.'))
                }
        except: pass
    return padrao

def salvar_config(conf):
    sh = conectar_google_sheets()
    if sh:
        ws = pegar_aba_config(sh)
        ws.clear()
        ws.update([["Senha", "MetaMensal"], [conf['senha'], conf['meta_mensal']]])

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

def obter_setor(ticker):
    return SETORES.get(ticker.replace(".SA","").strip(), "Outros")

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

# --- LOGIN ---
def check_password():
    # Carrega config da nuvem na hora do login
    if 'config_cache' not in st.session_state:
        st.session_state['config_cache'] = carregar_config()
    conf = st.session_state['config_cache']

    if 'logado' not in st.session_state: st.session_state['logado'] = False
    if st.session_state['logado']: return True
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("## 🔐 Acesso Seguro (Cloud)")
        senha = st.text_input("Digite sua senha:", type="password")
        if st.button("Entrar", type="primary"):
            if senha == conf['senha']:
                st.session_state['logado'] = True; st.rerun()
            else: st.error("Senha incorreta!")
    return False

# ================= APP START =================
if check_password():
    if 'config_cache' not in st.session_state: st.session_state['config_cache'] = carregar_config()
    conf = st.session_state['config_cache']
    
    with st.sidebar:
        st.title("🦅 Painel Cloud")
        menu = st.radio("Navegação", ["🏠 Minha Carteira", "⚙️ Configurações"])
        st.divider()
        st.success("Google Drive: Conectado ✅")
        if st.button("🔒 Sair"): st.session_state['logado']=False; st.rerun()
        st.divider()
        modo_live = st.toggle("🔄 Modo Live (60s)")

    if 'carteira_cache' not in st.session_state:
        with st.spinner("Sincronizando Banco de Dados..."):
            st.session_state['carteira_cache'] = carregar_carteira()
    carteira_completa = st.session_state['carteira_cache']

    # ================= TELA: CARTEIRA =================
    if menu == "🏠 Minha Carteira":
        st.title("Minha Carteira (Nuvem ☁️)")

        if not carteira_completa: st.warning("Carteira vazia no Google Sheets.")

        # --- FILTROS ---
        st.markdown("### 🔍 Visualização")
        opcoes_filtro = ["Todas"] + list(CARTEIRAS_PRONTAS.keys()) + ["Personalizados"]
        filtro_selecionado = st.multiselect("Filtrar Carteiras:", opcoes_filtro, default=["Todas"])
        
        carteira_exibicao = {}
        if "Todas" in filtro_selecionado or not filtro_selecionado:
            carteira_exibicao = carteira_completa.copy()
        else:
            tickers_permitidos = []
            todos_prontos = []
            for k, v in CARTEIRAS_PRONTAS.items(): todos_prontos.extend(v.keys())
            for selecao in filtro_selecionado:
                if selecao in CARTEIRAS_PRONTAS: tickers_permitidos.extend(CARTEIRAS_PRONTAS[selecao].keys())
                elif selecao == "Personalizados":
                    for t in carteira_completa.keys():
                        if t not in todos_prontos: tickers_permitidos.append(t)
            for t, dados in carteira_completa.items():
                if t in tickers_permitidos: carteira_exibicao[t] = dados

        st.divider()

        # --- CÁLCULO DE LIBERDADE ---
        patrimonio_est = sum([d['qtde'] * d.get('pm', 0) for d in carteira_exibicao.values()])
        renda_est_mensal = patrimonio_est * 0.007 # 0.7% a.m (estimativa base)
        meta = conf['meta_mensal']
        progresso = min(renda_est_mensal / meta, 1.0) if meta > 0 else 0
        
        c_meta1, c_meta2 = st.columns([3, 1])
        with c_meta1:
            st.subheader(f"🚀 Rumo à Liberdade: R$ {renda_est_mensal:.2f} / R$ {meta:.2f} (mês)")
            st.progress(progresso)
        with c_meta2: st.metric("Concluído", f"{progresso*100:.1f}%")
        st.divider()

        c1, c2 = st.columns([1, 2])
        aporte = c1.number_input("💰 Aporte (R$)", value=1000.00, step=100.0)
        c2.write(""); c2.write("")
        executar = c2.button("🚀 Analisar Carteira", type="primary")

        # --- EDIÇÃO ---
        with st.expander(f"📝 Editar Ativos ({len(carteira_exibicao)} visíveis)", expanded=True):
            add = st.text_input("Novo Ticker (ex: BBAS3)")
            if st.button("Adicionar") and add:
                t = add.upper().strip().replace(".SA","")
                if t not in carteira_completa: 
                    carteira_completa[t]={'qtde':0,'meta_pct':10,'pm':0.0,'divs':0.0}
                    salvar_carteira(carteira_completa) 
                    st.session_state['carteira_cache'] = carteira_completa
                    st.rerun()

            st.divider()
            mudou_algo = False
            remover_lista = []
            
            cols_head = st.columns([1, 1, 1, 1, 1, 0.5])
            cols_head[0].markdown("**Ativo**")
            cols_head[1].markdown("**Qtd**")
            cols_head[2].markdown("**Meta %**")
            cols_head[3].markdown("**P. Médio**")
            cols_head[4].markdown("**Divs (R$)**")
            
            for t in list(carteira_exibicao.keys()):
                cols = st.columns([1, 1, 1, 1, 1, 0.5])
                cols[0].write(f"**{t}**")
                nq = cols[1].number_input(f"Q_{t}", value=int(carteira_completa[t]['qtde']), min_value=0, step=1, key=f"q_{t}", label_visibility="collapsed")
                nm = cols[2].number_input(f"M_{t}", value=int(carteira_completa[t]['meta_pct']), min_value=0, step=1, key=f"m_{t}", label_visibility="collapsed")
                np = cols[3].number_input(f"P_{t}", value=float(carteira_completa[t].get('pm',0)), min_value=0.0, step=0.01, format="%.2f", key=f"p_{t}", label_visibility="collapsed")
                nd = cols[4].number_input(f"D_{t}", value=float(carteira_completa[t].get('divs',0)), min_value=0.0, step=0.01, format="%.2f", key=f"d_{t}", label_visibility="collapsed")
                
                if cols[5].button("🗑️", key=f"del_{t}"): remover_lista.append(t); mudou_algo=True
                if nq!=carteira_completa[t]['qtde'] or nm!=carteira_completa[t]['meta_pct'] or np!=carteira_completa[t].get('pm',0) or nd!=carteira_completa[t].get('divs',0):
                    carteira_completa[t].update({'qtde':nq, 'meta_pct':nm, 'pm':np, 'divs':nd})
                    mudou_algo=True
            
            if remover_lista:
                for t in remover_lista: del carteira_completa[t]
                salvar_carteira(carteira_completa); st.session_state['carteira_cache'] = carteira_completa; st.rerun()
            if mudou_algo: 
                salvar_carteira(carteira_completa)
                st.session_state['carteira_cache'] = carteira_completa

        # --- DASHBOARD ---
        if executar or modo_live:
            if carteira_exibicao:
                with st.spinner("Analisando Mercado..."):
                    df = pd.DataFrame.from_dict(carteira_exibicao, orient='index')
                    precos = {}
                    for t in df.index: precos[t] = obter_preco_atual(t)
                    df['preco_atual'] = df.index.map(precos)
                    df = df[df['preco_atual'] > 0]

                    if not df.empty:
                        df['total_atual'] = df['qtde'] * df['preco_atual']
                        df['total_inv'] = df['qtde'] * df['pm']
                        df['lucro_cota'] = df['total_atual'] - df['total_inv']
                        df['lucro_real'] = df['lucro_cota'] + df['divs']
                        df['rentab_pct'] = df.apply(lambda x: (x['lucro_real']/x['total_inv'])*100 if x['total_inv']>0 else 0, axis=1)
                        df['yoc_pct'] = df.apply(lambda x: (x['divs']/x['total_inv'])*100 if x['total_inv']>0 else 0, axis=1)
                        df['setor'] = df.index.map(obter_setor)

                        df_fim, sobra = calcular_compras(df, aporte)
                        
                        patr = df_fim['total_atual'].sum()
                        lucro = df_fim['lucro_real'].sum()
                        
                        # --- PROJEÇÃO DE RENDA (NOVO!) ---
                        # Estimativa conservadora de 8% a.a. sobre o patrimônio total
                        projecao_anual = patr * 0.08 
                        
                        k1, k2, k3, k4 = st.columns(4)
                        k1.metric("Patrimônio", f"R$ {patr:,.2f}")
                        k2.metric("Lucro Real", f"R$ {lucro:,.2f}", delta=f"{(lucro/patr*100) if patr>0 else 0:.1f}%")
                        k3.metric("🔮 Projeção Anual (8%)", f"R$ {projecao_anual:,.2f}", delta="Estimado")
                        k4.metric("Caixa", f"R$ {sobra:,.2f}")

                        st.divider()

                        g1, g2 = st.columns(2)
                        with g1: st.plotly_chart(px.pie(df_fim, values='total_atual', names=df_fim.index, title="Por Ativo", hole=0.5), use_container_width=True)
                        with g2: 
                            df_s = df_fim.groupby('setor')['total_atual'].sum().reset_index()
                            st.plotly_chart(px.pie(df_s, values='total_atual', names='setor', title="Por Setor", hole=0.5), use_container_width=True)
                        
                        st.subheader("🛒 Ordem de Compra")
                        compra = df_fim[df_fim['comprar_qtd']>0].sort_values('custo_total', ascending=False)
                        if not compra.empty:
                            st.dataframe(compra[['preco_atual','meta_pct','comprar_qtd','custo_total']].style.format({'preco_atual':'R$ {:.2f}','custo_total':'R$ {:.2f}','meta_pct':'{:.0f}%'}), use_container_width=True)
                        else: st.success("Aguarde! Nenhuma compra necessária.")

                        st.divider()
                        with st.expander("🔎 Detalhes (Yield on Cost, Rentabilidade)"):
                            cols = ['qtde','pm','preco_atual','divs','lucro_real','rentab_pct', 'yoc_pct']
                            st.dataframe(df_fim[cols].sort_values('rentab_pct', ascending=False)
                                         .style.format({'pm':'R$ {:.2f}','preco_atual':'R$ {:.2f}','divs':'R$ {:.2f}','lucro_real':'R$ {:.2f}','rentab_pct':'{:.1f}%','yoc_pct':'{:.1f}%'})
                                         .applymap(lambda x: 'color: green' if x>0 else 'color: red', subset=['lucro_real','rentab_pct']), use_container_width=True)
            else: st.info("Filtro vazio.")

    # ================= TELA: CONFIGURAÇÕES (AGORA SALVA NA NUVEM) =================
    elif menu == "⚙️ Configurações":
        st.title("Configurações (Nuvem ☁️)")
        
        st.subheader("🎯 Meta Mensal")
        nm = st.number_input("Renda Passiva Desejada (R$)", value=float(conf['meta_mensal']))
        if nm != conf['meta_mensal']:
            conf['meta_mensal'] = nm
            salvar_config(conf) # Salva no Google
            st.session_state['config_cache'] = conf
            st.success("Meta Salva na Nuvem!")

        st.divider()

        st.subheader("🔑 Alterar Senha")
        s1 = st.text_input("Nova Senha", type="password")
        s2 = st.text_input("Confirmar", type="password")
        if st.button("Salvar Senha"):
            if s1 == s2 and len(s1)>3:
                conf['senha'] = s1
                salvar_config(conf) # Salva no Google
                st.session_state['config_cache'] = conf
                st.success("Senha atualizada na Nuvem! Faça login novamente.")
                time.sleep(2); st.session_state['logado']=False; st.rerun()
            else: st.error("Senhas diferentes ou muito curta.")
        
        st.divider()
        st.subheader("Importar Modelo")
        mod = st.selectbox("Escolha:", ["..."] + list(CARTEIRAS_PRONTAS.keys()))
        if st.button("Aplicar Modelo"):
            if mod != "...":
                novos = CARTEIRAS_PRONTAS[mod]
                for t, m in novos.items():
                    if t not in carteira_completa: carteira_completa[t] = {'qtde':0, 'meta_pct':m, 'pm':0.0, 'divs':0.0}
                salvar_carteira(carteira_completa)
                st.session_state['carteira_cache'] = carteira_completa
                st.toast("Modelo aplicado!")
                time.sleep(1); st.rerun()

    if modo_live: time.sleep(60); st.rerun()