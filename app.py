"""Gestão do Escritório — clientes, processos e honorários.

Rodar localmente:  streamlit run app.py
"""
import time
from pathlib import Path

import streamlit as st

from core import auth
from core.db import get_session
from core.ui import mostrar_avisos

TIMEOUT_MIN = 60  # logout automático após inatividade (LGPD)
ASSETS = Path(__file__).parent / "assets"
LOGO = ASSETS / "logo_completo.png"   # troque estes arquivos para usar outra marca
ICONE = ASSETS / "icone.png"
NOME_PADRAO = "Lesly Vargas Advocacia"

def _nome_app():
    try:
        return st.secrets.get("NOME_ESCRITORIO", NOME_PADRAO)
    except Exception:
        return NOME_PADRAO


st.set_page_config(page_title=_nome_app(), page_icon=str(ICONE) if ICONE.exists() else "⚖️", layout="wide")


# Texto escuro nos botões dourados (melhor leitura)
st.markdown("""<style>
button[kind="primary"], button[kind="primaryFormSubmit"], a[kind="primary"] { color: #140C0D !important; font-weight: 600; }
</style>""", unsafe_allow_html=True)


def _cabecalho_marca(largura: int | None = None):
    if LOGO.exists():
        st.image(str(LOGO), width=largura or "stretch")
    else:
        st.title(f"⚖️ {_nome_app()}")


def _aviso_banco(s):
    if s.get_bind().dialect.name != "sqlite":
        return
    try:
        chaves = list(st.secrets.keys())
    except Exception:
        chaves = []
    st.warning("⚠️ Usando o **banco LOCAL de teste**. Os dados daqui NÃO ficam salvos online.\n\n"
               f"Configurações encontradas nos Secrets: **{', '.join(chaves) or 'nenhuma'}**. "
               "É preciso ter **DATABASE_URL** (em Settings → Secrets no Streamlit Cloud). "
               "Versão do app: 2026-10-03b")


def tela_primeiro_acesso(s):
    _cabecalho_marca(largura=320)
    _aviso_banco(s)
    st.subheader("Configuração inicial")
    st.info("Nenhum usuário cadastrado ainda. Crie o usuário administrador do escritório.")
    with st.form("primeiro_admin"):
        nome = st.text_input("Nome")
        email = st.text_input("E-mail")
        senha = st.text_input("Senha (mín. 8 caracteres)", type="password")
        senha2 = st.text_input("Confirme a senha", type="password")
        if st.form_submit_button("Criar administrador", type="primary"):
            if senha != senha2:
                st.error("As senhas não conferem.")
            else:
                try:
                    u = auth.criar_usuario(s, nome, email, senha, "admin")
                    _logar(u)
                    st.rerun()
                except Exception as e:
                    s.rollback()
                    st.error(str(e))


def tela_login(s):
    _, centro, _ = st.columns([1, 1.2, 1])
    with centro:
        _cabecalho_marca()
        _aviso_banco(s)
        if st.session_state.pop("_expirou", False):
            st.warning("Sessão encerrada por inatividade. Entre novamente.")
        with st.form("login"):
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar", type="primary", width="stretch"):
                u = auth.autenticar(s, email, senha)
                if u:
                    _logar(u)
                    st.rerun()
                else:
                    time.sleep(1)  # dificulta tentativa e erro
                    st.error("E-mail ou senha incorretos.")


def _logar(u):
    st.session_state["usuario"] = {"id": u.id, "nome": u.nome, "email": u.email, "perfil": u.perfil}
    st.session_state["_ultima_acao"] = time.time()


def _sair():
    for k in list(st.session_state.keys()):
        if k != "_db":
            del st.session_state[k]


def main():
    from core.db import ErroConfiguracao

    try:
        s = get_session()
    except ErroConfiguracao as e:
        st.error(str(e))
        st.stop()
    except Exception as e:
        st.error(f"Não foi possível conectar ao banco de dados. Confira o DATABASE_URL e a senha.\n\nDetalhe: {e}")
        st.stop()
    st.session_state["_db"] = s
    try:
        if not auth.existe_usuario(s):
            tela_primeiro_acesso(s)
            return
        u = st.session_state.get("usuario")
        if u and time.time() - st.session_state.get("_ultima_acao", 0) > TIMEOUT_MIN * 60:
            _sair()
            st.session_state["_expirou"] = True
            u = None
        if not u:
            tela_login(s)
            return
        st.session_state["_ultima_acao"] = time.time()

        paginas = {
            "Visão geral": [
                st.Page("views/dashboard.py", title="Dashboard", icon="📊", default=True),
                st.Page("views/agenda.py", title="Agenda de prazos", icon="📅"),
                st.Page("views/cobranca.py", title="Cobrança", icon="📲"),
            ],
            "Cadastros": [
                st.Page("views/clientes.py", title="Clientes", icon="👤"),
                st.Page("views/processos.py", title="Processos e honorários", icon="📁"),
            ],
            "Financeiro": [
                st.Page("views/financeiro.py", title="Parcelas e recebimentos", icon="💰"),
            ],
            "Sistema": [
                st.Page("views/pendencias.py", title="Pendências de cadastro", icon="🧹"),
                st.Page("views/usuarios.py", title="Usuários e senha", icon="🔐"),
            ],
        }
        if ICONE.exists():
            st.logo(str(ICONE), size="large")
        pg = st.navigation(paginas)
        with st.sidebar:
            if LOGO.exists():
                st.image(str(LOGO), width="stretch")
            else:
                st.markdown(f"**⚖️ {_nome_app()}**")
            st.caption(f"Conectado como {u['nome']}")
            if s.get_bind().dialect.name == "sqlite":
                st.caption("⚠️ Banco local de teste")
            if st.button("Sair", width="stretch"):
                _sair()
                st.rerun()
        mostrar_avisos()
        pg.run()
    finally:
        s.close()


main()
