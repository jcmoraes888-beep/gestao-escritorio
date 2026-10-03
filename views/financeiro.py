import io
from datetime import date

import pandas as pd
import streamlit as st

from core import repo
from core import validators as v
from core.componentes import acoes_parcela, tabela_parcelas
from core.db import AREAS
from core.ui import db

st.title("💰 Parcelas e recebimentos")

dfp = repo.df_parcelas(db())
if dfp.empty:
    st.info("Nenhuma parcela cadastrada ainda. Gere parcelas na página **Processos e honorários**.")
    st.stop()

f1, f2, f3, f4 = st.columns([2.2, 1.2, 1.2, 1.6])
busca = f1.text_input("Buscar cliente", placeholder="Nome do cliente", label_visibility="collapsed")
status = f2.multiselect("Status", ["Atrasada", "Vence em breve", "A vencer", "Paga"],
                        default=["Atrasada", "Vence em breve", "A vencer"], placeholder="Status",
                        label_visibility="collapsed")
area = f3.selectbox("Área", ["Todas"] + AREAS, label_visibility="collapsed")
ano = date.today().year
periodo = f4.date_input("Vencimento entre", value=(date(ano - 1, 1, 1), date(ano + 1, 12, 31)), format="DD/MM/YYYY",
                        label_visibility="collapsed")

f = dfp.copy()
if busca:
    f = f[f["Cliente"].str.contains(busca, case=False, na=False)]
if status:
    f = f[f["Status"].isin(status)]
if area != "Todas":
    f = f[f["Área"] == area]
if isinstance(periodo, tuple) and len(periodo) == 2:
    f = f[(f["Vencimento"] >= periodo[0]) & (f["Vencimento"] <= periodo[1])]

m1, m2, m3, m4 = st.columns(4)
m1.metric("Parcelas filtradas", len(f))
m2.metric("Em aberto", v.brl(f.loc[f["Status"] != "Paga", "Valor"].sum()))
m3.metric("Atrasado", v.brl(f.loc[f["Status"] == "Atrasada", "Valor"].sum()))
m4.metric("Recebido", v.brl(f.loc[f["Status"] == "Paga", "Valor pago"].sum()))

if f.empty:
    st.info("Nenhuma parcela com esses filtros.")
    st.stop()

sel = tabela_parcelas(f.reset_index(drop=True), "parc_fin")
if sel is not None:
    with st.container(border=True):
        st.caption(f"{sel['Cliente']} · {sel['Ação']} · {sel['Nº processo']}")
        acoes_parcela(sel, "fin")

# Exportar para Excel
exp = f.drop(columns=["id", "processo_id", "cliente_id"]).copy()
exp["Telefone"] = exp["Telefone"].map(v.formatar_telefone)
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as w:
    exp.to_excel(w, index=False, sheet_name="Parcelas")
st.download_button("⬇️ Exportar para Excel", buf.getvalue(), file_name=f"parcelas_{date.today():%Y-%m-%d}.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
