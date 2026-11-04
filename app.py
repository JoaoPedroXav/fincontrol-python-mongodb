"""Interface Streamlit do FinControl."""

from __future__ import annotations

from datetime import date

import streamlit as st

from database import (
    CATEGORIES, TYPES, create_transaction, delete_transaction, format_brl,
    get_client, get_totals, initialize_database, list_transactions,
    to_cents, update_transaction, validate_transaction,
)

st.set_page_config(page_title="FinControl", page_icon="💸", layout="wide")
st.markdown("""
<style>
  .stApp { background: #f7f8fb; color: #17223b; }
  .block-container { max-width: 1180px; padding-top: 2rem; }
  h1, h2, h3 { color: #17223b; letter-spacing: -.025em; }
  div[data-testid="stMetric"] { background: white; padding: 1.3rem 1.5rem;
    border: 1px solid #e7ebf2; border-radius: 16px; box-shadow: 0 4px 18px #1d2b4c08; }
  div[data-testid="stMetricValue"] { font-weight: 700; }
  .subtle { color: #65708a; margin-top: -.6rem; }
  .section { margin-top: 1.2rem; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="Conectando ao MongoDB Atlas...")
def collection():
    client = get_client()
    return initialize_database(client)


def display_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            "Data": row["data"].strftime("%d/%m/%Y"),
            "Descrição": row["descricao"],
            "Tipo": row["tipo"],
            "Categoria": row["categoria"],
            "Valor": format_brl(row["valor_centavos"]),
        }
        for row in rows
    ]


def transaction_options(rows: list[dict]) -> dict[str, dict]:
    return {
        f'{row["data"].strftime("%d/%m/%Y")} · {row["descricao"]} · {format_brl(row["valor_centavos"])} · {str(row["_id"])[-6:]}': row
        for row in rows
    }


def save_form(prefix: str, row: dict | None = None) -> dict | None:
    default_date = row["data"].date() if row else date.today()
    description = st.text_input("Descrição *", value=row["descricao"] if row else "", max_chars=120, key=f"{prefix}_description")
    c1, c2 = st.columns(2)
    with c1:
        kind = st.selectbox("Tipo *", TYPES, index=TYPES.index(row["tipo"]) if row else 0, key=f"{prefix}_kind")
    with c2:
        category = st.selectbox("Categoria *", CATEGORIES, index=CATEGORIES.index(row["categoria"]) if row else 0, key=f"{prefix}_category")
    c3, c4 = st.columns(2)
    with c3:
        value = st.number_input("Valor (R$) *", min_value=0.01, value=row["valor_centavos"] / 100 if row else 0.01, step=0.01, format="%.2f", key=f"{prefix}_value")
    with c4:
        transaction_date = st.date_input("Data *", value=default_date, format="DD/MM/YYYY", key=f"{prefix}_date")
    note = st.text_area("Observação", value=row.get("observacao", "") if row else "", max_chars=1000, key=f"{prefix}_note")
    if st.form_submit_button("Salvar transação", type="primary", use_container_width=True):
        try:
            return validate_transaction(description, kind, category, value, transaction_date, note)
        except ValueError as exc:
            st.error(str(exc))
    return None


def show_dashboard(db):
    totals = get_totals(db)
    c1, c2, c3 = st.columns(3)
    c1.metric("Receitas", format_brl(totals["receitas"]))
    c2.metric("Despesas", format_brl(totals["despesas"]))
    c3.metric("Saldo", format_brl(totals["saldo"]))
    st.subheader("Transações recentes")
    recent = list_transactions(db, limit=8)
    if recent:
        st.dataframe(display_rows(recent), hide_index=True, use_container_width=True)
    else:
        st.info("Nenhuma transação cadastrada. Comece pela aba Transações.")


FILTER_DEFAULTS = {
    "filter_kind": "Todos", "filter_category": "Todas", "filter_start_enabled": False,
    "filter_end_enabled": False, "filter_min_enabled": False, "filter_max_enabled": False,
    "filter_description": "", "filter_order": "Mais recentes",
}


def clear_filters():
    for key, value in FILTER_DEFAULTS.items():
        st.session_state[key] = value


def show_filters() -> tuple[dict, bool]:
    st.subheader("Consultar e filtrar")
    c1, c2, c3 = st.columns(3)
    with c1:
        kind = st.selectbox("Tipo", ["Todos", *TYPES], key="filter_kind")
        start_enabled = st.checkbox("Usar data inicial", key="filter_start_enabled")
        start = st.date_input("Data inicial", value=date.today(), format="DD/MM/YYYY", key="filter_start", disabled=not start_enabled)
        min_enabled = st.checkbox("Usar valor mínimo", key="filter_min_enabled")
        minimum = st.number_input("Valor mínimo (R$)", min_value=0.0, step=0.01, format="%.2f", key="filter_min", disabled=not min_enabled)
    with c2:
        category = st.selectbox("Categoria", ["Todas", *CATEGORIES], key="filter_category")
        end_enabled = st.checkbox("Usar data final", key="filter_end_enabled")
        end = st.date_input("Data final", value=date.today(), format="DD/MM/YYYY", key="filter_end", disabled=not end_enabled)
        max_enabled = st.checkbox("Usar valor máximo", key="filter_max_enabled")
        maximum = st.number_input("Valor máximo (R$)", min_value=0.0, step=0.01, format="%.2f", key="filter_max", disabled=not max_enabled)
    with c3:
        description = st.text_input("Buscar na descrição", key="filter_description")
        order = st.selectbox("Ordenar por data", ["Mais recentes", "Mais antigas"], key="filter_order")
        st.write("")
        st.button("Limpar filtros", use_container_width=True, on_click=clear_filters)
    filters = {
        "kind": None if kind == "Todos" else kind,
        "category": None if category == "Todas" else category,
        "start_date": start if start_enabled else None,
        "end_date": end if end_enabled else None,
        "min_cents": to_cents(minimum) if min_enabled and minimum > 0 else (0 if min_enabled else None),
        "max_cents": to_cents(maximum) if max_enabled and maximum > 0 else (0 if max_enabled else None),
        "description": description,
    }
    return filters, order == "Mais recentes"


def show_transactions(db):
    create_tab, browse_tab = st.tabs(["Nova transação", "Consultar e gerenciar"])
    with create_tab:
        with st.form("create_form", clear_on_submit=True):
            transaction = save_form("create")
        if transaction:
            create_transaction(db, transaction)
            st.success("Transação cadastrada no MongoDB Atlas.")
    with browse_tab:
        filters, descending = show_filters()
        try:
            rows = list_transactions(db, filters, descending=descending)
        except ValueError as exc:
            st.error(str(exc))
            return
        st.caption(f"{len(rows)} transação(ões) exibida(s), limite de 500 registros.")
        if not rows:
            st.info("Nenhuma transação encontrada para estes filtros.")
            return
        st.dataframe(display_rows(rows), hide_index=True, use_container_width=True)
        options = transaction_options(rows)
        selected = options[st.selectbox("Selecione para ver detalhes, editar ou excluir", list(options))]
        with st.expander("Detalhes", expanded=True):
            st.write(f'**Descrição:** {selected["descricao"]}')
            st.write(f'**Tipo e categoria:** {selected["tipo"]} · {selected["categoria"]}')
            st.write(f'**Valor:** {format_brl(selected["valor_centavos"])}')
            st.write(f'**Data:** {selected["data"].strftime("%d/%m/%Y")}')
            st.write(f'**Observação:** {selected.get("observacao") or "—"}')
            st.caption(f'ID: {selected["_id"]}')
        edit_tab, delete_tab = st.tabs(["Editar", "Excluir"])
        with edit_tab:
            with st.form(f'edit_form_{selected["_id"]}'):
                updated = save_form(f'edit_{selected["_id"]}', selected)
            if updated:
                if update_transaction(db, selected["_id"], updated):
                    st.success("Transação atualizada.")
                    st.rerun()
                else:
                    st.error("Transação não encontrada.")
        with delete_tab:
            st.warning("A exclusão é permanente.")
            confirmed = st.checkbox("Confirmo que desejo excluir esta transação", key=f'confirm_{selected["_id"]}')
            if st.button("Excluir transação", disabled=not confirmed, type="primary"):
                if delete_transaction(db, selected["_id"]):
                    st.success("Transação excluída.")
                    st.rerun()
                else:
                    st.error("Transação não encontrada.")


st.title("FinControl")
st.markdown('<p class="subtle">Suas finanças, organizadas em um só lugar.</p>', unsafe_allow_html=True)
try:
    db = collection()
except Exception as exc:
    st.error("Não foi possível conectar ao MongoDB Atlas. Confira MONGODB_URI, acesso de rede e permissões do usuário do banco.")
    st.code(str(exc))
    st.stop()

dashboard_tab, transactions_tab = st.tabs(["Dashboard", "Transações"])
with dashboard_tab:
    show_dashboard(db)
with transactions_tab:
    show_transactions(db)
