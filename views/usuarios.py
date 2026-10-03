import pandas as pd
import streamlit as st
from sqlalchemy import select

from core import auth
from core.db import Usuario
from core.ui import db, tratar_erro, usuario

st.title("🔐 Usuários e senha")
u = usuario()

st.subheader("Trocar minha senha")
with st.form("trocar_senha", clear_on_submit=True):
    atual = st.text_input("Senha atual", type="password")
    nova = st.text_input("Nova senha (mín. 8 caracteres)", type="password")
    nova2 = st.text_input("Confirme a nova senha", type="password")
    if st.form_submit_button("Alterar senha"):
        bloqueio = None
        try:
            confere = auth.autenticar(db(), u["email"], atual)
        except auth.ErroBloqueio as e:
            confere, bloqueio = None, str(e)
        if bloqueio:
            st.error(bloqueio)
        elif not confere:
            st.error("Senha atual incorreta.")
        elif nova != nova2:
            st.error("As senhas não conferem.")
        else:
            ok, _ = tratar_erro(auth.trocar_senha, db(), u["id"], nova)
            if ok:
                st.success("Senha alterada.")

if u["perfil"] != "admin":
    st.stop()

st.divider()
st.subheader("Usuários do escritório")
usuarios = db().scalars(select(Usuario).order_by(Usuario.nome)).all()
st.dataframe(pd.DataFrame([{"Nome": x.nome, "E-mail": x.email, "Perfil": x.perfil, "Ativo": x.ativo}
                           for x in usuarios]), hide_index=True, width="stretch")

with st.expander("➕ Novo usuário"):
    with st.form("novo_usuario"):
        nome = st.text_input("Nome")
        email = st.text_input("E-mail")
        senha = st.text_input("Senha provisória (mín. 8 caracteres)", type="password")
        perfil = st.selectbox("Perfil", ["usuario", "admin"],
                              format_func={"usuario": "Usuário", "admin": "Administrador"}.get)
        if st.form_submit_button("Criar usuário", type="primary"):
            ok, _ = tratar_erro(auth.criar_usuario, db(), nome, email, senha, perfil, sucesso="Usuário criado.")
            if ok:
                st.rerun()

outros = [x for x in usuarios if x.id != u["id"]]
if outros:
    with st.expander("Ativar / desativar usuário"):
        alvo = st.selectbox("Usuário", outros, format_func=lambda x: f"{x.nome} ({'ativo' if x.ativo else 'inativo'})")
        if st.button("Desativar" if alvo.ativo else "Reativar"):
            alvo.ativo = not alvo.ativo
            db().commit()
            st.rerun()


st.divider()
st.subheader("💾 Backup")
st.caption("Baixa todos os dados do escritório em Excel (clientes, processos, parcelas, prazos e usuários, "
           "sem as senhas). Faça pelo menos uma vez por semana e guarde em local seguro: o arquivo contém dados "
           "pessoais protegidos pela LGPD.")
if st.button("Gerar backup"):
    from datetime import date

    from core.backup import gerar_backup_xlsx

    dados, cont = gerar_backup_xlsx(db())
    st.success("Backup pronto: " + ", ".join(f"{k}: {v}" for k, v in cont.items()))
    st.download_button("⬇️ Baixar backup (Excel)", dados, file_name=f"backup_escritorio_{date.today():%Y-%m-%d}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
