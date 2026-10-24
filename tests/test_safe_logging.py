import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch


class LoggingTests(unittest.TestCase):
    def test_document_and_exception_text_are_not_retained(self):
        root = Path(__file__).resolve().parents[1]
        for folder in ("shared", "client/shared", "distributed/shared"):
            with self.subTest(folder=folder):
                spec = importlib.util.spec_from_file_location("safe_logger", root / folder / "logger.py")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module._initialized = True
                logger = Mock()
                with patch.object(module.logging, "getLogger", return_value=logger):
                    try:
                        raise ValueError("PRIVATE-DOCUMENT-TEXT")
                    except ValueError:
                        module.log_message("PRIVATE-DOCUMENT-TEXT", extra_data={"key":"PRIVATE-KEY"})
                self.assertNotIn("PRIVATE", str(module.logs_json))
                self.assertNotIn("PRIVATE", str(logger.log.call_args))
                self.assertIn("ValueError", str(logger.log.call_args))
