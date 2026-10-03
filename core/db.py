"""Modelos e conexão com o banco.

Produção: Supabase (Postgres) via DATABASE_URL.
Desenvolvimento: SQLite local (padrão quando DATABASE_URL não está definido).
"""
from __future__ import annotations

import os
from datetime import date, datetime
from functools import lru_cache

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
    create_engine, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

# ---------- Listas de opções (editáveis) ----------
SISTEMAS = ["PROJUDI", "PJE", "EPROC", "E-SAJ", "Outro"]
AREAS = ["Cível", "Família", "Criminal", "Trabalhista", "Previdenciário", "Tributário", "Outro"]
STATUS_PROCESSO = ["Ativo", "Suspenso", "Arquivado", "Encerrado"]
TIPOS_HONORARIO = ["Fixo", "Êxito (%)", "Fixo + Êxito", "Pro bono / sem honorário"]
TIPOS_PRAZO = ["Prazo processual", "Audiência", "Perícia", "Reunião com cliente", "Protocolo", "Outro"]
FORMAS_PAGAMENTO = ["PIX", "Dinheiro", "Transferência", "Boleto", "Cartão", "Outro"]


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(200))
    perfil: Mapped[str] = mapped_column(String(20), default="usuario")  # admin | usuario
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Cliente(Base):
    __tablename__ = "clientes"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), index=True)
    tipo_pessoa: Mapped[str] = mapped_column(String(2), default="PF")  # PF | PJ
    documento: Mapped[str | None] = mapped_column(String(14), index=True)  # só dígitos
    telefone: Mapped[str | None] = mapped_column(String(15))  # só dígitos
    email: Mapped[str | None] = mapped_column(String(160))
    endereco: Mapped[str | None] = mapped_column(String(300))
    observacoes: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    processos: Mapped[list["Processo"]] = relationship(back_populates="cliente", cascade="all, delete-orphan")


class Processo(Base):
    __tablename__ = "processos"
    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"), index=True)
    numero: Mapped[str | None] = mapped_column(String(30), index=True)  # só dígitos quando CNJ
    acao: Mapped[str] = mapped_column(String(200))
    sistema: Mapped[str | None] = mapped_column(String(30))
    area: Mapped[str] = mapped_column(String(30))
    comarca_vara: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="Ativo")
    data_inicio: Mapped[date | None] = mapped_column(Date)
    tipo_honorario: Mapped[str] = mapped_column(String(30), default="Fixo")
    valor_contratado: Mapped[float | None] = mapped_column(Numeric(12, 2))
    percentual_exito: Mapped[float | None] = mapped_column(Numeric(5, 2))
    observacoes: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    cliente: Mapped[Cliente] = relationship(back_populates="processos")
    parcelas: Mapped[list["Parcela"]] = relationship(
        back_populates="processo", cascade="all, delete-orphan", order_by="Parcela.vencimento"
    )
    prazos: Mapped[list["Prazo"]] = relationship(
        back_populates="processo", cascade="all, delete-orphan", order_by="Prazo.data"
    )


class Parcela(Base):
    __tablename__ = "parcelas"
    id: Mapped[int] = mapped_column(primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos.id", ondelete="CASCADE"), index=True)
    descricao: Mapped[str] = mapped_column(String(60))  # "Entrada", "Parcela 2/5", "Êxito"
    valor: Mapped[float] = mapped_column(Numeric(12, 2))
    vencimento: Mapped[date] = mapped_column(Date, index=True)
    data_pagamento: Mapped[date | None] = mapped_column(Date)
    valor_pago: Mapped[float | None] = mapped_column(Numeric(12, 2))
    forma_pagamento: Mapped[str | None] = mapped_column(String(30))
    observacoes: Mapped[str | None] = mapped_column(Text)

    processo: Mapped[Processo] = relationship(back_populates="parcelas")


class Prazo(Base):
    __tablename__ = "prazos"
    id: Mapped[int] = mapped_column(primary_key=True)
    processo_id: Mapped[int] = mapped_column(ForeignKey("processos.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(30), default="Prazo processual")
    descricao: Mapped[str] = mapped_column(String(200))   # ex.: "Contestação", "Audiência de conciliação"
    data: Mapped[date] = mapped_column(Date, index=True)   # data final / data do evento
    hora: Mapped[str | None] = mapped_column(String(5))   # "14:30" (audiências)
    local: Mapped[str | None] = mapped_column(String(200))
    data_intimacao: Mapped[date | None] = mapped_column(Date)
    dias_prazo: Mapped[int | None] = mapped_column(Integer)
    concluido: Mapped[bool] = mapped_column(Boolean, default=False)
    concluido_em: Mapped[date | None] = mapped_column(Date)
    observacoes: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    processo: Mapped[Processo] = relationship(back_populates="prazos")


# ---------- Conexão ----------
class ErroConfiguracao(RuntimeError):
    pass


def _url_do_arquivo_secrets() -> str | None:
    """Lê .streamlit/secrets.toml da pasta do app. Se o arquivo existir com erro, avisa em vez de
    cair silenciosamente no banco local."""
    import tomllib
    from pathlib import Path

    caminho = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    if not caminho.exists():
        return None
    try:
        with open(caminho, "rb") as f:
            dados = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ErroConfiguracao(f"Erro de digitação no arquivo .streamlit/secrets.toml: {e}. "
                               "Confira aspas e sinais de = em cada linha.") from None
    return dados.get("DATABASE_URL")


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL") or _url_do_arquivo_secrets()
    if not url:
        try:
            import streamlit as st

            url = st.secrets.get("DATABASE_URL")
        except Exception:
            url = None
    if not url:
        os.makedirs("data", exist_ok=True)
        url = "sqlite:///data/escritorio.db"
    # O Supabase entrega "postgresql://..."; o SQLAlchemy 2.1 usaria o driver psycopg (v3).
    # Padronizamos para psycopg2, que é o que está no requirements.txt.
    for prefixo in ("postgres://", "postgresql://"):
        if url.startswith(prefixo):
            url = "postgresql+psycopg2://" + url[len(prefixo):]
    return url


@lru_cache(maxsize=4)
def get_engine(url: str | None = None):
    url = url or _database_url()
    if not url.startswith(("sqlite", "postgresql")):
        raise ErroConfiguracao("DATABASE_URL deve começar com postgresql+psycopg2:// (veja o README).")
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    Base.metadata.create_all(engine)
    if engine.dialect.name == "postgresql":
        _proteger_supabase(engine)
    return engine


def _proteger_supabase(engine):
    """No Supabase, tabelas do schema public ficam expostas pela API REST (chave anon).
    Ativar RLS sem políticas bloqueia esse acesso; o app conecta como dono do banco e não é afetado."""
    from sqlalchemy import text

    with engine.begin() as con:
        for tabela in Base.metadata.tables:
            con.execute(text(f'ALTER TABLE public."{tabela}" ENABLE ROW LEVEL SECURITY'))


def get_session(url: str | None = None):
    return sessionmaker(bind=get_engine(url), expire_on_commit=False)()
