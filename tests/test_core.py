from datetime import date, timedelta
from decimal import Decimal

import pytest

from core import auth, repo
from core import validators as v
from core.db import get_session


@pytest.fixture
def s(tmp_path):
    return get_session(f"sqlite:///{tmp_path}/t.db")


# CPF/CNPJ gerados para teste (válidos, fictícios)
CPF_OK = "529.982.247-25"
CNPJ_OK = "11.222.333/0001-81"
CNJ_OK = "0059403-39.2025.8.16.0021"


def test_validadores():
    assert v.cpf_valido(CPF_OK) and not v.cpf_valido("529.982.247-24") and not v.cpf_valido("111.111.111-11")
    assert v.cnpj_valido(CNPJ_OK) and not v.cnpj_valido("11.222.333/0001-80")
    assert v.processo_cnj_valido(CNJ_OK)
    assert not v.processo_cnj_valido("0059403-38.2025.8.16.0021")
    assert v.formatar_processo(v.so_digitos(CNJ_OK)) == CNJ_OK
    assert v.formatar_telefone("45998887777") == "(45) 9 9888-7777"
    assert not v.telefone_valido("(45) 9")
    assert v.link_whatsapp("45998887777", "Olá").startswith("https://wa.me/5545998887777?text=Ol")
    assert v.para_decimal("R$ 35.000,00") == Decimal("35000.00")
    assert v.para_decimal("2500") == Decimal("2500")
    assert v.brl(1234.5) == "R$ 1.234,50"
    assert v.mascarar_documento("52998224725") == "***.982.247-**"


def test_cliente_validacao(s):
    with pytest.raises(repo.ErroValidacao):
        repo.salvar_cliente(s, {"nome": "X", "documento": "123"})
    with pytest.raises(repo.ErroValidacao):
        repo.salvar_cliente(s, {"nome": "X", "telefone": "(45) 9"})
    c = repo.salvar_cliente(s, {"nome": "maria teste", "documento": CPF_OK, "telefone": "45 99888-7777"})
    assert c.nome == "MARIA TESTE" and c.documento == "52998224725"
    with pytest.raises(repo.ErroValidacao, match="Já existe"):
        repo.salvar_cliente(s, {"nome": "Outra", "documento": CPF_OK})
    pj = repo.salvar_cliente(s, {"nome": "Empresa", "documento": CNPJ_OK})
    assert pj.tipo_pessoa == "PJ"
    assert len(repo.df_clientes(s, busca="maria")) == 1
    assert len(repo.df_clientes(s, busca="982.247")) == 1


def _proc(s, **kw):
    c = repo.salvar_cliente(s, {"nome": "Cliente"})
    base = {"cliente_id": c.id, "acao": "Execução", "area": "Cível", "sistema": "PROJUDI",
            "tipo_honorario": "Fixo", "valor_contratado": "35.000,00", "numero": CNJ_OK}
    base.update(kw)
    return repo.salvar_processo(s, base)


def test_processo_e_parcelas(s):
    with pytest.raises(repo.ErroValidacao, match="dígito"):
        _proc(s, numero="0059403-38.2025.8.16.0021")
    p = _proc(s)
    assert p.numero == v.so_digitos(CNJ_OK)
    parc = repo.gerar_parcelas(s, p.id, "35000", 3, date(2026, 1, 31), entrada="10000", data_entrada=date(2026, 1, 10))
    assert [x.descricao for x in parc] == ["Entrada", "Parcela 1/3", "Parcela 2/3", "Parcela 3/3"]
    assert sum(Decimal(str(x.valor)) for x in parc) == Decimal("35000")
    assert parc[2].vencimento == date(2026, 2, 28)  # fim de mês ajustado
    # Pagamento parcial gera saldo
    saldo = repo.registrar_pagamento(s, parc[1].id, date(2026, 2, 1), "5000", "PIX")
    assert saldo is not None and float(saldo.valor) == pytest.approx(3333.33)
    df = repo.df_parcelas(s, hoje=date(2026, 3, 15))
    assert (df["Status"] == "Paga").sum() == 1
    assert df["Valor"].sum() == pytest.approx(35000)
    r = repo.resumo(s, hoje=date(2026, 3, 15))
    assert r["recebido_total"] == 5000 and r["a_receber"] == pytest.approx(30000)
    assert r["qtd_atrasadas"] == 3  # entrada (10/01), saldo (31/01) e parcela 2 (28/02)
    # Regerar substitui só pendentes
    repo.gerar_parcelas(s, p.id, "20000", 2, date(2026, 4, 10))
    df2 = repo.df_parcelas(s)
    assert len(df2) == 3 and (df2["Status"] == "Paga").sum() == 1
    repo.estornar_pagamento(s, parc[1].id)
    assert (repo.df_parcelas(s)["Status"] == "Paga").sum() == 0
    fm = repo.fluxo_mensal(repo.df_parcelas(s), hoje=date(2026, 3, 15))
    assert len(fm) == 12


def test_exito(s):
    with pytest.raises(repo.ErroValidacao):
        _proc(s, tipo_honorario="Êxito (%)", valor_contratado=None, numero=None)
    p = _proc(s, tipo_honorario="Êxito (%)", percentual_exito="30", numero=None)
    assert p.valor_contratado is None
    pa = repo.lancar_exito(s, p.id, "3.500,00", date(2026, 5, 1))
    assert float(pa.valor) == 1050.0
    assert "30%" in repo.descrever_honorario(p)


