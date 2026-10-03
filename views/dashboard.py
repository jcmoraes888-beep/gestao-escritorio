from datetime import date

import plotly.graph_objects as go
import streamlit as st

from core import repo
from core import validators as v
from core.ui import data, db, estilo_moeda, moeda

st.title("📊 Dashboard")
hoje = date.today()
r = repo.resumo(db(), hoje)
dfp = r["parcelas"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Recebido no mês", v.brl(r["recebido_mes"]), help="Pagamentos registrados neste mês")
c2.metric("A receber no mês", v.brl(r["a_receber_mes"]), help="Parcelas em aberto com vencimento até o fim do mês (inclui atrasadas)")
c3.metric("Em atraso", v.brl(r["atrasado"]),
          delta=f"{r['qtd_atrasadas']} parcela(s) · {r['clientes_inadimplentes']} cliente(s)",
          delta_color="inverse" if r["qtd_atrasadas"] else "off")
c4.metric("Total a receber", v.brl(r["a_receber"]), help="Todas as parcelas em aberto")

c5, c6, c7, c8 = st.columns(4)
c5.metric("Clientes ativos", r["clientes_ativos"])
c6.metric("Processos ativos", r["processos_ativos"])
c7.metric("Processos com êxito a receber", r["exito_pendente"],
          help="Processos ativos com honorário de êxito (%). Lance o valor quando houver acordo/sentença.")
c8.metric("Recebido (total)", v.brl(r["recebido_total"]))

# ---- Prazos ----
dpz = repo.df_prazos(db(), hoje=hoje)
urg = dpz[dpz["Status"].isin(["Vencido", "Hoje", "Próximos 7 dias"])] if not dpz.empty else dpz
if not urg.empty:
    st.divider()
    venc, hj = int((urg["Status"] == "Vencido").sum()), int((urg["Status"] == "Hoje").sum())
    st.subheader("📅 Prazos da semana")
    if venc:
        st.error(f"{venc} prazo(s) vencido(s) sem marcação de cumprido. Confira na Agenda.")
    if hj:
        st.warning(f"{hj} prazo(s) vencem **hoje**.")
    from core.comp_prazos import _cor
    st.dataframe(urg[["Data", "Dia", "Hora", "Status", "Tipo", "Descrição", "Cliente"]].style.map(_cor, subset=["Status"]),
                 hide_index=True, width="stretch", column_config={"Data": data("Data")})
    st.page_link("views/agenda.py", label="Abrir agenda de prazos", icon="📅")

if dfp.empty:
    st.info("Ainda não há parcelas. Cadastre um cliente, um processo e gere as parcelas dos honorários.")
    st.stop()

st.divider()
g1, g2 = st.columns([3, 2])
with g1:
    st.subheader("Fluxo de honorários")
    fm = repo.fluxo_mensal(dfp, hoje)
    fig = go.Figure()
    fig.add_bar(x=fm["Mês"], y=fm["Recebido"], name="Recebido", marker_color="#C9A14A")
    fig.add_bar(x=fm["Mês"], y=fm["Previsto em aberto"], name="Em aberto (por vencimento)", marker_color="#6B3A3E")
    fig.update_layout(barmode="stack", height=340, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", y=-0.15), yaxis_tickprefix="R$ ", separators=",.")
    st.plotly_chart(fig, width="stretch")

with g2:
    st.subheader("Em aberto por área")
    ab = dfp[dfp["Status"] != "Paga"]
    if ab.empty:
        st.success("Nenhum valor em aberto. 🎉")
    else:
        por_area = ab.groupby("Área")["Valor"].sum().sort_values()
        fig2 = go.Figure(go.Bar(x=por_area.values, y=por_area.index, orientation="h", marker_color="#C9A14A",
                                text=[v.brl(x) for x in por_area.values], textposition="auto",
                                textfont=dict(color="#140C0D", size=13)))
        fig2.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0), xaxis_visible=False)
        st.plotly_chart(fig2, width="stretch")

st.divider()
t1, t2 = st.columns(2)
with t1:
    st.subheader("🔴 Maiores atrasos por cliente")
    atr = dfp[dfp["Status"] == "Atrasada"]
    if atr.empty:
        st.success("Nenhuma parcela atrasada.")
    else:
        top = (atr.groupby("Cliente").agg(Valor=("Valor", "sum"), Parcelas=("id", "count"),
                                          **{"Maior atraso (dias)": ("Dias de atraso", "max")})
               .sort_values("Valor", ascending=False).reset_index())
        st.dataframe(estilo_moeda(top, ["Valor"]), hide_index=True, width="stretch", column_config={"Valor": moeda("Valor")})
        st.page_link("views/cobranca.py", label="Ir para cobrança", icon="📲")
with t2:
    st.subheader("🟠 Próximos vencimentos (7 dias)")
    prox = dfp[dfp["Status"] == "Vence em breve"][["Cliente", "Descrição", "Valor", "Vencimento"]]
    if prox.empty:
        st.info("Nada vencendo nos próximos 7 dias.")
    else:
        st.dataframe(estilo_moeda(prox, ["Valor"]), hide_index=True, width="stretch",
                     column_config={"Valor": moeda("Valor"), "Vencimento": data("Vencimento")})
