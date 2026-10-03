"""Usuários, senhas (bcrypt), bloqueio por tentativas e código de ativação."""
import hmac
import os
from datetime import datetime, timedelta, timezone

import bcrypt
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .db import TentativaLogin, Usuario
from .repo import ErroValidacao

MAX_TENTATIVAS = 5
BLOQUEIO_MIN = 15
CHAVE_ATIVACAO = "__ativacao__"  # tentativas do código de ativação usam esta "conta"


class ErroBloqueio(ErroValidacao):
    pass


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def conferir_senha(senha: str, hash_: str) -> bool:
    try:
        return bcrypt.checkpw((senha or "").encode(), hash_.encode())
    except ValueError:
        return False


# ---------------- Bloqueio por tentativas ----------------
def minutos_bloqueado(s: Session, chave: str) -> int:
    """Quantos minutos faltam para liberar (0 = liberado)."""
    desde = _agora() - timedelta(minutes=BLOQUEIO_MIN)
    tentativas = s.scalars(select(TentativaLogin.quando)
                           .where(TentativaLogin.email == chave, TentativaLogin.quando >= desde)
                           .order_by(TentativaLogin.quando)).all()
    if len(tentativas) < MAX_TENTATIVAS:
        return 0
    libera = tentativas[-MAX_TENTATIVAS] + timedelta(minutes=BLOQUEIO_MIN)
    return max(1, int((libera - _agora()).total_seconds() // 60) + 1)


def _registrar_falha(s: Session, chave: str):
    s.add(TentativaLogin(email=chave, quando=_agora()))
    # limpeza de registros antigos
    s.execute(delete(TentativaLogin).where(TentativaLogin.quando < _agora() - timedelta(days=7)))
    s.commit()


def _limpar_falhas(s: Session, chave: str):
    s.execute(delete(TentativaLogin).where(TentativaLogin.email == chave))
    s.commit()


def _checar_bloqueio(s: Session, chave: str):
    if (m := minutos_bloqueado(s, chave)):
        raise ErroBloqueio(f"Muitas tentativas erradas. Tente de novo em {m} minuto(s).")


# ---------------- Usuários ----------------
def existe_usuario(s: Session) -> bool:
    return (s.scalar(select(func.count(Usuario.id))) or 0) > 0


def criar_usuario(s: Session, nome: str, email: str, senha: str, perfil: str = "usuario") -> Usuario:
    email = (email or "").strip().lower()
    if not (nome or "").strip() or "@" not in email:
        raise ErroValidacao("Informe nome e e-mail válidos.")
    if len(senha or "") < 8:
        raise ErroValidacao("A senha precisa ter pelo menos 8 caracteres.")
    if s.scalar(select(Usuario).where(Usuario.email == email)):
        raise ErroValidacao("Já existe um usuário com este e-mail.")
    u = Usuario(nome=nome.strip(), email=email, senha_hash=hash_senha(senha), perfil=perfil)
    s.add(u)
    s.commit()
    return u


def autenticar(s: Session, email: str, senha: str) -> Usuario | None:
    """Retorna o usuário se a senha conferir. Levanta ErroBloqueio após muitas falhas."""
    chave = (email or "").strip().lower()
    _checar_bloqueio(s, chave)
    u = s.scalar(select(Usuario).where(Usuario.email == chave, Usuario.ativo.is_(True)))
    if u and conferir_senha(senha, u.senha_hash):
        _limpar_falhas(s, chave)
        return u
    _registrar_falha(s, chave)
    return None


def trocar_senha(s: Session, usuario_id: int, nova: str):
    if len(nova or "") < 8:
        raise ErroValidacao("A senha precisa ter pelo menos 8 caracteres.")
    u = s.get(Usuario, usuario_id)
    u.senha_hash = hash_senha(nova)
    s.commit()


# ---------------- Código de ativação ----------------
def codigo_ativacao_configurado() -> str | None:
    cod = os.environ.get("CODIGO_ATIVACAO")
    if not cod:
        try:
            import streamlit as st
            cod = st.secrets.get("CODIGO_ATIVACAO")
        except Exception:
            cod = None
    return str(cod).strip() if cod else None


def conferir_codigo_ativacao(s: Session, informado: str, esperado: str):
    _checar_bloqueio(s, CHAVE_ATIVACAO)
    if not hmac.compare_digest((informado or "").strip().encode(), esperado.encode()):
        _registrar_falha(s, CHAVE_ATIVACAO)
        raise ErroValidacao("Código de ativação incorreto.")
    _limpar_falhas(s, CHAVE_ATIVACAO)


def criar_primeiro_admin(s: Session, nome, email, senha, codigo_informado, exigir_codigo: bool) -> Usuario:
    if existe_usuario(s):
        raise ErroValidacao("O administrador já foi criado. Faça login.")
    if exigir_codigo:
        esperado = codigo_ativacao_configurado()
        if not esperado:
            raise ErroValidacao("Configure CODIGO_ATIVACAO nos Secrets antes de criar o administrador.")
        conferir_codigo_ativacao(s, codigo_informado, esperado)
    return criar_usuario(s, nome, email, senha, "admin")