def test_pendencias(s):
    c = repo.salvar_cliente(s, {"nome": "Sem dados"})
    repo.salvar_processo(s, {"cliente_id": c.id, "acao": "Ação", "area": "Família",
                             "tipo_honorario": "Fixo", "valor_contratado": "1500"})
    pend = repo.pendencias_cadastro(s)["Pendência"].tolist()
    assert "Sem CPF/CNPJ" in pend and "Sem número do processo" in pend
    assert "Honorário fixo sem parcelas geradas" in pend


def test_auth(s):
    assert not auth.existe_usuario(s)
    with pytest.raises(repo.ErroValidacao):
        auth.criar_usuario(s, "Adv", "adv@x.com", "curta")
    auth.criar_usuario(s, "Adv", "ADV@x.com", "senha-forte-1", "admin")
    assert auth.autenticar(s, "adv@x.com", "senha-forte-1")
    assert auth.autenticar(s, "adv@x.com", "errada") is None


def test_prazos(s):
    from core.prazos import calcular_prazo, dia_util
    # intimação sexta 02/10/2026; 12/10 é feriado -> 15 dias úteis terminam em 26/10
    assert calcular_prazo(date(2026, 10, 2), 15) == date(2026, 10, 26)
    # recesso forense suspende de 20/12 a 20/01
    assert calcular_prazo(date(2026, 12, 15), 15) == date(2027, 2, 5)
    # dias corridos que caem no sábado vão para segunda
    assert calcular_prazo(date(2026, 10, 2), 1, uteis=False) == date(2026, 10, 5)
    assert not dia_util(date(2026, 4, 3))  # Sexta-feira Santa 2026
    assert not dia_util(date(2026, 2, 17))  # Carnaval 2026
    p = _proc(s, numero=None)
    with pytest.raises(repo.ErroValidacao):
        repo.salvar_prazo(s, {"processo_id": p.id, "descricao": "X", "data": date(2026, 10, 9), "hora": "25:00"})
    pz = repo.salvar_prazo(s, {"processo_id": p.id, "descricao": "Contestação", "data": date(2026, 10, 9), "hora": "9:30"})
    assert pz.hora == "09:30"
    hoje = date(2026, 10, 5)
    assert repo.df_prazos(s, hoje=hoje)["Status"].iloc[0] == "Próximos 7 dias"
    assert repo.df_prazos(s, hoje=date(2026, 10, 10))["Status"].iloc[0] == "Vencido"
    repo.concluir_prazo(s, pz.id)
    assert repo.df_prazos(s)["Status"].iloc[0] == "Concluído"


def test_recibo(s):
    from core.config import PADRAO
    from core.extenso import reais_extenso
    from core.recibo import gerar_recibo_pdf
    assert reais_extenso(1250.01) == "mil duzentos e cinquenta reais e um centavo"
    assert reais_extenso(35000) == "trinta e cinco mil reais"
    assert reais_extenso(1) == "um real"
    p = _proc(s)
    pa = repo.gerar_parcelas(s, p.id, "1000", 1, date(2026, 10, 1))[0]
    with pytest.raises(repo.ErroValidacao):
        repo.dados_recibo(s, pa.id)
    repo.registrar_pagamento(s, pa.id, date(2026, 10, 2), "1000", "PIX")
    pdf = gerar_recibo_pdf(repo.dados_recibo(s, pa.id), PADRAO)
    assert pdf[:4] == b"%PDF" and len(pdf) > 5000


def test_bloqueio_e_ativacao(s, monkeypatch):
    auth.criar_usuario(s, "Adv", "a@x.com", "senha-forte-1", "admin")
    for _ in range(auth.MAX_TENTATIVAS):
        assert auth.autenticar(s, "a@x.com", "errada") is None
    with pytest.raises(auth.ErroBloqueio):
        auth.autenticar(s, "a@x.com", "senha-forte-1")  # bloqueado mesmo com a senha certa
    # e-mail inexistente também conta (não revela quais e-mails existem)
    for _ in range(auth.MAX_TENTATIVAS):
        auth.autenticar(s, "nao@existe.com", "x")
    assert auth.minutos_bloqueado(s, "nao@existe.com") > 0


def test_primeiro_admin_exige_codigo(s, monkeypatch):
    monkeypatch.delenv("CODIGO_ATIVACAO", raising=False)
    with pytest.raises(repo.ErroValidacao, match="Configure"):
        auth.criar_primeiro_admin(s, "A", "a@x.com", "senha-forte-1", "", exigir_codigo=True)
    monkeypatch.setenv("CODIGO_ATIVACAO", "LV-2026-abc")
    with pytest.raises(repo.ErroValidacao, match="incorreto"):
        auth.criar_primeiro_admin(s, "A", "a@x.com", "senha-forte-1", "chute", exigir_codigo=True)
    u = auth.criar_primeiro_admin(s, "A", "a@x.com", "senha-forte-1", " LV-2026-abc ", exigir_codigo=True)
    assert u.perfil == "admin"
    with pytest.raises(repo.ErroValidacao, match="já foi criado"):
        auth.criar_primeiro_admin(s, "B", "b@x.com", "senha-forte-1", "LV-2026-abc", exigir_codigo=True)


def test_backup(s):
    from core.backup import gerar_backup_xlsx
    c = repo.salvar_cliente(s, {"nome": "Fulano"})
    auth.criar_usuario(s, "Adv", "a@x.com", "senha-forte-1")
    dados, cont = gerar_backup_xlsx(s)
    assert dados[:2] == b"PK" and cont["Clientes"] == 1 and cont["Usuarios"] == 1
    import io, pandas as pd
    assert "senha_hash" not in pd.read_excel(io.BytesIO(dados), sheet_name="Usuarios").columns
