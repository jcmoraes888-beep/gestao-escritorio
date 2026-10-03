"""Utilitários de interface compartilhados pelas páginas."""
import streamlit as st

CORES_STATUS = {
    "Paga": "#66bb6a",
    "A vencer": "#90a4ae",
    "Vence em breve": "#ffa726",
    "Atrasada": "#ef5350",
}


def db():
    """Sessão do banco aberta para esta execução (criada em app.py)."""
    return st.session_state["_db"]


def usuario():
    return st.session_state.get("usuario")


def avisar(msg: str, icone: str = "✅"):
    """Mostra um toast após o próximo rerun."""
    st.session_state["_toast"] = (msg, icone)


def mostrar_avisos():
    if t := st.session_state.pop("_toast", None):
        st.toast(t[0], icon=t[1])


def moeda(label: str):
    """Coluna de valor. A formatação R$ 1.234,56 vem de estilo_moeda()."""
    return st.column_config.Column(label)


def estilo_moeda(df, colunas):
    """Formata colunas em reais (padrão brasileiro) mantendo a ordenação numérica."""
    from core.validators import brl
    import pandas as pd

    cols = [c for c in colunas if c in df.columns]
    return df.style.format({c: (lambda x: brl(x) if pd.notna(x) else "") for c in cols})


def data(label: str):
    return st.column_config.DateColumn(label, format="DD/MM/YYYY")


def colorir_status(val):
    cor = CORES_STATUS.get(val)
    return f"color: {cor}; font-weight: 600" if cor else ""


def linha_selecionada(evento, df):
    """Retorna a linha (Series) selecionada num st.dataframe com on_select, ou None."""
    try:
        linhas = evento.selection.rows
    except AttributeError:
        return None
    if linhas and not df.empty:
        return df.iloc[linhas[0]]
    return None


def tratar_erro(func, *args, sucesso: str | None = None, **kwargs):
    """Executa uma ação; mostra erro de validação amigável. Retorna (ok, resultado)."""
    from core.repo import ErroValidacao

    try:
        res = func(*args, **kwargs)
    except ErroValidacao as e:
        db().rollback()
        st.error(str(e))
        return False, None
    except Exception as e:  # erro inesperado: não perder a sessão
        db().rollback()
        st.error(f"Erro inesperado: {e}")
        return False, None
    if sucesso:
        avisar(sucesso)
    return True, res
