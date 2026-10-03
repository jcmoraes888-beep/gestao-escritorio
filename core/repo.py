"""Regras de negócio e consultas. Não depende do Streamlit (testável)."""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import validators as v
from .db import Cliente, Parcela, Processo

DIAS_ALERTA = 7
CENT = Decimal("0.01")


class ErroValidacao(ValueError):
    pass


def _limpo(x):
    if isinstance(x, str):
        x = x.strip()
        return x or None
    return x


def _bate(busca: str, campos: list) -> bool:
    """Busca por texto (sem diferenciar maiúsculas) ou por dígitos (CPF, telefone, nº processo)."""
    b = busca.strip().lower()
    dig = v.so_digitos(busca)
    for campo in campos:
        if not campo:
            continue
        if b in str(campo).lower():
            return True
        if len(dig) >= 3 and dig in v.so_digitos(str(campo)):
            return True
    return False


def add_meses(d: date, meses: int) -> date:
    m = d.month - 1 + meses
    ano, mes = d.year + m // 12, m % 12 + 1
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


# =============================== CLIENTES ===============================
def salvar_cliente(s: Session, dados: dict, cliente_id: int | None = None) -> Cliente:
    nome = _limpo(dados.get("nome"))
    if not nome:
        raise ErroValidacao("Informe o nome do cliente.")
    doc = v.so_digitos(dados.get("documento"))
    tipo = dados.get("tipo_pessoa") or ("PJ" if len(doc) == 14 else "PF")
    if doc:
        if tipo == "PF" and not v.cpf_valido(doc):
            raise ErroValidacao("CPF inválido. Confira os dígitos.")
        if tipo == "PJ" and not v.cnpj_valido(doc):
            raise ErroValidacao("CNPJ inválido. Confira os dígitos.")
        dup = s.scalar(select(Cliente).where(Cliente.documento == doc, Cliente.id != (cliente_id or 0)))
        if dup:
            raise ErroValidacao(f"Já existe um cliente com este documento: {dup.nome}.")
    tel = v.so_digitos(dados.get("telefone"))
    if tel and not v.telefone_valido(tel):
        raise ErroValidacao("Telefone incompleto. Use DDD + número, ex.: (45) 9 9999-9999.")

    c = s.get(Cliente, cliente_id) if cliente_id else Cliente()
    c.nome = nome.upper()
    c.tipo_pessoa = tipo
    c.documento = doc or None
    c.telefone = tel or None
    c.email = _limpo(dados.get("email"))
    c.endereco = _limpo(dados.get("endereco"))
    c.observacoes = _limpo(dados.get("observacoes"))
    c.ativo = bool(dados.get("ativo", True))
    s.add(c)
    s.commit()
    return c


def excluir_cliente(s: Session, cliente_id: int):
    c = s.get(Cliente, cliente_id)
    if c:
        s.delete(c)
        s.commit()


def df_clientes(s: Session, busca: str = "", apenas_ativos: bool = True) -> pd.DataFrame:
    s.expire_all()  # garante dados atualizados
    q = select(Cliente).options(selectinload(Cliente.processos).selectinload(Processo.parcelas))
    if apenas_ativos:
        q = q.where(Cliente.ativo.is_(True))
    hoje = date.today()
    linhas = []
    for c in s.scalars(q.order_by(Cliente.nome)):
        if busca and not _bate(busca, [c.nome, c.documento, c.telefone] + [p.numero for p in c.processos]):
            continue
        parcelas = [pa for p in c.processos for pa in p.parcelas]
        aberto = sum(float(pa.valor) for pa in parcelas if not pa.data_pagamento)
        atrasado = sum(float(pa.valor) for pa in parcelas if not pa.data_pagamento and pa.vencimento < hoje)
        linhas.append({
            "id": c.id,
            "Cliente": c.nome,
            "Tipo": c.tipo_pessoa,
            "CPF/CNPJ": v.mascarar_documento(c.documento),
            "Telefone": v.formatar_telefone(c.telefone),
            "Processos": len(c.processos),
            "Em aberto": aberto,
            "Em atraso": atrasado,
            "Ativo": c.ativo,
        })
    return pd.DataFrame(linhas, columns=["id", "Cliente", "Tipo", "CPF/CNPJ", "Telefone", "Processos",
                                         "Em aberto", "Em atraso", "Ativo"])


