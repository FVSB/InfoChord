import ast
from datetime import datetime, timedelta
import json
from pathlib import Path
import socket
import struct
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "distributed"))
from infochord_protocol import codec as wire


class ProtocolTests(unittest.TestCase):
    def test_primitive_contracts(self):
        value = (28, {"bytes": b"\x00\xff", "items": [None, True, 42, 0.2],
                      "time": datetime(2024, 1, 2), "set": {1, 2}})
        self.assertEqual(wire.loads(wire.dumps(value)), value)

    def test_bad_messages(self):
        bad = [b"not json", b"\x80\x04cos\nsystem\n", b"[]",
               b'{"version":2,"payload":null}',
               b'{"version":true,"payload":null}',
               b'{"version":1,"version":1,"payload":null}',
               b'{"version":1,"payload":NaN}',
               b'{"version":1,"payload":{"$":"os.system","data":"whoami"}}',
               b'{"version":1,"payload":{"$":"Bytes","data":"!"}}']
        for payload in bad:
            with self.subTest(payload=payload), self.assertRaises(wire.ProtocolError):
                wire.loads(payload)

    def test_size_and_depth_limits(self):
        with self.assertRaises(wire.ProtocolError):
            wire.dumps("a" * wire.MAX_MESSAGE_BYTES)
        with self.assertRaises(wire.ProtocolError):
            wire.loads(b"a" * (wire.MAX_MESSAGE_BYTES + 1))
        value = 1
        for _ in range(wire.MAX_DEPTH + 2):
            value = [value]
        with self.assertRaises(wire.ProtocolError):
            wire.dumps(value)

    def test_partial_tcp_reads(self):
        left, right = socket.socketpair()
        payload = wire.dumps("x" * 4096)
        frame = struct.pack("!I", len(payload)) + payload
        def writer():
            with left:
                for i in range(0, len(frame), 7):
                    left.sendall(frame[i:i+7])
        thread = threading.Thread(target=writer)
        thread.start()
        with right:
            self.assertEqual(wire.recv_frame(right), payload)
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())

    def test_closed_connection_and_invalid_lengths(self):
        for data in (b"\x00", struct.pack("!I", wire.MAX_MESSAGE_BYTES + 1), struct.pack("!I", 0)):
            left, right = socket.socketpair()
            with left:
                left.sendall(data)
            with right, self.assertRaises(wire.ProtocolError):
                wire.recv_frame(right)

    def test_frame_send_and_timeout(self):
        from unittest.mock import Mock
        sock = Mock()
        wire.send_frame(sock, b"abc")
        sock.settimeout.assert_called_once_with(wire.SOCKET_TIMEOUT)
        sock.sendall.assert_called_once_with(b"\x00\x00\x00\x03abc")

    def test_no_unsafe_serializers(self):
        for folder in ("client", "distributed", "infochord_protocol"):
            for path in (ROOT / folder).rglob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        self.assertFalse({x.name for x in node.names} & {"pickle", "jsonpickle"}, str(path))
                    elif isinstance(node, ast.ImportFrom):
                        self.assertNotIn(node.module, ("pickle", "jsonpickle"), str(path))


class DomainContractTests(unittest.TestCase):
    def test_reference_uses_frames_and_reads_large_responses(self):
        from chord.reference import ChordNodeReference
        failures = []
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(5)
            expected = "x" * 20000
            def respond():
                try:
                    conn, _ = listener.accept()
                    with conn:
                        self.assertEqual(wire.loads(wire.recv_frame(conn)), (42, "sample"))
                        wire.send_frame(conn, wire.dumps(expected))
                except Exception as exc:
                    failures.append(exc)
            thread = threading.Thread(target=respond)
            thread.start()
            reference = ChordNodeReference("127.0.0.1", listener.getsockname()[1])
            self.assertEqual(reference._send_data(42, "sample"), expected)
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(failures, [])

    def test_node_handler_uses_frames(self):
        from chord.node import ChordNode
        node = object.__new__(ChordNode)
        node.handle_request = lambda data, operation, payload: wire.dumps((operation, payload))
        left, right = socket.socketpair()
        thread = threading.Thread(target=node.server_handle, args=(right, ("127.0.0.1", 1)))
        thread.start()
        with left:
            value = (42, "x" * 10000)
            wire.send_frame(left, wire.dumps(value))
            self.assertEqual(wire.loads(wire.recv_frame(left)), value)
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())

    def test_document_roundtrip_and_tombstone(self):
        import numpy as np
        from helper.docs import EmbeddingDocument, get_document_from_bytes
        doc = EmbeddingDocument("sample.txt", "old text", [np.array([1., 0.])],
                                [np.array([0., 1.])], ["old text"])
        restored = get_document_from_bytes(wire.dumps(doc))
        self.assertEqual(restored.record.last_change, doc.record.last_change)
        self.assertEqual(restored.id, doc.id)
        np.testing.assert_array_equal(restored.embedding_list[0], doc.embedding_list[0])
        doc.delete()
        restored = wire.loads(wire.dumps(doc))
        self.assertTrue(restored.record.is_delete)
        self.assertIsNone(restored.text)

    def test_update_keeps_chunks_in_sync(self):
        import numpy as np
        from helper.docs import EmbeddingDocument
        old = EmbeddingDocument("sample.txt", "old", [np.array([1., 0.])], [np.array([1., 0.])], ["old"])
        new = EmbeddingDocument("sample.txt", "new", [np.array([0., 1.])], [np.array([0., 1.])], ["new"])
        new.record.last_change = old.record.last_change + timedelta(seconds=1)
        self.assertTrue(old.update(new))
        self.assertEqual(old.text_chunks, ["new"])

    def test_nodes_operations_packets_and_query(self):
        import numpy as np
        from chord.reference import ChordNodeReference
        from helper.query import QueryHandle
        from helper.utils import CrudCode, Paquete
        node = ChordNodeReference("172.25.0.2")
        restored = wire.loads(wire.dumps((node, CrudCode.Insert, Paquete(1, b"abc", True))))
        self.assertEqual(restored[0].__dict__, node.__dict__)
        self.assertIs(restored[1], CrudCode.Insert)
        self.assertEqual(restored[2].bytes_datos, b"abc")
        query = QueryHandle("test-guid", [np.array([1., 0.])], [], lambda *_: 1, 5)
        query._add_posible(1, "one", "sample", 0.5)
        query._add_posible(2, "two", "sample", np.float64(0.9))
        payload = wire.dumps(query)
        self.assertNotIn(b"lambda", payload)
        restored = wire.loads(payload)
        self.assertEqual(restored.func_score_embedding([1, 0], [1, 0]), 1)
        self.assertEqual([x["id"] for x in restored.get_results()], [2, 1])

    def test_invalid_vectors_and_schema(self):
        for payload in (
            {"$": "Vector", "data": [True, 1]},
            {"$": "Vector", "data": []},
            {"$": "Node", "data": {"id": 1, "ip": "evil/", "port": 8001}},
            {"$": "Document", "data": {"id": 1}},
        ):
            with self.subTest(payload=payload), self.assertRaises(wire.ProtocolError):
                wire.loads(json.dumps({"version": 1, "payload": payload}))

    def test_query_tracking_can_be_removed(self):
        from helper.utils import ThreadingSet
        values = ThreadingSet()
        self.assertTrue(values.add_item("query"))
        self.assertTrue(values.delete_if_exits_item("query"))
        self.assertFalse(values.contains_item("query"))
        self.assertFalse(values.delete_if_exits_item("query"))
