"""Backup completo em Excel (uma aba por tabela). Não inclui hashes de senha."""
import io
from datetime import datetime

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

TABELAS = {
    "Clientes": "select * from clientes order by nome",
    "Processos": "select * from processos order by id",
    "Parcelas": "select * from parcelas order by vencimento",
    "Prazos": "select * from prazos order by data",
    "Usuarios": "select id, nome, email, perfil, ativo, criado_em from usuarios order by nome",
}


def gerar_backup_xlsx(s: Session) -> tuple[bytes, dict]:
    buf = io.BytesIO()
    contagem = {}
    with s.get_bind().connect() as con, pd.ExcelWriter(buf, engine="openpyxl") as w:
        for aba, sql in TABELAS.items():
            df = pd.read_sql(text(sql), con)
            contagem[aba] = len(df)
            df.to_excel(w, sheet_name=aba, index=False)
        pd.DataFrame([{"Gerado em": datetime.now().strftime("%d/%m/%Y %H:%M"),
                       **{f"Qtd. {k}": v for k, v in contagem.items()}}]).to_excel(w, sheet_name="Info", index=False)
    return buf.getvalue(), contagem