# =============================== PROCESSOS ===============================
def salvar_processo(s: Session, dados: dict, processo_id: int | None = None) -> Processo:
    if not dados.get("cliente_id"):
        raise ErroValidacao("Selecione o cliente.")
    if not _limpo(dados.get("acao")):
        raise ErroValidacao("Informe a ação/tipo do processo.")
    if not dados.get("area"):
        raise ErroValidacao("Informe a área.")
    numero_txt = _limpo(dados.get("numero"))
    numero = None
    if numero_txt:
        dig = v.so_digitos(numero_txt)
        if len(dig) == 20:
            if not v.processo_cnj_valido(dig):
                raise ErroValidacao("Número CNJ com dígito verificador inválido. Confira o número.")
            numero = dig
        else:
            numero = numero_txt  # processos antigos / administrativos
        dup = s.scalar(select(Processo).where(Processo.numero == numero, Processo.id != (processo_id or 0)))
        if dup:
            raise ErroValidacao("Já existe um processo cadastrado com este número.")

    tipo = dados.get("tipo_honorario") or "Fixo"
    valor = v.para_decimal(dados.get("valor_contratado")) if dados.get("valor_contratado") not in (None, "") else None
    perc = v.para_decimal(dados.get("percentual_exito")) if dados.get("percentual_exito") not in (None, "") else None
    if tipo in ("Fixo", "Fixo + Êxito") and not valor:
        raise ErroValidacao("Informe o valor fixo contratado.")
    if tipo in ("Êxito (%)", "Fixo + Êxito") and not perc:
        raise ErroValidacao("Informe o percentual de êxito.")
    if perc is not None and not (0 < perc <= 100):
        raise ErroValidacao("Percentual de êxito deve estar entre 0 e 100.")

    p = s.get(Processo, processo_id) if processo_id else Processo()
    p.cliente_id = int(dados["cliente_id"])
    p.numero = numero
    p.acao = _limpo(dados.get("acao")).upper()
    p.sistema = dados.get("sistema")
    p.area = dados["area"]
    p.comarca_vara = _limpo(dados.get("comarca_vara"))
    p.status = dados.get("status") or "Ativo"
    p.data_inicio = dados.get("data_inicio")
    p.tipo_honorario = tipo
    p.valor_contratado = valor if tipo in ("Fixo", "Fixo + Êxito") else None
    p.percentual_exito = perc if tipo in ("Êxito (%)", "Fixo + Êxito") else None
    p.observacoes = _limpo(dados.get("observacoes"))
    s.add(p)
    s.commit()
    return p


def excluir_processo(s: Session, processo_id: int):
    p = s.get(Processo, processo_id)
    if p:
        s.delete(p)
        s.commit()


def df_processos(s: Session, cliente_id: int | None = None, area: str | None = None,
                 status: str | None = None, busca: str = "") -> pd.DataFrame:
    s.expire_all()  # garante dados atualizados
    q = select(Processo).options(selectinload(Processo.cliente), selectinload(Processo.parcelas))
    if cliente_id:
        q = q.where(Processo.cliente_id == cliente_id)
    if area:
        q = q.where(Processo.area == area)
    if status:
        q = q.where(Processo.status == status)
    linhas = []
    for p in s.scalars(q):
        if busca and not _bate(busca, [p.cliente.nome, p.acao, p.numero]):
            continue
        pago = sum(float(pa.valor_pago or 0) for pa in p.parcelas if pa.data_pagamento)
        aberto = sum(float(pa.valor) for pa in p.parcelas if not pa.data_pagamento)
        linhas.append({
            "id": p.id,
            "Cliente": p.cliente.nome,
            "Nº processo": v.formatar_processo(p.numero) or "—",
            "Ação": p.acao,
            "Área": p.area,
            "Sistema": p.sistema or "",
            "Status": p.status,
            "Honorário": descrever_honorario(p),
            "Recebido": pago,
            "Em aberto": aberto,
        })
    df = pd.DataFrame(linhas, columns=["id", "Cliente", "Nº processo", "Ação", "Área", "Sistema", "Status",
                                       "Honorário", "Recebido", "Em aberto"])
    return df.sort_values(["Cliente", "Ação"]).reset_index(drop=True) if not df.empty else df


