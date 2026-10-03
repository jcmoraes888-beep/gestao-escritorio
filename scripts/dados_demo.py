"""Popula o banco com dados FICTÍCIOS para demonstração/treinamento.

Uso:  python scripts/dados_demo.py            (usa DATABASE_URL ou SQLite local)
NÃO rode no banco de produção do escritório.
"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import auth, repo  # noqa: E402
from core.db import get_session  # noqa: E402


def gerar_cpf(rnd):
    n = [rnd.randint(0, 9) for _ in range(9)]
    for i in (9, 10):
        s = sum(n[k] * ((i + 1) - k) for k in range(i))
        n.append((s * 10) % 11 % 10)
    return "".join(map(str, n))


def gerar_cnj(rnd, ano, j, tr, orgao):
    seq = f"{rnd.randint(1, 9999999):07d}"
    resto = f"{ano}{j}{tr:02d}{orgao:04d}"
    dv = 98 - (int(seq + resto + "00") % 97)
    return f"{seq}{dv:02d}{resto}"


def main():
    rnd = random.Random(42)
    s = get_session()
    if not auth.existe_usuario(s):
        auth.criar_usuario(s, "Administrador Demo", "admin@demo.com", "demo12345", "admin")
        print("Usuário criado: admin@demo.com / demo12345")

    nomes = ["ANA PAULA SOUZA", "BRUNO HENRIQUE LIMA", "CARLA MENDES ROCHA", "DIEGO FERREIRA ALVES",
             "ELAINE CRISTINA MOURA", "FABIO RODRIGUES NUNES", "GABRIELA SANTOS PIRES", "HUGO MARTINS COSTA",
             "IARA BEATRIZ CAMPOS", "JULIO CESAR TEIXEIRA"]
    acoes = [("PENSÃO ALIMENTÍCIA", "Família", "PROJUDI"), ("EXECUÇÃO", "Cível", "PROJUDI"),
             ("DANOS MORAIS", "Cível", "PROJUDI"), ("RECLAMATÓRIA TRABALHISTA", "Trabalhista", "PJE"),
             ("DIVÓRCIO CONSENSUAL", "Família", "PROJUDI"), ("DEFESA CRIMINAL", "Criminal", "PROJUDI")]
    hoje = date.today()
    for i, nome in enumerate(nomes):
        c = repo.salvar_cliente(s, {"nome": nome, "documento": gerar_cpf(rnd) if i != 7 else "",
                                    "telefone": f"45999{rnd.randint(100000, 999999)}" if i != 4 else ""})
        for _ in range(rnd.choice([1, 1, 2])):
            acao, area, sist = rnd.choice(acoes)
            tr = 9 if area == "Trabalhista" else 16
            j = 5 if area == "Trabalhista" else 8
            numero = gerar_cnj(rnd, rnd.choice([2024, 2025, 2026]), j, tr, 21) if rnd.random() > 0.15 else ""
            if area == "Trabalhista":
                p = repo.salvar_processo(s, {"cliente_id": c.id, "numero": numero, "acao": acao, "area": area,
                                             "sistema": sist, "tipo_honorario": "Êxito (%)", "percentual_exito": 30})
                continue
            valor = rnd.choice([1500, 2500, 3500, 5000, 8000, 35000])
            p = repo.salvar_processo(s, {"cliente_id": c.id, "numero": numero, "acao": acao, "area": area,
                                         "sistema": sist, "tipo_honorario": "Fixo", "valor_contratado": valor})
            inicio = hoje - timedelta(days=rnd.randint(30, 200))
            n = rnd.choice([1, 3, 4, 6, 10])
            entrada = round(valor * rnd.choice([0, 0.2, 0.3]))
            parcelas = repo.gerar_parcelas(s, p.id, valor, n, repo.add_meses(inicio, 1), entrada, inicio)
            for pa in parcelas:
                if pa.vencimento < hoje and rnd.random() < 0.75:
                    repo.registrar_pagamento(s, pa.id, pa.vencimento + timedelta(days=rnd.randint(0, 5)),
                                             pa.valor, rnd.choice(["PIX", "PIX", "Dinheiro"]))
    # Prazos de exemplo
    from sqlalchemy import select
    from core.db import Processo
    from core.prazos import calcular_prazo
    exemplos = [("Prazo processual", "Contestação", 15), ("Prazo processual", "Réplica", 15),
                ("Prazo processual", "Manifestação sobre laudo", 5), ("Audiência", "Audiência de conciliação", None),
                ("Prazo processual", "Recurso de apelação", 15), ("Reunião com cliente", "Assinar procuração", None)]
    for p in s.scalars(select(Processo)).all():
        tipo, desc, dias = rnd.choice(exemplos)
        if dias:
            intim = hoje - timedelta(days=rnd.randint(0, 25))
            dados = {"data": calcular_prazo(intim, dias), "data_intimacao": intim, "dias_prazo": dias}
        else:
            dados = {"data": hoje + timedelta(days=rnd.randint(-2, 20)), "hora": rnd.choice(["09:00", "14:30", "16:00"]),
                     "local": "Fórum de Cascavel" if tipo == "Audiência" else "Escritório"}
        pz = repo.salvar_prazo(s, {"processo_id": p.id, "tipo": tipo, "descricao": desc, **dados})
        if pz.data < hoje and rnd.random() < 0.6:
            repo.concluir_prazo(s, pz.id, True, pz.data)
    print("Dados de demonstração criados.")


if __name__ == "__main__":
    main()
