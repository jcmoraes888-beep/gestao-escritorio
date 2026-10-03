"""Usuários e senhas (bcrypt)."""
import bcrypt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import Usuario
from .repo import ErroValidacao


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def conferir_senha(senha: str, hash_: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode(), hash_.encode())
    except ValueError:
        return False


def existe_usuario(s: Session) -> bool:
    return (s.scalar(select(func.count(Usuario.id))) or 0) > 0


def criar_usuario(s: Session, nome: str, email: str, senha: str, perfil: str = "usuario") -> Usuario:
    email = (email or "").strip().lower()
    if not nome or "@" not in email:
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
    u = s.scalar(select(Usuario).where(Usuario.email == (email or "").strip().lower(), Usuario.ativo.is_(True)))
    if u and conferir_senha(senha, u.senha_hash):
        return u
    return None


def trocar_senha(s: Session, usuario_id: int, nova: str):
    if len(nova or "") < 8:
        raise ErroValidacao("A senha precisa ter pelo menos 8 caracteres.")
    u = s.get(Usuario, usuario_id)
    u.senha_hash = hash_senha(nova)
    s.commit()
