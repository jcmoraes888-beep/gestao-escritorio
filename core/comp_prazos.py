"""Componentes de tela para prazos (usados na Agenda e na ficha do processo)."""
from datetime import date, datetime, timedelta
from urllib.parse import quote

import pandas as pd
import streamlit as st

from core import repo
from core.db import TIPOS_PRAZO, Prazo
from core.prazos import calcular_prazo, motivo_nao_util
from core.ui import data, db, linha_selecionada, tratar_erro

CORES_PRAZO = {
    "Vencido": "#ef5350",
    "Hoje": "#ffa726",
    "Próximos 7 dias": "#E2C27A",
    "Futuro": "#b0a59a",
    "Concluído": "#66bb6a",
}


def _cor(val):
    c = CORES_PRAZO.get(val)
    return f"color: {c}; font-weight: 600" if c else ""


def tabela_prazos(df: pd.DataFrame, chave: str, ocultar: list[str] | None = None):
    ocultar = list(ocultar or [])
    if "Concluído em" in df.columns and df["Concluído em"].isna().all():
        ocultar.append("Concluído em")
    vis = df.drop(columns=[c for c in ocultar if c in df.columns]).reset_index(drop=True)
    ev = st.dataframe(
        vis.style.map(_cor, subset=["Status"]), hide_index=True, width="stretch",
        on_select="rerun", selection_mode="single-row", key=chave,
        column_config={"id": None, "processo_id": None, "Data": data("Data"), "Concluído em": data("Concluído em"),
                       "Faltam (dias)": st.column_config.NumberColumn("Faltam (dias)", format="%d")},
    )
    return linha_selecionada(ev, vis)


def link_google_agenda(pz: Prazo) -> str:
    titulo = f"[{pz.tipo}] {pz.descricao} - {pz.processo.cliente.nome}"
    if pz.hora:
        ini = datetime.combine(pz.data, datetime.strptime(pz.hora, "%H:%M").time())
        datas = f"{ini:%Y%m%dT%H%M00}/{ini + timedelta(hours=1):%Y%m%dT%H%M00}"
    else:
        datas = f"{pz.data:%Y%m%d}/{pz.data + timedelta(days=1):%Y%m%d}"
    det = f"Processo: {pz.processo.numero or '-'} | Ação: {pz.processo.acao}"
    url = (f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={quote(titulo)}"
           f"&dates={datas}&details={quote(det)}&ctz=America/Sao_Paulo")
    if pz.local:
        url += f"&location={quote(pz.local)}"
    return url


def acoes_prazo(prazo_id: int, chave: str, processos: dict | None = None):
    pz = db().get(Prazo, prazo_id)
    if not pz:
        return
    st.markdown(f"**{pz.descricao}** · {pz.tipo} · {pz.data:%d/%m/%Y}{' às ' + pz.hora if pz.hora else ''} · "
                f"*{repo.status_prazo(pz)}*")
    st.caption(f"{pz.processo.cliente.nome} · {pz.processo.acao}"
               + (f" · intimação {pz.data_intimacao:%d/%m/%Y}, {pz.dias_prazo} dias" if pz.data_intimacao else "")
               + (f" · {pz.observacoes}" if pz.observacoes else ""))
    a, b, c, d = st.columns(4)
    if not pz.concluido:
        if a.button("✅ Marcar como cumprido", key=f"conc_{chave}_{pz.id}", type="primary", width="stretch"):
            tratar_erro(repo.concluir_prazo, db(), pz.id, True, sucesso="Prazo cumprido.")
            st.rerun()
    else:
        if a.button("↩️ Reabrir", key=f"reab_{chave}_{pz.id}", width="stretch"):
            tratar_erro(repo.concluir_prazo, db(), pz.id, False, sucesso="Prazo reaberto.")
            st.rerun()
    b.link_button("📅 Google Agenda", link_google_agenda(pz), width="stretch")
    editar = c.toggle("✏️ Editar", key=f"edit_tg_{chave}_{pz.id}")
    if d.button("🗑️ Excluir", key=f"del_{chave}_{pz.id}", width="stretch"):
        tratar_erro(repo.excluir_prazo, db(), pz.id, sucesso="Prazo excluído.")
        st.rerun()
    if editar:
        form_prazo(f"edit_{chave}_{pz.id}", processos=processos, prazo=pz)


