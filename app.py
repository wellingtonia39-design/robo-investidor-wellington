import streamlit as st
import pandas as pd
import requests
import json
import time
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Robô Investidor Pro 9.0 (Google Cloud)", layout="wide", page_icon="☁️")

# --- NOME DA PLANILHA NO GOOGLE (Tem que ser exato) ---
NOME_PLANILHA_GOOGLE = "carteira_robo_db"

# --- SENHA DE ACESSO (Pode deixar fixo ou usar Secrets também) ---
SENHA_SECRETA = "123456"

# --- CONEXÃO COM GOOGLE SHEETS ---
def conectar_google_sheets():
    try:
        # Pega as credenciais do "Cofre" do Streamlit
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"]) # Transforma em dict python
        
        # Corrige formatação da chave privada (o TOML às vezes zoa as quebras de linha)
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Abre a planilha
        sheet = client.open(NOME_PLANILHA_GOOGLE).sheet1
        return sheet
    except Exception as e:
        st.error(f"Erro ao conectar no Google: {e}")
        return None

# --- CARREGAR DADOS (DA NUVEM) ---
def carregar_carteira():
    sheet = conectar_google_sheets()
    if sheet:
        try:
            dados = sheet.get_all_records()
            carteira = {}
            # Converte a lista do Google para o formato do nosso Robô
            for linha in dados:
                t = linha['Ticker']
                carteira[t] = {
                    'qtde': linha['Qtd'],
                    'meta_pct': linha['Meta'],
                    'pm': float(str(linha['PM']).replace(',', '.')),
                    'divs': float(str(linha['Divs']).replace(',', '.'))
                }
            return carteira
        except:
            return {} # Retorna vazio se der erro ou estiver vazia
    return {}

# --- SALVAR DADOS (NA NUVEM) ---
def salvar_carteira(carteira):
    sheet = conectar_google_sheets()
    if sheet:
        # Prepara os dados para o formato de tabela
        linhas = []
        # Cabeçalho
        linhas.append(["Ticker", "Qtd", "Meta", "PM", "Divs"])
        
        for t, dados in carteira.items():
            linhas.append([
                t, 
                dados['qtde'], 
                dados['meta_pct'], 
                dados.get('pm', 0.0), 
                dados.get('divs', 0.0)
            ])
        
        # Limpa e Reescreve
        sheet.clear()
        sheet.update(linhas)

# --- CONFIGURAÇÕES DE DADOS AUXILIARES ---
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
CARTEIRAS_PRONTAS = {
    "🏆 Carteira Recomendada IA": {"WEGE3": 10, "ITUB4": 15, "VALE3": 10, "TAEE11": 10, "PSSA3": 5, "IVVB11": 20, "HGLG11": 10, "KNCR11": 10, "MXRF11": 10}
}

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

def obter_setor(ticker):
    return SETORES.get(ticker.replace(".SA","").strip(), "Outros")

# --- LOGIN ---
def check_password():
    if 'logado' not in st.session_state: st.session_state['logado'] = False
    if st.session_state['logado']: return True
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("## 🔐 Acesso Google Cloud")
        senha = st.text_input("Digite sua senha:", type="password")
        if st.button("Entrar", type="primary"):
            if senha == SENHA_SECRETA:
                st.session_state['logado'] = True; st.rerun()
            else: st.error("Senha incorreta!")
    return False

