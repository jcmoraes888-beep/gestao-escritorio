"""Geração do recibo de honorários em PDF (fpdf2)."""
from __future__ import annotations

from datetime import date

from fpdf import FPDF

from . import validators as v
from .config import LOGO
from .extenso import data_extenso, reais_extenso

VINHO = (140, 15, 19)
DOURADO = (176, 137, 58)
CINZA = (90, 90, 90)


def _t(texto) -> str:
    """Fontes padrão do PDF usam latin-1: troca caracteres fora dele."""
    s = str(texto or "")
    for a, b in {"–": "-", "—": "-", "“": '"', "”": '"', "’": "'", "‘": "'", "…": "...", "•": "-"}.items():
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


def numero_recibo(parcela_id: int, data_pg: date) -> str:
    return f"{parcela_id:05d}/{data_pg.year}"


def gerar_recibo_pdf(dados: dict, escritorio: dict) -> bytes:
    """dados: cliente, documento, processo_numero, acao, descricao, valor, data_pagamento, forma, parcela_id"""
    valor = float(dados["valor"])
    dt: date = dados["data_pagamento"]
    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(False)
    pdf.add_page()
    W = pdf.w

    # Faixa superior com logo
    pdf.set_fill_color(*VINHO)
    pdf.rect(0, 0, W, 62, "F")
    if LOGO.exists():
        pdf.image(str(LOGO), x=(W - 78) / 2, y=6, w=78)
    else:
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Times", "B", 22)
        pdf.set_xy(0, 24)
        pdf.cell(W, 10, _t(escritorio["advogada"].upper()), align="C")
    pdf.set_fill_color(*DOURADO)
    pdf.rect(0, 62, W, 1.2, "F")

    # Título e número
    pdf.set_text_color(*VINHO)
    pdf.set_font("Times", "B", 22)
    pdf.set_xy(20, 74)
    pdf.cell(110, 10, _t("RECIBO DE HONORÁRIOS"))
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*CINZA)
    pdf.set_xy(20, 84)
    pdf.cell(110, 5, _t(f"Nº {numero_recibo(dados['parcela_id'], dt)}"))

    # Caixa do valor
    pdf.set_draw_color(*DOURADO)
    pdf.set_line_width(0.6)
    pdf.rect(132, 72, 58, 18)
    pdf.set_xy(132, 74)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(58, 4, "VALOR", align="C")
    pdf.set_xy(132, 79)
    pdf.set_font("Times", "B", 16)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(58, 9, _t(v.brl(valor)), align="C")

    # Corpo
    doc_cli = v.formatar_documento(dados.get("documento"))
    rotulo_doc = "CNPJ" if len(v.so_digitos(doc_cli)) == 14 else "CPF"
    pagador = dados["cliente"] + (f", inscrito(a) no {rotulo_doc} sob o nº {doc_cli}" if doc_cli else "")
    ref = f"honorários advocatícios ({dados['descricao']})"
    if dados.get("acao"):
        ref += f" referentes à ação de {dados['acao'].title()}"
    num = v.formatar_processo(dados.get("processo_numero"))
    if num:
        ref += f", processo nº {num}"
    texto = (f"Recebi de {pagador}, a importância de {v.brl(valor)} ({reais_extenso(valor)}), "
             f"referente a {ref}.")
    if dados.get("forma"):
        texto += f" Pagamento realizado via {dados['forma']}."
    texto += " Para clareza, firmo o presente recibo, dando plena e geral quitação do valor acima."

    pdf.set_xy(20, 104)
    pdf.set_font("Times", "", 13)
    pdf.set_text_color(25, 25, 25)
    pdf.multi_cell(170, 7.5, _t(texto), align="J")

    # Quadro de detalhes
    y = pdf.get_y() + 8
    linhas = [("Cliente", dados["cliente"]), (rotulo_doc, doc_cli or "-"),
              ("Processo", num or "-"), ("Ação", (dados.get("acao") or "-").title()),
              ("Referência", dados["descricao"]), ("Data do pagamento", dt.strftime("%d/%m/%Y")),
              ("Forma de pagamento", dados.get("forma") or "-")]
    pdf.set_line_width(0.2)
    pdf.set_draw_color(220, 210, 195)
    for i, (k, val) in enumerate(linhas):
        if i % 2 == 0:
            pdf.set_fill_color(250, 246, 239)
            pdf.rect(20, y, 170, 7, "F")
        pdf.set_xy(23, y + 1)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*CINZA)
        pdf.cell(45, 5, _t(k))
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(25, 25, 25)
        pdf.cell(120, 5, _t(val))
        y += 7

    # Local, data e assinatura
    y += 14
    pdf.set_xy(20, y)
    pdf.set_font("Times", "", 12)
    pdf.cell(170, 6, _t(f"{escritorio['cidade']}, {data_extenso(dt)}."), align="R")
    y += 32
    pdf.set_draw_color(40, 40, 40)
    pdf.line(60, y, 150, y)
    pdf.set_xy(20, y + 2)
    pdf.set_font("Times", "B", 12)
    pdf.cell(170, 6, _t(escritorio["advogada"]), align="C")
    pdf.set_xy(20, y + 8)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*CINZA)
    linha2 = escritorio["oab"] + (f"  |  {escritorio['documento']}" if escritorio.get("documento") else "")
    pdf.cell(170, 5, _t(linha2), align="C")

    # Rodapé
    contato = "  |  ".join(x for x in (escritorio.get("endereco"), escritorio.get("telefone"),
                                       escritorio.get("email")) if x)
    pdf.set_fill_color(*VINHO)
    pdf.rect(0, pdf.h - 16, W, 16, "F")
    pdf.set_fill_color(*DOURADO)
    pdf.rect(0, pdf.h - 16, W, 0.8, "F")
    pdf.set_text_color(240, 225, 190)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_xy(0, pdf.h - 11)
    pdf.cell(W, 5, _t(contato or f"{escritorio['advogada']}  |  Advogada  |  {escritorio['oab']}"), align="C")

    return bytes(pdf.output())
