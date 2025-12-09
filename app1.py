import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(page_title="Dashboard Financeiro", layout="wide")
st.title("📊 Dashboard de Performance e Alocação")

# --- Configuração da Planilha ---
SHEET_ID = "1c21rBds6IGSSpJoP6YfpOMsUmo7-Q1Eku2Om38QQYSw"

# GIDs das abas
GIDS = {
    "Página1": "0",          # Histórico (Cotas, PL, Bench)
    "AA": "857049627",       # Alocação e Lista de Ativos
    "Retorno": "1036617467"  # Performance dos Ativos
}

# --- Funções de Limpeza e Carga ---
@st.cache_data(ttl=600)
def load_data(gid, header_row=0):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    try:
        df = pd.read_csv(url, header=header_row)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar aba (GID: {gid}): {e}")
        return pd.DataFrame()

def clean_float(val):
    if isinstance(val, str):
        # Remove R$, espaços, troca vírgula por ponto
        val = val.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
        try:
            return float(val)
        except:
            return 0.0
    return val

def clean_percent(val):
    if isinstance(val, str):
        val = val.replace('%', '').replace(' ', '').replace('.', '').replace(',', '.')
        try:
            return float(val) / 100
        except:
            return 0.0
    return val

# --- 1. KPIs e Gráfico de Histórico (Aba Página1) ---
st.header("1. Performance do Portfólio")
df_hist = load_data(GIDS["Página1"])

if not df_hist.empty:
    # Seleção por índice de coluna (A=0, B=1, D=3, E=4)
    # Renomeando para facilitar manipulação
    df_hist = df_hist.iloc[:, [0, 1, 3, 4]] 
    df_hist.columns = ['Data', 'Cota', 'Patrimonio', 'Benchmark']

    # Tratamento de Tipos
    df_hist['Data'] = pd.to_datetime(df_hist['Data'], dayfirst=True, errors='coerce')
    df_hist['Cota'] = df_hist['Cota'].apply(clean_float)
    df_hist['Patrimonio'] = df_hist['Patrimonio'].apply(clean_float)
    df_hist['Benchmark'] = df_hist['Benchmark'].apply(clean_float)
    
    df_hist = df_hist.sort_values('Data').dropna(subset=['Data'])

    # --- Cálculo dos KPIs (Mês, Ano, 12m) ---
    if len(df_hist) > 1:
        last_date = df_hist['Data'].iloc[-1]
        last_cota = df_hist['Cota'].iloc[-1]
        last_pl = df_hist['Patrimonio'].iloc[-1]

        # Função auxiliar para calcular retorno
        def calc_return(df, target_date):
            # Pega a cota na data imediatamente anterior ou igual ao target
            df_filtered = df[df['Data'] <= target_date]
            if not df_filtered.empty:
                start_cota = df_filtered['Cota'].iloc[-1]
                if start_cota != 0:
                    return (last_cota / start_cota) - 1
            return 0.0

        # Datas de referência
        start_month = last_date.replace(day=1) # Início do mês atual (pegar cota do dia anterior a este)
        start_year = last_date.replace(month=1, day=1) # Início do ano
        start_12m = last_date - pd.DateOffset(years=1) # 1 ano atrás

        # Buscar cota anterior ao dia 1 do mês atual (fechamento mês anterior)
        ret_mtd = calc_return(df_hist[df_hist['Data'] < start_month], start_month)
        # Buscar cota anterior ao dia 1 do ano (fechamento ano anterior)
        ret_ytd = calc_return(df_hist[df_hist['Data'] < start_year], start_year)
        # Retorno 12m
        ret_12m = calc_return(df_hist, start_12m)

        # Exibição dos KPIs
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Retorno Mês", f"{ret_mtd:.2%}")
        kpi2.metric("Retorno Ano", f"{ret_ytd:.2%}")
        kpi3.metric("Retorno 12 Meses", f"{ret_12m:.2%}")
        kpi4.metric("Patrimônio Atual", f"R$ {last_pl:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    # --- Gráfico de Linha (Cota vs Benchmark) ---
    st.subheader("Evolução: Portfólio vs Benchmark (SOFR + 3%)")
    
    # Criar gráfico com duas linhas
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_hist['Data'], y=df_hist['Cota'], mode='lines', name='Portfólio'))
    fig.add_trace(go.Scatter(x=df_hist['Data'], y=df_hist['Benchmark'], mode='lines', name='SOFR + 3%', line=dict(dash='dot')))
    
    fig.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0.5, xanchor="center"))
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("Não foi possível ler os dados da aba Página1.")

st.divider()

# --- 2. Alocação (Aba AA - Colunas G e H) ---
st.header("2. Alocação do Portfólio")
df_aa = load_data(GIDS["AA"])

if not df_aa.empty:
    col_graph, col_list = st.columns([1, 2])

    with col_graph:
        st.subheader("Distribuição por Classe")
        # Coluna G (índice 6) = Macro/Micro Classe, Coluna H (índice 7) = % PL
        # Verificando se o dataframe tem colunas suficientes
        if df_aa.shape[1] >= 8:
            df_alloc = df_aa.iloc[:, [6, 7]]
            df_alloc.columns = ['Classe', '% PL']
            
            # Limpeza
            df_alloc['% PL'] = df_alloc['% PL'].apply(clean_percent)
            df_alloc = df_alloc.dropna(subset=['Classe'])
            
            # Agrupar caso haja repetições
            df_grouped = df_alloc.groupby('Classe')['% PL'].sum().reset_index()
            
            fig_pie = px.pie(df_grouped, values='% PL', names='Classe', title='Exposição por Classe')
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.warning("Colunas G e H não encontradas na aba AA.")

    with col_list:
        st.subheader("Lista de Ativos Investidos")
        # Colunas A, B, C, D -> Índices 0, 1, 2, 3
        if df_aa.shape[1] >= 4:
            df_list = df_aa.iloc[:, [0, 1, 2, 3]]
            df_list.columns = ['Ativo', 'Descrição', 'Posição', '% PL']
            
            # Formatação visual apenas
            st.dataframe(df_list, use_container_width=True, hide_index=True)
        else:
            st.warning("Colunas de ativos (A-D) não encontradas na aba AA.")

else:
    st.error("Não foi possível ler os dados da aba AA.")

st.divider()

# --- 3. Performance dos Ativos (Aba Retorno) ---
st.header("3. Performance Detalhada dos Ativos")
df_ret = load_data(GIDS["Retorno"])

if not df_ret.empty:
    # Colunas A, B, C, D -> Índices 0, 1, 2, 3
    if df_ret.shape[1] >= 4:
        df_perf = df_ret.iloc[:, [0, 1, 2, 3]]
        df_perf.columns = ['Ativo', 'Retorno Mês', 'Retorno Ano', 'Retorno 12m']
        
        # Opcional: Limpar para ordenação se necessário, ou exibir como string
        # Se quiser colorir ou formatar, pode usar style do pandas
        st.dataframe(df_perf, use_container_width=True, hide_index=True)
    else:
        st.warning("Colunas insuficientes na aba Retorno.")
else:
    st.error("Não foi possível ler os dados da aba Retorno.")