def descrever_honorario(p: Processo) -> str:
    if p.tipo_honorario == "Fixo":
        return v.brl(p.valor_contratado)
    if p.tipo_honorario == "Êxito (%)":
        return f"{float(p.percentual_exito or 0):g}% do êxito"
    if p.tipo_honorario == "Fixo + Êxito":
        return f"{v.brl(p.valor_contratado)} + {float(p.percentual_exito or 0):g}% do êxito"
    return "Sem honorário"


# =============================== PARCELAS ===============================
def gerar_parcelas(s: Session, processo_id: int, valor_total, n_parcelas: int, primeiro_vencimento: date,
                   entrada=0, data_entrada: date | None = None, substituir_pendentes: bool = True) -> list[Parcela]:
    """Cria a entrada (opcional) + N parcelas mensais. Ajusta centavos na última parcela."""
    total = v.para_decimal(valor_total)
    ent = v.para_decimal(entrada)
    if total <= 0:
        raise ErroValidacao("Valor total deve ser maior que zero.")
    if ent < 0 or ent > total:
        raise ErroValidacao("Entrada deve estar entre zero e o valor total.")
    restante = total - ent
    if restante > 0 and n_parcelas < 1:
        raise ErroValidacao("Informe ao menos 1 parcela para o saldo.")

    if substituir_pendentes:
        pendentes = s.scalars(select(Parcela).where(Parcela.processo_id == processo_id,
                                                    Parcela.data_pagamento.is_(None)))
        for pa in pendentes:
            s.delete(pa)
        s.flush()

    novas = []
    if ent > 0:
        novas.append(Parcela(processo_id=processo_id, descricao="Entrada", valor=ent,
                             vencimento=data_entrada or date.today()))
    if restante > 0:
        base = (restante / n_parcelas).quantize(CENT, rounding=ROUND_HALF_UP)
        for i in range(n_parcelas):
            valor = base if i < n_parcelas - 1 else restante - base * (n_parcelas - 1)
            novas.append(Parcela(processo_id=processo_id, descricao=f"Parcela {i + 1}/{n_parcelas}",
                                 valor=valor, vencimento=add_meses(primeiro_vencimento, i)))
    s.add_all(novas)
    s.commit()
    return novas


def adicionar_parcela(s: Session, processo_id: int, descricao: str, valor, vencimento: date) -> Parcela:
    val = v.para_decimal(valor)
    if val <= 0:
        raise ErroValidacao("Valor deve ser maior que zero.")
    pa = Parcela(processo_id=processo_id, descricao=_limpo(descricao) or "Avulsa", valor=val, vencimento=vencimento)
    s.add(pa)
    s.commit()
    return pa


