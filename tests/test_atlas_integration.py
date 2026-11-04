"""Testes reais: requerem MONGODB_URI e removem apenas registros com marcador único."""

import os
import unittest
from datetime import date
from uuid import uuid4

from database import (
    create_transaction, delete_transaction, get_client, get_totals,
    initialize_database, list_transactions, update_transaction,
    validate_transaction,
)


@unittest.skipUnless(os.getenv("MONGODB_URI", "").strip(), "MONGODB_URI não configurada")
class AtlasIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = get_client()
        cls.collection = initialize_database(cls.client)  # ping, coleção e índices reais
        cls.marker = f"FINCONTROL_TEST_{uuid4().hex}"
        cls.ids = []

    @classmethod
    def tearDownClass(cls):
        # A limpeza só alcança registros criados por esta execução.
        cls.collection.delete_many({"observacao": cls.marker})
        cls.client.close()

    def test_crud_filters_and_totals(self):
        before = get_totals(self.collection)
        income = validate_transaction("Salário teste", "Receita", "Salário", "150.00", date(2026, 11, 1), self.marker)
        expense = validate_transaction("Mercado teste", "Despesa", "Alimentação", "25.50", date(2026, 11, 2), self.marker)
        income_id = create_transaction(self.collection, income)
        expense_id = create_transaction(self.collection, expense)
        self.ids.extend([income_id, expense_id])

        self.assertEqual(self.collection.find_one({"_id": income_id})["descricao"], "Salário teste")
        self.assertEqual(self.collection.find_one({"_id": expense_id})["descricao"], "Mercado teste")
        self.assertTrue(any(row["_id"] == income_id for row in list_transactions(self.collection, {"description": "Salário teste"})))

        cases = [
            {"category": "Alimentação"},
            {"kind": "Despesa"},
            {"start_date": date(2026, 11, 2), "end_date": date(2026, 11, 2)},
            {"min_cents": 2500, "max_cents": 2600},
            {"kind": "Despesa", "category": "Alimentação", "start_date": date(2026, 11, 2),
             "end_date": date(2026, 11, 2), "min_cents": 2500, "max_cents": 2600,
             "description": "Mercado"},
        ]
        for filters in cases:
            with self.subTest(filters=filters):
                self.assertTrue(any(row["_id"] == expense_id for row in list_transactions(self.collection, filters)))

        during = get_totals(self.collection)
        self.assertEqual(during["receitas"] - before["receitas"], 15000)
        self.assertEqual(during["despesas"] - before["despesas"], 2550)
        self.assertEqual(during["saldo"] - before["saldo"], 12450)

        changed = validate_transaction("Mercado atualizado", "Despesa", "Alimentação", "30.00", date(2026, 11, 2), self.marker)
        self.assertTrue(update_transaction(self.collection, expense_id, changed))
        self.assertEqual(self.collection.find_one({"_id": expense_id})["valor_centavos"], 3000)
        self.assertTrue(delete_transaction(self.collection, expense_id))
        self.assertIsNone(self.collection.find_one({"_id": expense_id}))
        self.assertTrue(delete_transaction(self.collection, income_id))
        self.assertIsNone(self.collection.find_one({"_id": income_id}))


if __name__ == "__main__":
    unittest.main()
