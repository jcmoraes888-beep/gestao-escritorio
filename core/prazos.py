"""Contagem de prazos processuais em dias úteis (CPC, arts. 219, 220 e 224).

Considera: fins de semana, feriados nacionais (fixos e móveis), Carnaval e o recesso forense
(20/12 a 20/01). NÃO considera feriados estaduais/municipais nem suspensões específicas do tribunal:
sempre confira no calendário do TJPR/TRT antes de confiar na data.
"""
from datetime import date, timedelta
from functools import lru_cache


def _pascoa(ano: int) -> date:
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


@lru_cache(maxsize=32)
def feriados(ano: int) -> dict[date, str]:
    p = _pascoa(ano)
    f = {
        date(ano, 1, 1): "Confraternização Universal",
        date(ano, 4, 21): "Tiradentes",
        date(ano, 5, 1): "Dia do Trabalho",
        date(ano, 9, 7): "Independência",
        date(ano, 10, 12): "Nossa Senhora Aparecida",
        date(ano, 11, 2): "Finados",
        date(ano, 11, 15): "Proclamação da República",
        date(ano, 11, 20): "Consciência Negra",
        date(ano, 12, 25): "Natal",
        p - timedelta(days=48): "Carnaval",
        p - timedelta(days=47): "Carnaval",
        p - timedelta(days=2): "Sexta-feira Santa",
        p + timedelta(days=60): "Corpus Christi",
    }
    return f


def em_recesso(d: date) -> bool:
    """Recesso forense: prazos suspensos de 20/12 a 20/01 (CPC art. 220)."""
    return (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 20)


def dia_util(d: date) -> bool:
    return d.weekday() < 5 and d not in feriados(d.year) and not em_recesso(d)


def motivo_nao_util(d: date) -> str | None:
    if d.weekday() >= 5:
        return "fim de semana"
    if d in feriados(d.year):
        return feriados(d.year)[d]
    if em_recesso(d):
        return "recesso forense"
    return None


def calcular_prazo(inicio: date, dias: int, uteis: bool = True) -> date:
    """Data final do prazo. Exclui o dia do começo e conta a partir do 1º dia útil seguinte (CPC 224).
    Em dias corridos (prazos de direito material), se cair em dia não útil, prorroga para o próximo útil."""
    if dias < 1:
        raise ValueError("O prazo precisa ter pelo menos 1 dia.")
    d = inicio
    if uteis:
        contados = 0
        while contados < dias:
            d += timedelta(days=1)
            if dia_util(d):
                contados += 1
        return d
    d = inicio + timedelta(days=dias)
    while not dia_util(d):
        d += timedelta(days=1)
    return d
