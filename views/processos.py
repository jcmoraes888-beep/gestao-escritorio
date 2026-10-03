from datetime import date

import streamlit as st
from sqlalchemy import select

from core import repo
from core import validators as v
from core.comp_prazos import acoes_prazo, form_prazo, tabela_prazos
from core.componentes import acoes_parcela, tabela_parcelas
from core.db import AREAS, SISTEMAS, STATUS_PROCESSO, TIPOS_HONORARIO, Cliente, Processo
from core.ui import db, estilo_moeda, linha_selecionada, moeda, tratar_erro

st.title("📁 Processos e honorários")

clientes = {c.id: c.nome for c in db().scalars(select(Cliente).where(Cliente.ativo.is_(True)).order_by(Cliente.nome))}


def _idx(lista, valor, padrao=0):
    return lista.index(valor) if valor in lista else padrao


def form_processo(p: Processo | None, chave: str, cliente_padrao: int | None = None) -> bool:
    if not clientes:
        st.warning("Cadastre um cliente primeiro.")
        return False
    if p and p.cliente_id not in clientes:  # cliente inativo
        clientes[p.cliente_id] = p.cliente.nome
    ids = list(clientes)
    with st.form(chave):
        atual = p.cliente_id if p else cliente_padrao
        cli = st.selectbox("Cliente *", ids, format_func=clientes.get,
                           index=ids.index(atual) if atual in ids else 0)
        a, b = st.columns(2)
        numero = a.text_input("Nº do processo (CNJ)", value=v.formatar_processo(p.numero) if p else "",
                              placeholder="0000000-00.0000.0.00.0000",
                              help="Pode deixar em branco se ainda não foi distribuído.")
        acao = b.text_input("Ação *", value=p.acao if p else "", placeholder="Ex.: Pensão alimentícia")
        a, b, c = st.columns(3)
        area = a.selectbox("Área *", AREAS, index=_idx(AREAS, p.area if p else None))
        sistema = b.selectbox("Sistema", SISTEMAS, index=_idx(SISTEMAS, p.sistema if p else None))
        status = c.selectbox("Status", STATUS_PROCESSO, index=_idx(STATUS_PROCESSO, p.status if p else None))
        a, b = st.columns([2, 1])
        comarca = a.text_input("Comarca / Vara", value=(p.comarca_vara or "") if p else "")
        inicio = b.date_input("Data de início", value=p.data_inicio if p and p.data_inicio else None,
                              format="DD/MM/YYYY")
        st.markdown("**Honorários**")
        a, b, c = st.columns(3)
        tipo = a.selectbox("Tipo de honorário", TIPOS_HONORARIO,
                           index=_idx(TIPOS_HONORARIO, p.tipo_honorario if p else None))
        valor = b.number_input("Valor fixo (R$)", min_value=0.0, step=100.0, format="%.2f",
                               value=float(p.valor_contratado) if p and p.valor_contratado else 0.0,
                               help="Usado em “Fixo” e “Fixo + Êxito”.")
        perc = c.number_input("Êxito (%)", min_value=0.0, max_value=100.0, step=5.0, format="%.1f",
                              value=float(p.percentual_exito) if p and p.percentual_exito else 0.0,
                              help="Usado em “Êxito (%)” e “Fixo + Êxito”.")
        obs = st.text_area("Observações", value=(p.observacoes or "") if p else "", height=70)
        if st.form_submit_button("Salvar processo", type="primary"):
            ok, novo = tratar_erro(repo.salvar_processo, db(), {
                "cliente_id": cli, "numero": numero, "acao": acao, "area": area, "sistema": sistema,
                "status": status, "comarca_vara": comarca, "data_inicio": inicio, "tipo_honorario": tipo,
                "valor_contratado": valor or None, "percentual_exito": perc or None, "observacoes": obs,
            }, p.id if p else None, sucesso="Processo salvo.")
            if ok and p is None:
                st.session_state["proc_aberto"] = novo.id
            return ok
    return False


@st.dialog("Novo processo", width="large")
def dialog_novo(cliente_padrao=None):
    if form_processo(None, "novo_proc", cliente_padrao):
        st.rerun()


@st.dialog("Excluir processo")
def dialog_excluir(pid: int):
    st.warning("Excluir o processo apaga também todas as parcelas dele (inclusive as pagas).")
    if st.button("Excluir definitivamente", type="primary"):
        tratar_erro(repo.excluir_processo, db(), pid, sucesso="Processo excluído.")
        st.session_state.pop("proc_aberto", None)
        st.rerun()


# ------------------------- Lista -------------------------
if cid := st.session_state.pop("novo_processo_cliente", None):
    dialog_novo(cid)

f1, f2, f3, f4 = st.columns([3, 1.3, 1.3, 1.2])
busca = f1.text_input("Buscar", placeholder="Cliente, ação ou nº do processo", label_visibility="collapsed")
area = f2.selectbox("Área", ["Todas"] + AREAS, label_visibility="collapsed")
status = f3.selectbox("Status", ["Todos"] + STATUS_PROCESSO, index=1, label_visibility="collapsed")
if f4.button("➕ Novo processo", type="primary", width="stretch"):
    dialog_novo()

df = repo.df_processos(db(), area=None if area == "Todas" else area,
                       status=None if status == "Todos" else status, busca=busca)
if df.empty:
    st.info("Nenhum processo encontrado.")
    st.stop()

