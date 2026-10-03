import streamlit as st

from core import repo
from core import validators as v
from core.db import Cliente
from core.ui import db, estilo_moeda, linha_selecionada, moeda, tratar_erro

st.title("👤 Clientes")


def form_cliente(c: Cliente | None, chave: str):
    """Formulário de cadastro/edição. Retorna True se salvou."""
    with st.form(chave):
        a, b = st.columns([3, 1])
        nome = a.text_input("Nome / Razão social *", value=c.nome if c else "")
        tipo = b.radio("Tipo", ["PF", "PJ"], horizontal=True,
                       index=0 if not c or c.tipo_pessoa == "PF" else 1)
        a, b, cc = st.columns(3)
        doc = a.text_input("CPF / CNPJ", value=v.formatar_documento(c.documento) if c else "")
        tel = b.text_input("Telefone (WhatsApp)", value=v.formatar_telefone(c.telefone) if c else "",
                           placeholder="(45) 9 9999-9999")
        email = cc.text_input("E-mail", value=(c.email or "") if c else "")
        end = st.text_input("Endereço", value=(c.endereco or "") if c else "")
        obs = st.text_area("Observações", value=(c.observacoes or "") if c else "", height=80)
        ativo = st.checkbox("Cliente ativo", value=c.ativo if c else True)
        if st.form_submit_button("Salvar", type="primary"):
            ok, _ = tratar_erro(
                repo.salvar_cliente, db(),
                {"nome": nome, "tipo_pessoa": tipo, "documento": doc, "telefone": tel, "email": email,
                 "endereco": end, "observacoes": obs, "ativo": ativo},
                c.id if c else None, sucesso="Cliente salvo.")
            return ok
    return False


@st.dialog("Novo cliente", width="large")
def dialog_novo():
    if form_cliente(None, "novo_cliente"):
        st.rerun()


@st.dialog("Excluir cliente")
def dialog_excluir(cid: int, nome: str):
    st.warning(f"Excluir **{nome}** apagará também todos os processos e parcelas dele. Esta ação não pode ser desfeita.")
    st.caption("Dica: para clientes que encerraram, prefira desmarcar “Cliente ativo”.")
    if st.button("Excluir definitivamente", type="primary"):
        tratar_erro(repo.excluir_cliente, db(), cid, sucesso="Cliente excluído.")
        st.rerun()


topo1, topo2, topo3 = st.columns([3, 1, 1])
busca = topo1.text_input("Buscar", placeholder="Nome, CPF/CNPJ, telefone ou nº do processo",
                         label_visibility="collapsed")
inativos = topo2.toggle("Mostrar inativos")
if topo3.button("➕ Novo cliente", type="primary", width="stretch"):
    dialog_novo()

df = repo.df_clientes(db(), busca, apenas_ativos=not inativos)
if df.empty:
    st.info("Nenhum cliente encontrado." if busca else "Nenhum cliente cadastrado. Clique em **➕ Novo cliente**.")
    st.stop()

st.caption(f"{len(df)} cliente(s). Clique numa linha para ver detalhes.")
ev = st.dataframe(
    estilo_moeda(df, ["Em aberto", "Em atraso"]), hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
    column_config={"id": None, "Em aberto": moeda("Em aberto"), "Em atraso": moeda("Em atraso"),
                   "Ativo": st.column_config.CheckboxColumn("Ativo")},
)
sel = linha_selecionada(ev, df)
if sel is None:
    st.stop()

c = db().get(Cliente, int(sel["id"]))
st.divider()
st.subheader(c.nome)
info1, info2, info3 = st.columns(3)
info1.write(f"**{'CPF' if c.tipo_pessoa == 'PF' else 'CNPJ'}:** {v.formatar_documento(c.documento) or '—'}")
info2.write(f"**Telefone:** {v.formatar_telefone(c.telefone) or '—'}")
if link := v.link_whatsapp(c.telefone):
    info3.link_button("Abrir WhatsApp", link)

aba1, aba2 = st.tabs(["📁 Processos", "✏️ Editar cadastro"])
with aba1:
    dproc = repo.df_processos(db(), cliente_id=c.id)
    if dproc.empty:
        st.info("Este cliente ainda não tem processos.")
    else:
        st.dataframe(estilo_moeda(dproc.drop(columns=["Cliente"]), ["Recebido", "Em aberto"]), hide_index=True, width="stretch",
                     column_config={"id": None, "Recebido": moeda("Recebido"), "Em aberto": moeda("Em aberto")})
    if st.button("➕ Novo processo para este cliente"):
        st.session_state["novo_processo_cliente"] = c.id
        st.switch_page("views/processos.py")
with aba2:
    if form_cliente(c, f"edit_cliente_{c.id}"):
        st.rerun()
    if st.button("🗑️ Excluir cliente"):
        dialog_excluir(c.id, c.nome)
