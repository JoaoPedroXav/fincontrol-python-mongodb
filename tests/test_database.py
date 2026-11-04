import unittest
from datetime import date, datetime, timezone

from database import build_query, format_brl, to_cents, validate_transaction


class DatabaseUnitTests(unittest.TestCase):
    def test_cents_and_brazilian_format(self):
        self.assertEqual(to_cents("1234,56"), 123456)
        self.assertEqual(format_brl(123456), "R$ 1.234,56")
        self.assertEqual(format_brl(-100), "-R$ 1,00")
        self.assertEqual(format_brl(123456789012345), "R$ 1.234.567.890.123,45")
        with self.assertRaises(ValueError):
            to_cents("1,234")
        with self.assertRaises(ValueError):
            to_cents(0)

    def test_validation_and_utc_date(self):
        row = validate_transaction(" Salário ", "Receita", "Salário", "1000.00", date(2026, 11, 4))
        self.assertEqual(row["descricao"], "Salário")
        self.assertEqual(row["valor_centavos"], 100000)
        self.assertEqual(row["data"], datetime(2026, 11, 4, tzinfo=timezone.utc))
        with self.assertRaises(ValueError):
            validate_transaction(" ", "Receita", "Salário", 10, date.today())

    def test_combined_query_is_sent_to_mongodb(self):
        query = build_query(
            kind="Despesa", category="Alimentação",
            start_date=date(2026, 11, 1), end_date=date(2026, 11, 4),
            min_cents=1000, max_cents=5000, description="café.*",
        )
        self.assertEqual(query["tipo"], "Despesa")
        self.assertEqual(query["categoria"], "Alimentação")
        self.assertEqual(query["data"]["$gte"], datetime(2026, 11, 1, tzinfo=timezone.utc))
        self.assertEqual(query["data"]["$lt"], datetime(2026, 11, 5, tzinfo=timezone.utc))
        self.assertEqual(query["valor_centavos"], {"$gte": 1000, "$lte": 5000})
        self.assertEqual(query["descricao"]["$regex"], "café\\.\\*")


if __name__ == "__main__":
    unittest.main()