# ================= APP START =================
if check_password():
    # --- CHECK DE CONEXÃO ---
    with st.spinner("Conectando ao Google Sheets..."):
        carteira = carregar_carteira()
    
    with st.sidebar:
        st.title("☁️ Painel Google Cloud")
        if st.button("Sair"): st.session_state['logado']=False; st.rerun()
        st.divider()
        st.success("Status: Conectado ao Google Drive ✅")
        st.divider()
        modo_live = st.toggle("Modo Live (60s)")

    st.title("Minha Carteira (Sincronizada na Nuvem)")

    # --- INPUTS ---
    c1, c2 = st.columns([1, 2])
    aporte = c1.number_input("💰 Aporte (R$)", value=1000.00, step=100.0)
    c2.write(""); c2.write("")
    executar = c2.button("🚀 Analisar", type="primary")

    # --- EDIÇÃO ---
    with st.expander("📝 Editar Ativos (Salva no Google Sheets)"):
        # Importar Modelo
        mod = st.selectbox("Importar Modelo:", ["..."] + list(CARTEIRAS_PRONTAS.keys()))
        if st.button("Aplicar Modelo"):
            if mod != "...":
                novos = CARTEIRAS_PRONTAS[mod]
                for t, m in novos.items():
                    if t not in carteira: carteira[t] = {'qtde':0, 'meta_pct':m, 'pm':0.0, 'divs':0.0}
                salvar_carteira(carteira)
                st.rerun()

        add = st.text_input("Novo Ticker:")
        if st.button("Adicionar") and add:
            t = add.upper().strip().replace(".SA","")
            if t not in carteira: 
                carteira[t]={'qtde':0,'meta_pct':10,'pm':0.0,'divs':0.0}
                salvar_carteira(carteira); st.rerun()

        st.divider()
        mudou_algo = False
        remover_lista = []
        
        if not carteira: st.warning("Planilha Vazia.")
        
        for t in list(carteira.keys()):
            cols = st.columns([1, 1, 1, 1, 0.5])
            cols[0].write(f"**{t}**")
            nq = cols[1].number_input(f"Q", int(carteira[t]['qtde']), key=f"q_{t}", label_visibility="collapsed")
            nm = cols[2].number_input(f"M", int(carteira[t]['meta_pct']), key=f"m_{t}", label_visibility="collapsed")
            np = cols[3].number_input(f"P", float(carteira[t].get('pm',0)), key=f"p_{t}", label_visibility="collapsed")
            
            if cols[4].button("🗑️", key=f"d_{t}"): remover_lista.append(t); mudou_algo=True

            if nq!=carteira[t]['qtde'] or nm!=carteira[t]['meta_pct'] or np!=carteira[t].get('pm',0):
                carteira[t].update({'qtde':nq, 'meta_pct':nm, 'pm':np})
                mudou_algo=True
        
        if remover_lista:
            for t in remover_lista: del carteira[t]
            salvar_carteira(carteira); st.rerun()
        
        if mudou_algo: salvar_carteira(carteira)

    # --- CÁLCULOS E DASHBOARD ---
    if executar or modo_live:
        if carteira:
            with st.spinner("Analisando..."):
                df = pd.DataFrame.from_dict(carteira, orient='index')
                precos = {}
                for t in df.index: precos[t] = obter_preco_atual(t)
                df['preco_atual'] = df.index.map(precos)
                df = df[df['preco_atual'] > 0]

                if not df.empty:
                    df['total_atual'] = df['qtde'] * df['preco_atual']
                    df['total_inv'] = df['qtde'] * df['pm']
                    df['lucro'] = df['total_atual'] - df['total_inv']
                    df['setor'] = df.index.map(obter_setor)
                    
                    df_fim, sobra = calcular_compras(df, aporte)
                    
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("Patrimônio", f"R$ {df_fim['total_atual'].sum():,.2f}")
                    k2.metric("Lucro", f"R$ {df_fim['lucro'].sum():,.2f}")
                    k3.metric("Aporte", f"R$ {(aporte-sobra):,.2f}")
                    k4.metric("Caixa", f"R$ {sobra:,.2f}")
                    
                    st.divider()
                    g1, g2 = st.columns(2)
                    with g1: st.plotly_chart(px.pie(df_fim, values='total_atual', names=df_fim.index, title="Carteira"), use_container_width=True)
                    with g2: 
                        df_s = df_fim.groupby('setor')['total_atual'].sum().reset_index()
                        st.plotly_chart(px.pie(df_s, values='total_atual', names='setor', title="Setores"), use_container_width=True)
                    
                    compra = df_fim[df_fim['comprar_qtd']>0].sort_values('custo_total', ascending=False)
                    if not compra.empty:
                        st.dataframe(compra[['preco_atual','comprar_qtd','custo_total']], use_container_width=True)
                    else: st.success("Nada para comprar.")

    if modo_live: time.sleep(60); st.rerun()