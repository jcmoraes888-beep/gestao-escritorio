"""Valores e datas por extenso em português (para recibos)."""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

_UNID = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze",
         "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
_DEZ = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
_CEM = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos",
        "oitocentos", "novecentos"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]


def _ate_mil(n: int) -> str:
    if n == 100:
        return "cem"
    c, r = divmod(n, 100)
    partes = []
    if c:
        partes.append(_CEM[c])
    if r:
        if r < 20:
            partes.append(_UNID[r])
        else:
            d, u = divmod(r, 10)
            partes.append(_DEZ[d] + (f" e {_UNID[u]}" if u else ""))
    return " e ".join(partes)


def inteiro_extenso(n: int) -> str:
    if n == 0:
        return "zero"
    grupos = []
    while n:
        n, g = divmod(n, 1000)
        grupos.append(g)
    nomes = [("", ""), ("mil", "mil"), ("milhão", "milhões"), ("bilhão", "bilhões")]
    partes = []
    for i in range(len(grupos) - 1, -1, -1):
        g = grupos[i]
        if not g:
            continue
        if i == 1 and g == 1:
            txt = "mil"
        else:
            txt = _ate_mil(g)
            if i:
                txt += " " + (nomes[i][0] if g == 1 else nomes[i][1])
        partes.append((g, txt))
    # Regra do "e": usa "e" antes do último grupo se ele for < 100 ou múltiplo de 100
    out = partes[0][1]
    for g, txt in partes[1:]:
        out += (" e " if g < 100 or g % 100 == 0 else " ") + txt
    return out


def reais_extenso(valor) -> str:
    v = Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    reais = int(v)
    cent = int((v - reais) * 100)
    partes = []
    if reais:
        txt = inteiro_extenso(reais)
        # "um milhão de reais", "dois mil reais"
        sufixo = "real" if reais == 1 else "reais"
        if reais % 1_000_000 == 0:
            sufixo = "de " + sufixo
        partes.append(f"{txt} {sufixo}")
    if cent:
        partes.append(f"{inteiro_extenso(cent)} {'centavo' if cent == 1 else 'centavos'}")
    return " e ".join(partes) if partes else "zero real"


def data_extenso(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"
