"""Persistência e consultas do FinControl no MongoDB Atlas."""

from __future__ import annotations

import os
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient

load_dotenv()

DATABASE_NAME = os.getenv("MONGODB_DATABASE", "controle_financeiro")
COLLECTION_NAME = "transacoes"
TYPES = ("Receita", "Despesa")
CATEGORIES = (
    "Alimentação", "Transporte", "Moradia", "Saúde", "Educação",
    "Lazer", "Salário", "Outros",
)


def get_client() -> MongoClient:
    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri:
        raise RuntimeError("Defina MONGODB_URI no arquivo .env para conectar ao MongoDB Atlas.")
    return MongoClient(uri, serverSelectionTimeoutMS=8000, tz_aware=True)


def get_collection(client: MongoClient | None = None):
    client = client or get_client()
    return client[DATABASE_NAME][COLLECTION_NAME]


def initialize_database(client: MongoClient | None = None):
    client = client or get_client()
    client.admin.command("ping")
    database = client[DATABASE_NAME]
    if COLLECTION_NAME not in database.list_collection_names():
        database.create_collection(COLLECTION_NAME)
    collection = database[COLLECTION_NAME]
    collection.create_index([("data", DESCENDING)], name="data_desc")
    collection.create_index([("tipo", ASCENDING), ("categoria", ASCENDING), ("data", DESCENDING)], name="filtros_principais")
    collection.create_index([("valor_centavos", ASCENDING)], name="valor_asc")
    return collection


def to_cents(value: Any) -> int:
    try:
        amount = Decimal(str(value).replace(",", "."))
        cents = int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Informe um valor monetário válido.") from exc
    if not amount.is_finite() or cents <= 0:
        raise ValueError("O valor deve ser maior que zero.")
    if amount.as_tuple().exponent < -2:
        raise ValueError("Use no máximo duas casas decimais.")
    if cents > 9_223_372_036_854_775_807:
        raise ValueError("O valor excede o limite suportado pelo banco.")
    return cents


def format_brl(cents: int) -> str:
    reais, centavos = divmod(abs(cents), 100)
    value = f"{reais:,}".replace(",", ".") + f",{centavos:02d}"
    return f"{'-' if cents < 0 else ''}R$ {value}"


def validate_transaction(description: str, kind: str, category: str, value: Any, transaction_date: date, note: str = "") -> dict:
    description = description.strip()
    if not description:
        raise ValueError("A descrição é obrigatória.")
    if len(description) > 120:
        raise ValueError("A descrição deve ter até 120 caracteres.")
    if kind not in TYPES:
        raise ValueError("Selecione um tipo válido.")
    if category not in CATEGORIES:
        raise ValueError("Selecione uma categoria válida.")
    if not isinstance(transaction_date, date):
        raise ValueError("Informe uma data válida.")
    if len(note) > 1000:
        raise ValueError("A observação deve ter até 1000 caracteres.")
    return {
        "descricao": description,
        "tipo": kind,
        "categoria": category,
        "valor_centavos": to_cents(value),
        "data": datetime.combine(transaction_date, time.min, tzinfo=timezone.utc),
        "observacao": note.strip(),
    }


def create_transaction(collection, transaction: dict) -> ObjectId:
    return collection.insert_one(transaction).inserted_id


def list_transactions(collection, filters: dict | None = None, *, limit: int = 500, descending: bool = True) -> list[dict]:
    query = build_query(**(filters or {}))
    direction = DESCENDING if descending else ASCENDING
    return list(collection.find(query).sort([("data", direction), ("_id", direction)]).limit(limit))


def get_transaction(collection, transaction_id: str | ObjectId) -> dict | None:
    return collection.find_one({"_id": ObjectId(transaction_id)})


def update_transaction(collection, transaction_id: str | ObjectId, transaction: dict) -> bool:
    result = collection.update_one({"_id": ObjectId(transaction_id)}, {"$set": transaction})
    return result.matched_count == 1


def delete_transaction(collection, transaction_id: str | ObjectId) -> bool:
    return collection.delete_one({"_id": ObjectId(transaction_id)}).deleted_count == 1


def build_query(
    kind: str | None = None,
    category: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    min_cents: int | None = None,
    max_cents: int | None = None,
    description: str | None = None,
) -> dict:
    if start_date and end_date and start_date > end_date:
        raise ValueError("A data inicial deve ser anterior à data final.")
    if min_cents is not None and max_cents is not None and min_cents > max_cents:
        raise ValueError("O valor mínimo deve ser menor ou igual ao máximo.")
    query: dict[str, Any] = {}
    if kind:
        query["tipo"] = kind
    if category:
        query["categoria"] = category
    if start_date or end_date:
        query["data"] = {}
        if start_date:
            query["data"]["$gte"] = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        if end_date:
            query["data"]["$lt"] = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    if min_cents is not None or max_cents is not None:
        query["valor_centavos"] = {}
        if min_cents is not None:
            query["valor_centavos"]["$gte"] = min_cents
        if max_cents is not None:
            query["valor_centavos"]["$lte"] = max_cents
    if description and description.strip():
        query["descricao"] = {"$regex": re.escape(description.strip()), "$options": "i"}
    return query


def get_totals(collection) -> dict[str, int]:
    pipeline = [{"$group": {"_id": "$tipo", "total": {"$sum": "$valor_centavos"}}}]
    amounts = {row["_id"]: row["total"] for row in collection.aggregate(pipeline)}
    income = amounts.get("Receita", 0)
    expense = amounts.get("Despesa", 0)
    return {"receitas": income, "despesas": expense, "saldo": income - expense}