def form_prazo(chave: str, processos: dict | None = None, processo_id: int | None = None,
               prazo: Prazo | None = None) -> bool:
    """Formulário com calculadora de prazo em dias úteis. Widgets fora de st.form para calcular ao vivo."""
    k = lambda n: f"{chave}_{n}"  # noqa: E731
    if processo_id is None and prazo is None:
        if not processos:
            st.warning("Cadastre um processo primeiro.")
            return False
        ids = list(processos)
        pid = st.selectbox("Processo *", ids, format_func=processos.get, key=k("proc"))
    else:
        pid = prazo.processo_id if prazo else processo_id

    a, b = st.columns([1, 2])
    tipo = a.selectbox("Tipo", TIPOS_PRAZO, key=k("tipo"),
                       index=TIPOS_PRAZO.index(prazo.tipo) if prazo and prazo.tipo in TIPOS_PRAZO else 0)
    desc = b.text_input("Descrição *", value=prazo.descricao if prazo else "", key=k("desc"),
                        placeholder="Ex.: Contestação, Réplica, Audiência de conciliação")

    calcular = st.toggle("🧮 Calcular a data pela intimação", key=k("calc"),
                         value=bool(prazo and prazo.data_intimacao) if prazo else tipo == "Prazo processual")
    data_final, intim, dias = (prazo.data if prazo else date.today()), None, None
    if calcular:
        a, b, c = st.columns(3)
        intim = a.date_input("Data da intimação/publicação", format="DD/MM/YYYY", key=k("intim"),
                             value=prazo.data_intimacao if prazo and prazo.data_intimacao else date.today())
        dias = b.number_input("Prazo (dias)", min_value=1, max_value=365, key=k("dias"),
                              value=int(prazo.dias_prazo) if prazo and prazo.dias_prazo else 15)
        contagem = c.radio("Contagem", ["Dias úteis", "Dias corridos"], horizontal=True, key=k("cont"))
        data_final = calcular_prazo(intim, int(dias), uteis=contagem == "Dias úteis")
        st.info(f"Prazo final: **{data_final:%d/%m/%Y}** ({['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom'][data_final.weekday()]}). "
                "Conta a partir do 1º dia útil após a intimação, sem fins de semana, feriados nacionais e recesso "
                "(20/12 a 20/01). **Confira feriados locais e suspensões do tribunal.**")
    else:
        data_final = st.date_input("Data *", value=data_final, format="DD/MM/YYYY", key=k("data"))
        if motivo := motivo_nao_util(data_final):
            st.warning(f"Atenção: {data_final:%d/%m/%Y} não é dia útil ({motivo}).")

    a, b = st.columns([1, 2])
    hora = a.text_input("Hora", value=(prazo.hora or "") if prazo else "", placeholder="14:30", key=k("hora"))
    local = b.text_input("Local / link", value=(prazo.local or "") if prazo else "", key=k("local"),
                         placeholder="Ex.: Fórum de Cascavel, sala 3 ou link da videoconferência")
    obs = st.text_input("Observações", value=(prazo.observacoes or "") if prazo else "", key=k("obs"))
    if st.button("💾 Salvar prazo", type="primary", key=k("salvar")):
        ok, _ = tratar_erro(repo.salvar_prazo, db(), {
            "processo_id": pid, "tipo": tipo, "descricao": desc, "data": data_final, "hora": hora, "local": local,
            "data_intimacao": intim if calcular else None, "dias_prazo": int(dias) if calcular and dias else None,
            "observacoes": obs,
        }, prazo.id if prazo else None, sucesso="Prazo salvo.")
        if ok:
            for key in [x for x in st.session_state if str(x).startswith(chave)]:
                del st.session_state[key]
            st.rerun()
    return False
