"""Validação e formatação de documentos, telefones, nº CNJ e moeda (padrão brasileiro)."""
import re
from decimal import Decimal, InvalidOperation


def so_digitos(valor) -> str:
    if valor is None or (isinstance(valor, float) and valor != valor):  # None ou NaN
        return ""
    return re.sub(r"\D", "", str(valor))


# ---------------- CPF / CNPJ ----------------
def cpf_valido(cpf: str) -> bool:
    d = so_digitos(cpf)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for i in (9, 10):
        soma = sum(int(d[n]) * ((i + 1) - n) for n in range(i))
        dv = (soma * 10) % 11 % 10
        if dv != int(d[i]):
            return False
    return True


def cnpj_valido(cnpj: str) -> bool:
    d = so_digitos(cnpj)
    if len(d) != 14 or d == d[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    for pesos, pos in ((pesos1, 12), (pesos2, 13)):
        soma = sum(int(d[n]) * pesos[n] for n in range(len(pesos)))
        resto = soma % 11
        dv = 0 if resto < 2 else 11 - resto
        if dv != int(d[pos]):
            return False
    return True


def documento_valido(doc: str) -> bool:
    d = so_digitos(doc)
    return cpf_valido(d) if len(d) == 11 else cnpj_valido(d) if len(d) == 14 else False


def formatar_documento(doc: str | None) -> str:
    d = so_digitos(doc)
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return doc or ""


def mascarar_documento(doc: str | None) -> str:
    """Exibe só parte do CPF/CNPJ em listas (LGPD): ***.528.219-**"""
    f = formatar_documento(doc)
    d = so_digitos(doc)
    if len(d) == 11:
        return f"***.{d[3:6]}.{d[6:9]}-**"
    if len(d) == 14:
        return f"**.{d[2:5]}.{d[5:8]}/{d[8:12]}-**"
    return f


# ---------------- Telefone ----------------
def telefone_valido(tel: str | None) -> bool:
    d = so_digitos(tel)
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    return len(d) in (10, 11)


def formatar_telefone(tel: str | None) -> str:
    d = so_digitos(tel)
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    if len(d) == 11:
        return f"({d[:2]}) {d[2]} {d[3:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return tel if isinstance(tel, str) else ""


def link_whatsapp(tel: str | None, mensagem: str = "") -> str | None:
    if not telefone_valido(tel):
        return None
    from urllib.parse import quote

    d = so_digitos(tel)
    if not d.startswith("55"):
        d = "55" + d
    return f"https://wa.me/{d}?text={quote(mensagem)}"


# ---------------- Nº de processo (CNJ) ----------------
# NNNNNNN-DD.AAAA.J.TR.OOOO
def processo_cnj_valido(numero: str | None) -> bool:
    d = so_digitos(numero)
    if len(d) != 20:
        return False
    nnnnnnn, dd, resto = d[:7], d[7:9], d[9:]
    # Algoritmo módulo 97 (Resolução CNJ 65/2008)
    calc = 98 - (int(nnnnnnn + resto + "00") % 97)
    return calc == int(dd)


def formatar_processo(numero: str | None) -> str:
    d = so_digitos(numero)
    if len(d) == 20:
        return f"{d[:7]}-{d[7:9]}.{d[9:13]}.{d[13]}.{d[14:16]}.{d[16:]}"
    return numero or ""


# ---------------- Moeda ----------------
def brl(valor) -> str:
    try:
        v = float(valor or 0)
    except (TypeError, ValueError):
        v = 0.0
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def para_decimal(texto) -> Decimal:
    """Aceita '2.500,00', '2500', 'R$ 35.000,00', 2500.5"""
    if texto is None or texto == "":
        return Decimal("0")
    if isinstance(texto, (int, float, Decimal)):
        return Decimal(str(texto))
    t = str(texto).replace("R$", "").strip()
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return Decimal(t)
    except InvalidOperation:
        raise ValueError(f"Valor inválido: {texto}")
