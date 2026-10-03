"""Dados do escritório usados em recibos e no app.

Podem ser sobrescritos em .streamlit/secrets.toml, seção [escritorio].
"""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOGO = RAIZ / "assets" / "logo_completo.png"
ICONE = RAIZ / "assets" / "icone.png"

PADRAO = {
    "nome_app": "Lesly Vargas Advocacia",
    "advogada": "Lesly Vargas",
    "oab": "OAB/PR 132.199",
    "cidade": "Cascavel/PR",
    "documento": "",   # CPF/CNPJ de quem emite o recibo (opcional)
    "endereco": "",
    "telefone": "",
    "email": "",
}


def escritorio() -> dict:
    dados = dict(PADRAO)
    try:
        import streamlit as st

        if "NOME_ESCRITORIO" in st.secrets:
            dados["nome_app"] = st.secrets["NOME_ESCRITORIO"]
        if "escritorio" in st.secrets:
            dados.update({k: str(v) for k, v in st.secrets["escritorio"].items()})
    except Exception:
        pass
    return dados
