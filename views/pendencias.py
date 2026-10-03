import streamlit as st

from core import repo
from core.ui import db

st.title("🧹 Pendências de cadastro")
st.caption("Dados faltando que atrapalham a cobrança e o acompanhamento dos processos.")

df = repo.pendencias_cadastro(db())
if df.empty:
    st.success("Cadastro completo. Nenhuma pendência. 🎉")
    st.stop()

resumo = df["Pendência"].value_counts()
cols = st.columns(min(len(resumo), 4))
for i, (nome, qtd) in enumerate(resumo.items()):
    cols[i % len(cols)].metric(nome, qtd)

filtro = st.multiselect("Filtrar por tipo", resumo.index.tolist(), placeholder="Todas")
if filtro:
    df = df[df["Pendência"].isin(filtro)]
st.dataframe(df, hide_index=True, width="stretch")
st.page_link("views/clientes.py", label="Corrigir em Clientes", icon="👤")
