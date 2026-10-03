"""Apaga TODOS os dados do banco configurado (usuários, clientes, processos, parcelas e prazos).

Use antes de entregar o app para a cliente: depois de rodar, o app volta para a tela
"Configuração inicial", onde ela cria o próprio usuário administrador.

Uso:  python scripts/zerar_banco.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select  # noqa: E402

from core.db import Base, Cliente, Parcela, Prazo, Processo, Usuario, get_engine, get_session  # noqa: E402


def main():
    engine = get_engine()
    s = get_session()
    destino = f"{engine.dialect.name} ({engine.url.host or engine.url.database})"
    contagem = {m.__tablename__: s.scalar(select(func.count()).select_from(m))
                for m in (Usuario, Cliente, Processo, Parcela, Prazo)}
    print(f"Banco: {destino}")
    print("Registros atuais:", ", ".join(f"{k}={v}" for k, v in contagem.items()))
    resp = input('\nIsso APAGA TUDO e não tem volta. Digite APAGAR para confirmar: ').strip()
    if resp != "APAGAR":
        print("Cancelado. Nada foi apagado.")
        return
    with engine.begin() as con:
        for tabela in reversed(Base.metadata.sorted_tables):  # filhos antes dos pais
            con.execute(tabela.delete())
    print("Pronto! Banco vazio. Ao abrir o app, aparecerá a tela 'Configuração inicial'.")


if __name__ == "__main__":
    main()
