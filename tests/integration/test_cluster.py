"""Real cluster scenarios. Run through scripts/check-demo.py, not with private data."""
import os
import socket
import sys
import time
import unittest

import requests
from api import (ClientError, _insert_update_helper, _download_file, make_query,
                 make_crud_post, delete_document, download_file)
from infochord_protocol import codec as wire

NODES = os.getenv("TEST_NODES", "node1,node2,node3").split(",")
TITLE = "persistence.txt"
TEXT = "Distributed semantic search stores sample documents across a Chord ring."


class ClusterTests(unittest.TestCase):
    def test_health_and_request_validation(self):
        for node in NODES:
            url = f"http://{node}:8000"
            self.assertEqual(requests.get(url + "/health/live", timeout=30).status_code, 200)
            self.assertEqual(requests.get(url + "/health/ready", timeout=30).status_code, 200)
            self.assertEqual(requests.post(url + "/upload", data=b"not-json", timeout=30).status_code, 415)
            self.assertEqual(requests.post(url + "/upload", data=b"not-json", headers={"Content-Type":"application/json"}, timeout=30).status_code, 400)

    def test_multinode_crud_search_and_owner_redirect(self):
        title = "cluster-sample.txt"
        result = _insert_update_helper(title, "Oranges are citrus fruit grown in orchards.", True)
        self.assertTrue(result["is_finish"], result)
        redirected = False
        for node in NODES:
            if socket.gethostbyname(node) == result["owner_ip"]:
                continue
            response = requests.post(f"http://{node}:8000/update", data=wire.dumps((title, "Oranges citrus fresh sample")), headers={"Content-Type":"application/json"}, timeout=70, allow_redirects=False)
            if response.status_code == 301:
                redirected = True
                break
        self.assertTrue(redirected, "At least one node must redirect to the owner")
        result = _insert_update_helper(title, "Oranges citrus fresh sample", False)
        self.assertTrue(result["is_finish"], result)
        self.assertEqual(download_file(title), "Oranges citrus fresh sample")
        results = make_query("oranges citrus", ["txt"])
        self.assertIn(title, [item["title"] for item in results])
        delete_document(title)
        results = make_query("oranges citrus", ["txt"])
        self.assertNotIn(title, [item["title"] for item in results])
        with self.assertRaises(ClientError):
            download_file(title)

    def test_seed_persistence(self):
        result = _insert_update_helper(TITLE, TEXT, True)
        self.assertTrue(result["is_finish"], result)
        self.assertEqual(download_file(TITLE), TEXT)

    def test_persistence_from_every_surviving_node(self):
        for node in NODES:
            self.assertEqual(_download_file(f"http://{node}:8000/get_document_by_name", TITLE), TEXT)
        results = make_query("distributed semantic search", ["txt"])
        self.assertIn(TITLE, [item["title"] for item in results])

    def test_crud_after_node_failure(self):
        result = _insert_update_helper("survivor.txt", "Surviving nodes accept sample documents.", True)
        self.assertTrue(result["is_finish"], result)
        self.assertIn("survivor.txt", [x["title"] for x in make_query("surviving nodes", ["txt"])])
        _insert_update_helper("survivor.txt", "Updated survivor sample.", False)
        self.assertEqual(download_file("survivor.txt"), "Updated survivor sample.")
        delete_document("survivor.txt")

    def test_embedding_outage_is_visible_and_recoverable(self):
        control = "http://embeddings:9000/fixture/availability"
        started = time.monotonic()
        try:
            requests.post(control, json={"available": False}, timeout=10).raise_for_status()
            with self.assertRaises(ClientError):
                _insert_update_helper("provider-down.txt", "Disposable unavailable provider sample", True)
            self.assertLess(time.monotonic() - started, 100)
        finally:
            requests.post(control, json={"available": True}, timeout=10).raise_for_status()
        self.assertIn(TITLE, [x["title"] for x in make_query("distributed search", ["txt"])])


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "initial"
    stages = {
        "initial": ["test_health_and_request_validation", "test_multinode_crud_search_and_owner_redirect", "test_seed_persistence", "test_embedding_outage_is_visible_and_recoverable"],
        "restart": ["test_health_and_request_validation", "test_persistence_from_every_surviving_node"],
        "failure": ["test_health_and_request_validation", "test_persistence_from_every_surviving_node", "test_crud_after_node_failure"],
        "recovery": ["test_health_and_request_validation", "test_persistence_from_every_surviving_node"],
    }
    suite = unittest.TestSuite(ClusterTests(name) for name in stages[stage])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
