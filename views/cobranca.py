import streamlit as st

from core import repo
from core import validators as v
from core.ui import db, estilo_moeda

st.title("📲 Cobrança")
st.caption("Clientes com parcelas atrasadas ou vencendo nos próximos 7 dias. "
           "O botão abre o WhatsApp com a mensagem pronta; é só revisar e enviar.")

MODELO_PADRAO = (
    "Olá, {nome}! Tudo bem? Aqui é do escritório. Passando para lembrar dos honorários referentes a "
    "{acao}: {itens}. Total: {total}. Qualquer dúvida, estou à disposição."
)
with st.expander("✏️ Modelo da mensagem"):
    st.caption("Campos disponíveis: {nome}, {acao}, {itens}, {total}")
    modelo = st.text_area("Modelo", value=st.session_state.get("modelo_cobranca", MODELO_PADRAO), height=110,
                          label_visibility="collapsed")
    st.session_state["modelo_cobranca"] = modelo

dfp = repo.df_parcelas(db())
alvo = dfp[dfp["Status"].isin(["Atrasada", "Vence em breve"])] if not dfp.empty else dfp
if alvo.empty:
    st.success("Nenhuma cobrança pendente. 🎉")
    st.stop()

so_atrasadas = st.toggle("Somente atrasadas")
if so_atrasadas:
    alvo = alvo[alvo["Status"] == "Atrasada"]

grupos = (alvo.groupby(["cliente_id", "Cliente"])
          .agg(total=("Valor", "sum"), atraso=("Dias de atraso", "max"))
          .sort_values(["atraso", "total"], ascending=False).reset_index())

for _, g in grupos.iterrows():
    itens = alvo[alvo["cliente_id"] == g["cliente_id"]]
    tel = itens["Telefone"].iloc[0]
    with st.container(border=True):
        a, b, c = st.columns([3, 1.3, 1.3])
        a.markdown(f"**{g['Cliente']}**  \n{v.formatar_telefone(tel) or 'sem telefone'}")
        b.metric("Total", v.brl(g["total"]), label_visibility="collapsed")
        if g["atraso"] > 0:
            b.markdown(f":red[**{int(g['atraso'])} dia(s) de atraso**]")
        else:
            b.markdown(":orange[vence em breve]")

        desc = "; ".join(f"{r['Descrição']} de {v.brl(r['Valor'])} (venc. {r['Vencimento']:%d/%m})"
                         for _, r in itens.iterrows())
        acoes = ", ".join(sorted(set(itens["Ação"].str.lower())))
        primeiro_nome = g["Cliente"].split()[0].title()
        try:
            msg = modelo.format(nome=primeiro_nome, acao=acoes, itens=desc, total=v.brl(g["total"]))
        except (KeyError, IndexError, ValueError):
            msg = MODELO_PADRAO.format(nome=primeiro_nome, acao=acoes, itens=desc, total=v.brl(g["total"]))
        link = v.link_whatsapp(tel, msg)
        if link:
            c.link_button("💬 Cobrar no WhatsApp", link, width="stretch", type="primary")
        else:
            c.caption("Cadastre um telefone válido para cobrar pelo WhatsApp.")
        with a.expander("Ver parcelas"):
            st.dataframe(estilo_moeda(itens[["Ação", "Descrição", "Valor", "Vencimento", "Status"]], ["Valor"]), hide_index=True,
                         width="stretch",
                         column_config={"Vencimento": st.column_config.DateColumn(format="DD/MM/YYYY")})
