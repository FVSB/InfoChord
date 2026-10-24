"""Exercise real Streamlit rendering with backend calls mocked, not a live demo."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "client"))
import api
from streamlit.testing.v1 import AppTest


class UIRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Verify the native stack explicitly and keep DLL cold-start outside
        # interaction deadlines (important on Windows ARM with x64 Python).
        import numpy
        import pyarrow
        import pandas

    def test_home_renders(self):
        app = AppTest.from_file(str(ROOT / "client/ui/app.py"), default_timeout=20).run()
        self.assertFalse(app.exception)
        self.assertIn("InfoChord", app.title[0].value)

    def test_deletion_render_and_explicit_action(self):
        with patch.object(api, "delete_document", return_value={"message":"deleted"}) as delete:
            app = AppTest.from_file(str(ROOT / "client/ui/app.py"), default_timeout=20).run()
            app.sidebar.selectbox[0].set_value("Eliminar un archivo").run()
            delete.assert_not_called()
            app.text_input[0].set_value("sample.txt").run()
            app.button[0].click().run()
            delete.assert_not_called()
            app.checkbox[0].check().run()
            app.button[0].click().run()
            self.assertFalse(app.exception)
            delete.assert_called_once_with("sample.txt")
