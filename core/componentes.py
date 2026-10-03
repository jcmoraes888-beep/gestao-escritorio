"""Componentes de tela reutilizados (parcelas e pagamentos)."""
from datetime import date

import pandas as pd
import streamlit as st

from core import repo
from core import validators as v
from core.config import escritorio
from core.db import FORMAS_PAGAMENTO
from core.recibo import gerar_recibo_pdf, numero_recibo
from core.ui import colorir_status, data, db, linha_selecionada, moeda, tratar_erro

COLUNAS_PARCELA = {
    "id": None, "processo_id": None, "cliente_id": None, "Telefone": None,
    "Valor": moeda("Valor"), "Valor pago": moeda("Valor pago"),
    "Vencimento": data("Vencimento"), "Pago em": data("Pago em"),
}


def tabela_parcelas(df: pd.DataFrame, chave: str, ocultar: list[str] | None = None):
    """Mostra parcelas com status colorido e seleção de uma linha. Retorna a linha selecionada."""
    vis = df.drop(columns=[c for c in (ocultar or []) if c in df.columns])
    estilo = vis.style.map(colorir_status, subset=["Status"]).format(
        {"Valor": v.brl, "Valor pago": lambda x: v.brl(x) if pd.notna(x) else ""}, na_rep=""
    )
    ev = st.dataframe(estilo, hide_index=True, width="stretch", on_select="rerun",
                      selection_mode="single-row", key=chave, column_config=COLUNAS_PARCELA)
    return linha_selecionada(ev, vis)


def acoes_parcela(sel, chave: str):
    """Painel para baixar/estornar/excluir a parcela selecionada."""
    st.markdown(f"**{sel['Descrição']}** · {v.brl(sel['Valor'])} · vence {sel['Vencimento']:%d/%m/%Y} · "
                f"*{sel['Status']}*")
    if sel["Status"] != "Paga":
        with st.form(f"pagar_{chave}_{sel['id']}"):
            a, b, c = st.columns(3)
            dt = a.date_input("Data do pagamento", value=date.today(), format="DD/MM/YYYY")
            val = b.number_input("Valor pago (R$)", min_value=0.01, value=float(sel["Valor"]), step=50.0,
                                 format="%.2f")
            forma = c.selectbox("Forma", FORMAS_PAGAMENTO)
            st.caption("Se o valor pago for menor que o da parcela, o saldo vira uma nova parcela em aberto.")
            if st.form_submit_button("💵 Registrar pagamento", type="primary"):
                ok, saldo = tratar_erro(repo.registrar_pagamento, db(), int(sel["id"]), dt, val, forma,
                                        sucesso="Pagamento registrado.")
                if ok:
                    st.rerun()
    else:
        b1, b2, _ = st.columns([1.3, 1.3, 3])
        dados = repo.dados_recibo(db(), int(sel["id"]))
        pdf = gerar_recibo_pdf(dados, escritorio())
        nome_arq = f"recibo_{numero_recibo(dados['parcela_id'], dados['data_pagamento']).replace('/', '-')}_" \
                   f"{dados['cliente'].split()[0].lower()}.pdf"
        b1.download_button("🧾 Baixar recibo (PDF)", pdf, file_name=nome_arq, mime="application/pdf",
                           type="primary", key=f"recibo_{chave}_{sel['id']}", width="stretch")
        if b2.button("↩️ Estornar pagamento", key=f"estornar_{chave}_{sel['id']}", width="stretch"):
            tratar_erro(repo.estornar_pagamento, db(), int(sel["id"]), sucesso="Pagamento estornado.")
            st.rerun()
    if st.button("🗑️ Excluir parcela", key=f"excluir_{chave}_{sel['id']}"):
        tratar_erro(repo.excluir_parcela, db(), int(sel["id"]), sucesso="Parcela excluída.")
        st.rerun()
