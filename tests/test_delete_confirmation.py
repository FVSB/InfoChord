"""Regression tests for the Streamlit delete page's explicit confirmation gate."""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock


APP_PATH = Path(__file__).resolve().parents[1] / "client" / "ui" / "app.py"


class DeletePageConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.previous_modules = {
            name: sys.modules.get(name)
            for name in ("streamlit", "api", "shared", "shared.logger")
        }
        self.streamlit = types.ModuleType("streamlit")
        self.streamlit.filename = "sample.txt"
        self.streamlit.confirmed = False
        self.streamlit.clicked = False
        self.streamlit.warnings = []
        self.streamlit.set_page_config = Mock()
        self.streamlit.title = Mock()
        self.streamlit.text_input = lambda *_args, **_kwargs: self.streamlit.filename
        self.streamlit.checkbox = lambda *_args, **_kwargs: self.streamlit.confirmed
        self.streamlit.button = lambda label, **_kwargs: (
            label == "Eliminar documento" and self.streamlit.clicked
        )
        self.streamlit.warning = self.streamlit.warnings.append
        self.streamlit.write = Mock()
        self.streamlit.sidebar = types.SimpleNamespace(
            selectbox=lambda *_args, **_kwargs: "Eliminar un archivo"
        )

        self.api = types.ModuleType("api")
        self.api.delete_document = Mock(return_value="deleted")
        self.api.make_query = Mock()
        self.api.download_file = Mock()
        self.api.insert_document = Mock()
        self.api.update_document = Mock()

        shared = types.ModuleType("shared")
        shared.__path__ = []
        logger = types.ModuleType("shared.logger")
        logger.log_message = Mock()
        sys.modules.update(
            {
                "streamlit": self.streamlit,
                "api": self.api,
                "shared": shared,
                "shared.logger": logger,
            }
        )

    def tearDown(self):
        for name, previous in self.previous_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
        sys.modules.pop("_infochord_ui_under_test", None)

    def render_delete_page(self):
        spec = importlib.util.spec_from_file_location("_infochord_ui_under_test", APP_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

    def test_page_render_does_not_delete(self):
        self.render_delete_page()
        self.api.delete_document.assert_not_called()

    def test_delete_requires_confirmation_and_button(self):
        self.streamlit.clicked = True
        self.streamlit.confirmed = True
        self.render_delete_page()
        self.api.delete_document.assert_called_once_with("sample.txt")

    def test_delete_without_confirmation_is_rejected(self):
        self.streamlit.clicked = True
        self.render_delete_page()
        self.api.delete_document.assert_not_called()
        self.assertTrue(self.streamlit.warnings)

    def test_empty_filename_is_rejected_even_when_confirmed(self):
        self.streamlit.filename = "   "
        self.streamlit.confirmed = True
        self.streamlit.clicked = True
        self.render_delete_page()
        self.api.delete_document.assert_not_called()
        self.assertTrue(self.streamlit.warnings)


if __name__ == "__main__":
    unittest.main()