def lancar_exito(s: Session, processo_id: int, valor_obtido, vencimento: date) -> Parcela:
    """Calcula os honorários de êxito sobre o valor obtido (acordo/sentença) e cria a parcela."""
    p = s.get(Processo, processo_id)
    if not p.percentual_exito:
        raise ErroValidacao("Este processo não tem percentual de êxito cadastrado.")
    base = v.para_decimal(valor_obtido)
    honor = (base * Decimal(str(p.percentual_exito)) / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    return adicionar_parcela(s, processo_id, f"Êxito {float(p.percentual_exito):g}% s/ {v.brl(base)}", honor, vencimento)


def registrar_pagamento(s: Session, parcela_id: int, data_pagamento: date, valor_pago, forma: str | None = None,
                        gerar_saldo: bool = True) -> Parcela | None:
    """Baixa a parcela. Se pago menos que o devido, cria uma parcela com o saldo restante."""
    pa = s.get(Parcela, parcela_id)
    pago = v.para_decimal(valor_pago)
    if pago <= 0:
        raise ErroValidacao("Valor pago deve ser maior que zero.")
    devido = Decimal(str(pa.valor))
    saldo = None
    if pago < devido and gerar_saldo:
        saldo = Parcela(processo_id=pa.processo_id, descricao=f"Saldo de {pa.descricao}"[:60],
                        valor=devido - pago, vencimento=max(pa.vencimento, data_pagamento))
        pa.valor = pago
        s.add(saldo)
    pa.data_pagamento = data_pagamento
    pa.valor_pago = pago
    pa.forma_pagamento = forma
    s.commit()
    return saldo


def estornar_pagamento(s: Session, parcela_id: int):
    pa = s.get(Parcela, parcela_id)
    pa.data_pagamento = None
    pa.valor_pago = None
    pa.forma_pagamento = None
    s.commit()


def excluir_parcela(s: Session, parcela_id: int):
    pa = s.get(Parcela, parcela_id)
    if pa:
        s.delete(pa)
        s.commit()


def status_parcela(pa: Parcela, hoje: date | None = None) -> str:
    hoje = hoje or date.today()
    if pa.data_pagamento:
        return "Paga"
    if pa.vencimento < hoje:
        return "Atrasada"
    if pa.vencimento <= hoje + timedelta(days=DIAS_ALERTA):
        return "Vence em breve"
    return "A vencer"


def df_parcelas(s: Session, processo_id: int | None = None, hoje: date | None = None) -> pd.DataFrame:
    s.expire_all()  # garante dados atualizados
    hoje = hoje or date.today()
    q = select(Parcela).options(selectinload(Parcela.processo).selectinload(Processo.cliente))
    if processo_id:
        q = q.where(Parcela.processo_id == processo_id)
    linhas = []
    for pa in s.scalars(q.order_by(Parcela.vencimento)):
        c = pa.processo.cliente
        linhas.append({
            "id": pa.id,
            "processo_id": pa.processo_id,
            "cliente_id": c.id,
            "Cliente": c.nome,
            "Telefone": c.telefone,
            "Ação": pa.processo.acao,
            "Área": pa.processo.area,
            "Nº processo": v.formatar_processo(pa.processo.numero) or "—",
            "Descrição": pa.descricao,
            "Valor": float(pa.valor),
            "Vencimento": pa.vencimento,
            "Status": status_parcela(pa, hoje),
            "Dias de atraso": (hoje - pa.vencimento).days if not pa.data_pagamento and pa.vencimento < hoje else 0,
            "Pago em": pa.data_pagamento,
            "Valor pago": float(pa.valor_pago) if pa.valor_pago is not None else None,
            "Forma": pa.forma_pagamento,
        })
    cols = ["id", "processo_id", "cliente_id", "Cliente", "Telefone", "Ação", "Área", "Nº processo", "Descrição",
            "Valor", "Vencimento", "Status", "Dias de atraso", "Pago em", "Valor pago", "Forma"]
    return pd.DataFrame(linhas, columns=cols)


# =============================== DASHBOARD ===============================
def resumo(s: Session, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    dfp = df_parcelas(s, hoje=hoje)
    clientes = s.scalars(select(Cliente).where(Cliente.ativo.is_(True))).all()
    processos = s.scalars(select(Processo)).all()
    abertas = dfp[dfp["Status"] != "Paga"]
    pagas = dfp[dfp["Status"] == "Paga"]
    inicio_mes = hoje.replace(day=1)
    fim_mes = add_meses(inicio_mes, 1) - timedelta(days=1)
    return {
        "clientes_ativos": len(clientes),
        "processos_ativos": sum(1 for p in processos if p.status == "Ativo"),
        "exito_pendente": sum(1 for p in processos if p.percentual_exito and p.status == "Ativo"),
        "recebido_total": float(pagas["Valor pago"].sum()) if not pagas.empty else 0.0,
        "recebido_mes": float(pagas[(pagas["Pago em"] >= inicio_mes) & (pagas["Pago em"] <= hoje)]["Valor pago"].sum())
        if not pagas.empty else 0.0,
        "a_receber": float(abertas["Valor"].sum()),
        "a_receber_mes": float(abertas[abertas["Vencimento"] <= fim_mes]["Valor"].sum()) if not abertas.empty else 0.0,
        "atrasado": float(abertas[abertas["Status"] == "Atrasada"]["Valor"].sum()),
        "qtd_atrasadas": int((abertas["Status"] == "Atrasada").sum()),
        "clientes_inadimplentes": abertas[abertas["Status"] == "Atrasada"]["cliente_id"].nunique(),
        "parcelas": dfp,
    }


def fluxo_mensal(dfp: pd.DataFrame, hoje: date | None = None, meses_atras: int = 5, meses_frente: int = 6) -> pd.DataFrame:
    """Recebido por mês (passado) e previsto por mês (futuro, pelo vencimento)."""
    hoje = hoje or date.today()
    inicio = add_meses(hoje.replace(day=1), -meses_atras)
    meses = [add_meses(inicio, i) for i in range(meses_atras + meses_frente + 1)]
    linhas = []
    for m in meses:
        prox = add_meses(m, 1)
        rec = dfp[(dfp["Status"] == "Paga") & dfp["Pago em"].apply(lambda d: d is not None and m <= d < prox)]
        prev = dfp[(dfp["Status"] != "Paga") & dfp["Vencimento"].apply(lambda d: m <= d < prox)]
        linhas.append({"Mês": m.strftime("%m/%Y"), "Recebido": float(rec["Valor pago"].sum()),
                       "Previsto em aberto": float(prev["Valor"].sum())})
    return pd.DataFrame(linhas)


def pendencias_cadastro(s: Session) -> pd.DataFrame:
    s.expire_all()  # garante dados atualizados
    linhas = []
    for c in s.scalars(select(Cliente).options(selectinload(Cliente.processos)).where(Cliente.ativo.is_(True))):
        if not c.documento:
            linhas.append({"Cliente": c.nome, "Onde": "Cliente", "Pendência": "Sem CPF/CNPJ"})
        if not c.telefone:
            linhas.append({"Cliente": c.nome, "Onde": "Cliente", "Pendência": "Sem telefone"})
        if not c.processos:
            linhas.append({"Cliente": c.nome, "Onde": "Cliente", "Pendência": "Nenhum processo cadastrado"})
        for p in c.processos:
            ref = f"Processo: {p.acao}"
            if not p.numero:
                linhas.append({"Cliente": c.nome, "Onde": ref, "Pendência": "Sem número do processo"})
            if not p.sistema:
                linhas.append({"Cliente": c.nome, "Onde": ref, "Pendência": "Sem sistema (PROJUDI/PJE…)"})
            if p.tipo_honorario in ("Fixo", "Fixo + Êxito") and not p.parcelas and p.status == "Ativo":
                linhas.append({"Cliente": c.nome, "Onde": ref, "Pendência": "Honorário fixo sem parcelas geradas"})
    return pd.DataFrame(linhas, columns=["Cliente", "Onde", "Pendência"])


# =============================== RECIBO ===============================
def dados_recibo(s: Session, parcela_id: int) -> dict:
    pa = s.get(Parcela, parcela_id)
    if not pa or not pa.data_pagamento:
        raise ErroValidacao("Só é possível emitir recibo de parcela paga.")
    p, c = pa.processo, pa.processo.cliente
    return {
        "parcela_id": pa.id, "cliente": c.nome, "documento": c.documento, "processo_numero": p.numero,
        "acao": p.acao, "descricao": pa.descricao, "valor": float(pa.valor_pago or pa.valor),
        "data_pagamento": pa.data_pagamento, "forma": pa.forma_pagamento,
    }


# =============================== PRAZOS ===============================
def salvar_prazo(s: Session, dados: dict, prazo_id: int | None = None) -> "Prazo":
    from .db import Prazo

    if not dados.get("processo_id"):
        raise ErroValidacao("Selecione o processo.")
    if not _limpo(dados.get("descricao")):
        raise ErroValidacao("Descreva o prazo (ex.: Contestação, Audiência de conciliação).")
    if not dados.get("data"):
        raise ErroValidacao("Informe a data do prazo.")
    hora = _limpo(dados.get("hora"))
    if hora:
        import re
        if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", hora):
            raise ErroValidacao("Hora inválida. Use o formato 14:30.")
        hora = hora.zfill(5)
    pz = s.get(Prazo, prazo_id) if prazo_id else Prazo()
    pz.processo_id = int(dados["processo_id"])
    pz.tipo = dados.get("tipo") or "Prazo processual"
    pz.descricao = _limpo(dados["descricao"])
    pz.data = dados["data"]
    pz.hora = hora
    pz.local = _limpo(dados.get("local"))
    pz.data_intimacao = dados.get("data_intimacao")
    pz.dias_prazo = dados.get("dias_prazo")
    pz.observacoes = _limpo(dados.get("observacoes"))
    s.add(pz)
    s.commit()
    return pz


def concluir_prazo(s: Session, prazo_id: int, concluido: bool = True, quando: date | None = None):
    from .db import Prazo

    pz = s.get(Prazo, prazo_id)
    pz.concluido = concluido
    pz.concluido_em = (quando or date.today()) if concluido else None
    s.commit()


def excluir_prazo(s: Session, prazo_id: int):
    from .db import Prazo

    pz = s.get(Prazo, prazo_id)
    if pz:
        s.delete(pz)
        s.commit()


def status_prazo(pz, hoje: date | None = None) -> str:
    hoje = hoje or date.today()
    if pz.concluido:
        return "Concluído"
    if pz.data < hoje:
        return "Vencido"
    if pz.data == hoje:
        return "Hoje"
    if pz.data <= hoje + timedelta(days=DIAS_ALERTA):
        return "Próximos 7 dias"
    return "Futuro"


def df_prazos(s: Session, processo_id: int | None = None, hoje: date | None = None) -> pd.DataFrame:
    from .db import Prazo

    s.expire_all()
    hoje = hoje or date.today()
    q = select(Prazo).options(selectinload(Prazo.processo).selectinload(Processo.cliente))
    if processo_id:
        q = q.where(Prazo.processo_id == processo_id)
    dias_sem = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
    linhas = []
    for pz in s.scalars(q.order_by(Prazo.data, Prazo.hora)):
        p = pz.processo
        linhas.append({
            "id": pz.id, "processo_id": p.id,
            "Data": pz.data,
            "Dia": dias_sem[pz.data.weekday()],
            "Hora": pz.hora or "",
            "Status": status_prazo(pz, hoje),
            "Faltam (dias)": (pz.data - hoje).days if not pz.concluido else None,
            "Tipo": pz.tipo,
            "Descrição": pz.descricao,
            "Cliente": p.cliente.nome,
            "Ação": p.acao,
            "Nº processo": v.formatar_processo(p.numero) or "—",
            "Local": pz.local or "",
            "Concluído em": pz.concluido_em,
        })
    cols = ["id", "processo_id", "Data", "Dia", "Hora", "Status", "Faltam (dias)", "Tipo", "Descrição", "Cliente",
            "Ação", "Nº processo", "Local", "Concluído em"]
    return pd.DataFrame(linhas, columns=cols)
