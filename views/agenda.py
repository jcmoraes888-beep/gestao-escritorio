import streamlit as st
from sqlalchemy import select

from core import repo
from core.comp_prazos import acoes_prazo, form_prazo, tabela_prazos
from core.db import TIPOS_PRAZO, Cliente, Processo
from core.ui import db

st.title("📅 Agenda de prazos")

processos = {
    p.id: f"{p.cliente.nome} — {p.acao}"
    for p in db().scalars(select(Processo).join(Cliente).where(Processo.status == "Ativo").order_by(Cliente.nome))
}


@st.dialog("Novo prazo", width="large")
def dialog_novo():
    form_prazo("novo_prazo_agenda", processos=processos)


df = repo.df_prazos(db())
abertos = df[df["Status"] != "Concluído"]
m1, m2, m3, m4 = st.columns(4)
m1.metric("🔴 Vencidos", int((abertos["Status"] == "Vencido").sum()))
m2.metric("🟠 Hoje", int((abertos["Status"] == "Hoje").sum()))
m3.metric("🟡 Próximos 7 dias", int((abertos["Status"] == "Próximos 7 dias").sum()))
m4.metric("Em aberto (total)", len(abertos))

f1, f2, f3, f4 = st.columns([2.2, 2, 1.4, 1.2])
busca = f1.text_input("Buscar", placeholder="Cliente, descrição ou nº do processo", label_visibility="collapsed")
status = f2.multiselect("Status", ["Vencido", "Hoje", "Próximos 7 dias", "Futuro", "Concluído"],
                        default=["Vencido", "Hoje", "Próximos 7 dias", "Futuro"], placeholder="Status",
                        label_visibility="collapsed")
tipo = f3.selectbox("Tipo", ["Todos"] + TIPOS_PRAZO, label_visibility="collapsed")
if f4.button("➕ Novo prazo", type="primary", width="stretch"):
    dialog_novo()

if df.empty:
    st.info("Nenhum prazo cadastrado. Clique em **➕ Novo prazo** ou cadastre pela ficha do processo.")
    st.stop()

f = df.copy()
if busca:
    b = busca.lower()
    f = f[f[["Cliente", "Descrição", "Nº processo", "Ação"]].astype(str).apply(
        lambda r: b in " ".join(r).lower(), axis=1)]
if status:
    f = f[f["Status"].isin(status)]
if tipo != "Todos":
    f = f[f["Tipo"] == tipo]

if f.empty:
    st.info("Nenhum prazo com esses filtros.")
    st.stop()

st.caption(f"{len(f)} prazo(s). Clique numa linha para marcar como cumprido, editar ou enviar ao Google Agenda.")
sel = tabela_prazos(f, "tab_agenda", ocultar=["Concluído em"] if "Concluído" not in status else None)
if sel is not None:
    with st.container(border=True):
        acoes_prazo(int(sel["id"]), "agenda", processos)