st.caption(f"{len(df)} processo(s). Clique numa linha para ver honorários e parcelas.")
ev = st.dataframe(estilo_moeda(df, ["Recebido", "Em aberto"]), hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
                  column_config={"id": None, "Recebido": moeda("Recebido"), "Em aberto": moeda("Em aberto")},
                  key="tab_processos")
sel = linha_selecionada(ev, df)
pid = int(sel["id"]) if sel is not None else st.session_state.get("proc_aberto")
p = db().get(Processo, pid) if pid else None
if not p:
    st.stop()
st.session_state["proc_aberto"] = p.id

# ------------------------- Detalhe -------------------------
st.divider()
st.subheader(f"{p.acao} — {p.cliente.nome}")
st.caption(f"{v.formatar_processo(p.numero) or 'Sem número'} · {p.area} · {p.sistema or '—'} · {p.status} · "
           f"Honorário: {repo.descrever_honorario(p)}")

aba1, aba_pz, aba2 = st.tabs(["💰 Parcelas", "📅 Prazos", "✏️ Editar processo"])
with aba1:
    dfp = repo.df_parcelas(db(), processo_id=p.id)
    pago = dfp.loc[dfp["Status"] == "Paga", "Valor pago"].sum() if not dfp.empty else 0
    aberto = dfp.loc[dfp["Status"] != "Paga", "Valor"].sum() if not dfp.empty else 0
    m1, m2, m3 = st.columns(3)
    m1.metric("Contratado (fixo)", v.brl(p.valor_contratado) if p.valor_contratado else "—")
    m2.metric("Recebido", v.brl(pago))
    m3.metric("Em aberto", v.brl(aberto))

    if dfp.empty:
        st.info("Nenhuma parcela. Use **Gerar parcelas** abaixo.")
    else:
        sp = tabela_parcelas(dfp, f"parc_proc_{p.id}",
                             ocultar=["Cliente", "Ação", "Área", "Nº processo", "Dias de atraso"])
        if sp is not None:
            acoes_parcela(sp, "proc")

    c1, c2, c3 = st.columns(3)
    with c1.expander("🧮 Gerar parcelas", expanded=dfp.empty and bool(p.valor_contratado)):
        with st.form(f"gerar_{p.id}"):
            total = st.number_input("Valor total (R$)", min_value=0.0, step=100.0, format="%.2f",
                                    value=float(p.valor_contratado or 0))
            entrada = st.number_input("Entrada (R$)", min_value=0.0, step=100.0, format="%.2f")
            dt_ent = st.date_input("Data da entrada", value=date.today(), format="DD/MM/YYYY")
            n = st.number_input("Nº de parcelas (após a entrada)", min_value=0, max_value=120, value=1)
            primeiro = st.date_input("1º vencimento", value=repo.add_meses(date.today(), 1), format="DD/MM/YYYY")
            st.caption("⚠️ Substitui as parcelas **em aberto** deste processo. As pagas são mantidas.")
            if st.form_submit_button("Gerar", type="primary"):
                ok, _ = tratar_erro(repo.gerar_parcelas, db(), p.id, total, int(n), primeiro, entrada, dt_ent,
                                    sucesso="Parcelas geradas.")
                if ok:
                    st.rerun()
    with c2.expander("🏆 Lançar honorário de êxito"):
        if not p.percentual_exito:
            st.caption("Este processo não tem percentual de êxito. Edite o processo para incluir.")
        else:
            with st.form(f"exito_{p.id}"):
                base = st.number_input("Valor obtido no acordo/sentença (R$)", min_value=0.0, step=500.0,
                                       format="%.2f")
                st.caption(f"O honorário será {float(p.percentual_exito):g}% do valor obtido.")
                venc = st.date_input("Vencimento", value=date.today(), format="DD/MM/YYYY")
                if st.form_submit_button("Lançar", type="primary"):
                    ok, _ = tratar_erro(repo.lancar_exito, db(), p.id, base, venc, sucesso="Êxito lançado.")
                    if ok:
                        st.rerun()
    with c3.expander("➕ Parcela avulsa"):
        with st.form(f"avulsa_{p.id}"):
            desc = st.text_input("Descrição", placeholder="Ex.: Custas, diligência")
            val = st.number_input("Valor (R$)", min_value=0.0, step=50.0, format="%.2f")
            venc = st.date_input("Vencimento", value=date.today(), format="DD/MM/YYYY", key=f"venc_av_{p.id}")
            if st.form_submit_button("Adicionar", type="primary"):
                ok, _ = tratar_erro(repo.adicionar_parcela, db(), p.id, desc, val, venc, sucesso="Parcela adicionada.")
                if ok:
                    st.rerun()

with aba_pz:
    dpz = repo.df_prazos(db(), processo_id=p.id)
    if dpz.empty:
        st.info("Nenhum prazo cadastrado para este processo.")
    else:
        spz = tabela_prazos(dpz, f"prazos_proc_{p.id}", ocultar=["Cliente", "Ação", "Nº processo"])
        if spz is not None:
            with st.container(border=True):
                acoes_prazo(int(spz["id"]), f"proc{p.id}")
    with st.expander("➕ Novo prazo", expanded=dpz.empty):
        form_prazo(f"novo_prazo_proc_{p.id}", processo_id=p.id)

with aba2:
    if form_processo(p, f"edit_proc_{p.id}"):
        st.rerun()
    if st.button("🗑️ Excluir processo"):
        dialog_excluir(p.id)
