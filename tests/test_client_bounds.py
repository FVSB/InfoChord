import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "client"))
spec = importlib.util.spec_from_file_location("bounded_client", ROOT / "client/api.py")
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class ClientBoundsTests(unittest.TestCase):
    def test_query_retries_are_bounded(self):
        with patch.object(client, "_server_ip", return_value="127.0.0.1"), \
             patch.object(client, "_make_get_ask_to_server", side_effect=client.ClientError("down")) as get, \
             patch.object(client.time, "sleep"), self.assertRaises(client.ClientError):
            client.make_query("sample", [])
        self.assertEqual(get.call_count, client.MAX_ATTEMPTS)

    def test_redirect_loop_is_rejected(self):
        response = MagicMock(status_code=301)
        response.json.return_value = {"ip": "127.0.0.1"}
        with patch.object(client.requests, "post", return_value=response) as post, self.assertRaises(client.ClientError):
            client.make_crud_post("127.0.0.1", "upload", ("sample", "text"))
        self.assertEqual(post.call_count, 1)

    def test_progress_deadline(self):
        with patch.object(client, "_server_ip", return_value="127.0.0.1"), \
             patch.object(client, "make_crud_post", return_value=({"guid":"sample"}, "127.0.0.1")), \
             patch.object(client.time, "monotonic", side_effect=[0, 121]), self.assertRaises(client.ClientError):
            client.insert_document("sample", "text")

    def test_large_response_closes_connection(self):
        response = MagicMock()
        response.iter_content.return_value = [b"123456"]
        with patch.object(client.wire, "MAX_MESSAGE_BYTES", 5), self.assertRaises(client.ClientError):
            client._read_response(response)
        response.close.assert_called_once()

    def test_failed_write_is_not_retried(self):
        with patch.object(client.requests, "post", side_effect=client.requests.Timeout) as post, self.assertRaises(client.ClientError):
            client.make_crud_post("127.0.0.1", "upload", ("sample", "text"))
        self.assertEqual(post.call_count, 1)
