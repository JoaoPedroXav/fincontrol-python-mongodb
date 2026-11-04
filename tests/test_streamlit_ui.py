"""Teste da interface com persistência real no Atlas."""

import os
import unittest
from pathlib import Path
from uuid import uuid4

from streamlit.testing.v1 import AppTest

from database import get_client, get_collection


@unittest.skipUnless(os.getenv("MONGODB_URI", "").strip(), "MONGODB_URI não configurada")
class StreamlitUITests(unittest.TestCase):
    def test_create_form_persists_transaction(self):
        marker = f"FINCONTROL_UI_TEST_{uuid4().hex}"
        client = get_client()
        collection = get_collection(client)
        try:
            app_path = Path(__file__).resolve().parents[1] / "app.py"
            app = AppTest.from_file(str(app_path)).run(timeout=20)
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            next(x for x in app.text_input if x.key == "create_description").set_value(marker)
            next(x for x in app.selectbox if x.key == "create_category").set_value("Salário")
            next(x for x in app.number_input if x.key == "create_value").set_value(123.45)
            next(x for x in app.text_area if x.key == "create_note").set_value(marker)
            next(x for x in app.button if x.label == "Salvar transação").click()
            app.run(timeout=20)
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            row = collection.find_one({"observacao": marker})
            self.assertIsNotNone(row)
            self.assertEqual(row["valor_centavos"], 12345)
        finally:
            collection.delete_many({"observacao": marker})
            client.close()


if __name__ == "__main__":
    unittest.main()
