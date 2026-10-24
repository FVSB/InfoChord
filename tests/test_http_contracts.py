import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class HTTPContractTests(unittest.TestCase):
    def test_routes_health_and_input_contracts_without_background_threads(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join([str(root / "distributed"), str(root), env.get("PYTHONPATH", "")])
            env["DB_PATH"] = "sqlite:///" + (Path(folder) / "test.db").as_posix()
            code = '''
import faulthandler
faulthandler.dump_traceback_later(25)
print('Importing HTTP service', flush=True)
from searcher import DistributedSearcher, app
print('HTTP service imported', flush=True)
from infochord_protocol import codec as wire
# Bypass constructors that start background threads; exercise real route registration.
node = object.__new__(DistributedSearcher)
node.is_db_stable = lambda: True
node.upload_file = lambda: ('accepted', 200)
node.setup_routes()
print('Routes registered', flush=True)
client = app.test_client()
assert client.get('/health/live').status_code == 200
assert client.get('/health/ready').status_code == 200
print('Health endpoints passed', flush=True)
assert client.post('/upload', data=b'legacy object').status_code == 415
assert client.post('/upload', data=b'not-json', content_type='application/json').status_code == 400
assert client.post('/upload', data=wire.dumps(('sample.txt','sample text')), content_type='application/json').status_code == 200
assert client.post('/upload', data=wire.dumps(('', 'sample text')), content_type='application/json').status_code == 400
assert client.post('/upload', data=b'x'*(wire.MAX_MESSAGE_BYTES+1), content_type='application/json').status_code == 413
print('POST contract checks passed', flush=True)
assert client.get('/query?query=sample&max_results=abc').status_code == 400
assert client.get('/query?query=sample&min_score=NaN').status_code == 400
assert client.get('/query?query=sample&max_results=101').status_code == 400
assert client.get('/query?query=').status_code == 400
faulthandler.cancel_dump_traceback_later()
print('HTTP contract checks passed', flush=True)
'''
            try:
                result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=45)
            except subprocess.TimeoutExpired as exc:
                self.fail(f"HTTP contract process timed out. stdout={exc.stdout!r}; stderr={exc.stderr!r}")
            self.assertEqual(result.returncode, 0, result.stderr)
