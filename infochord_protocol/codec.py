"""JSON protocol v1. No dynamic imports, object hooks or executable payloads.

The schema is deliberately limited to the domain DTOs below. Internal locks,
callbacks and clients never cross the wire. Legacy databases are not decoded.
"""

import base64
import binascii
from datetime import datetime
import heapq
import json
import math
import struct
import time

VERSION = 1
MAX_MESSAGE_BYTES = 10 * 1024 * 1024
MAX_DEPTH = 40
SOCKET_TIMEOUT = 20


class ProtocolError(ValueError):
    """Untrusted input does not conform to protocol v1."""


# Exact fields, not arbitrary __dict__ reconstruction.
FIELDS = {
    "Node": ("id", "ip", "port"),
    "Record": ("doc_id", "is_delete", "last_change"),
    "Document": ("id", "title", "extension", "text", "record"),
    "EmbeddingDocument": (
        "id", "title", "extension", "text", "record", "embedding_list",
        "embedding_title_list", "text_chunks",
    ),
    "Result": ("id", "title", "snippet", "score"),
    "Heap": ("heap",),
    "Query": (
        "guid", "query_embedding_list", "posibles_extensions", "posible_docs",
        "min_score", "max_results", "is_stable_response_",
    ),
    "Packet": ("numero", "bytes_datos", "es_final"),
}


def _domain_types():
    # Static imports only; deferred so primitive client messages need no server deps.
    from chord.reference import ChordNodeReference
    from helper.docs import Document, EmbeddingDocument, DocsRecords
    from helper.query import DocsClassification, MaxHeap, QueryHandle
    from helper.utils import Paquete
    return {
        "Node": ChordNodeReference, "Record": DocsRecords,
        "Document": Document, "EmbeddingDocument": EmbeddingDocument,
        "Result": DocsClassification, "Heap": MaxHeap, "Query": QueryHandle,
        "Packet": Paquete,
    }


def _number(value):
    try:
        if type(value).__module__.startswith("numpy") and hasattr(value, "item"):
            value = value.item()
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _vectors(value):
    if value is None:
        return True  # tombstone
    if not isinstance(value, list) or len(value) > 10000:
        return False
    dimensions = set()
    for vector in value:
        # numpy arrays are restored by the Vector contract.
        if not isinstance(vector, (list, tuple)):
            try:
                vector = vector.tolist()
            except AttributeError:
                return False
        if not isinstance(vector, list) or not 1 <= len(vector) <= 65536:
            return False
        if not all(_number(n) for n in vector):
            return False
        dimensions.add(len(vector))
    return len(dimensions) <= 1


def _validate(tag, data):
    if tag not in FIELDS or set(data) != set(FIELDS[tag]):
        raise ProtocolError(f"Unknown contract or fields: {tag}")
    for field in ("id", "doc_id", "numero"):
        if field in data and (type(data[field]) is not int or data[field] < 0):
            raise ProtocolError(f"Invalid {field}")
    for field in ("title", "extension", "snippet", "guid", "ip"):
        if field in data and not isinstance(data[field], str):
            raise ProtocolError(f"Invalid {field}")
    if "title" in data and not 1 <= len(data["title"]) <= 1024:
        raise ProtocolError("Invalid title length")
    if "text" in data and data["text"] is not None and not isinstance(data["text"], str):
        raise ProtocolError("Invalid document text")
    for field in ("is_delete", "es_final", "is_stable_response_"):
        if field in data and type(data[field]) is not bool:
            raise ProtocolError(f"Invalid {field}")
    if tag == "Node":
        import ipaddress
        try:
            ipaddress.IPv4Address(data["ip"])
        except ValueError as exc:
            raise ProtocolError("Invalid node IPv4 address") from exc
        if type(data["port"]) is not int or not 1 <= data["port"] <= 65535:
            raise ProtocolError("Invalid port")
    if tag == "Record":
        if not isinstance(data["last_change"], datetime) or data["last_change"].tzinfo is not None:
            raise ProtocolError("Expected a naive UTC timestamp")
    if tag in ("Document", "EmbeddingDocument"):
        record = data["record"]
        if type(record).__name__ != "DocsRecords" or record.doc_id != data["id"]:
            raise ProtocolError("Document record does not match id")
    for field in ("embedding_list", "embedding_title_list", "query_embedding_list"):
        if field in data and not _vectors(data[field]):
            raise ProtocolError(f"Invalid vectors: {field}")
    if tag == "EmbeddingDocument":
        chunks = data["text_chunks"]
        if not isinstance(chunks, list) or not all(isinstance(x, str) for x in chunks):
            raise ProtocolError("Invalid text chunks")
        if not data["record"].is_delete:
            if not data["embedding_list"] or not data["embedding_title_list"]:
                raise ProtocolError("Live document requires embeddings")
            if len(chunks) != len(data["embedding_list"]):
                raise ProtocolError("Chunks and embeddings do not match")
            if len(data["embedding_list"][0]) != len(data["embedding_title_list"][0]):
                raise ProtocolError("Embedding dimensions do not match")
    if tag == "Result" and not _number(data["score"]):
        raise ProtocolError("Invalid result score")
    if tag == "Heap" and (not isinstance(data["heap"], list) or
                           not all(type(x).__name__ == "DocsClassification" for x in data["heap"])):
        raise ProtocolError("Invalid result heap")
    if tag == "Query":
        if type(data["max_results"]) is not int or not 1 <= data["max_results"] <= 100:
            raise ProtocolError("max_results must be 1..100")
        if not _number(data["min_score"]) or not data["query_embedding_list"]:
            raise ProtocolError("Invalid query scores or vectors")
        if not isinstance(data["posibles_extensions"], list) or not all(
            isinstance(x, str) for x in data["posibles_extensions"]
        ):
            raise ProtocolError("Invalid extensions")
        if type(data["posible_docs"]).__name__ != "MaxHeap":
            raise ProtocolError("Invalid query results")
    if tag == "Packet" and not isinstance(data["bytes_datos"], bytes):
        raise ProtocolError("Invalid packet bytes")


def _encode(value, depth=0):
    if depth > MAX_DEPTH:
        raise ProtocolError("Nesting limit exceeded")
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ProtocolError("Non-finite number")
        return value
    if isinstance(value, bytes):
        return {"$": "Bytes", "data": base64.b64encode(value).decode("ascii")}
    if isinstance(value, datetime):
        return {"$": "Time", "data": value.isoformat()}
    if isinstance(value, (list, tuple, set)):
        items = [_encode(x, depth + 1) for x in value]
        return items if isinstance(value, list) else {"$": "Tuple" if isinstance(value, tuple) else "Set", "data": items}
    if type(value) is dict:
        if not all(isinstance(k, str) for k in value) or "$" in value:
            raise ProtocolError("Dictionary keys must be strings without reserved '$'")
        return {k: _encode(v, depth + 1) for k, v in value.items()}
    # numpy is optional for primitive-only clients.
    if type(value).__module__.startswith("numpy"):
        if hasattr(value, "ndim") and value.ndim == 1:
            numbers = value.tolist()
            if not _vectors([numbers]):
                raise ProtocolError("Invalid numeric vector")
            return {"$": "Vector", "data": numbers}
        if hasattr(value, "item"):
            return _encode(value.item(), depth + 1)
    from helper.utils import CrudCode
    if type(value) is CrudCode:
        return {"$": "Crud", "data": value.name}
    for tag, cls in _domain_types().items():
        if type(value) is cls:
            fields = {name: getattr(value, name) for name in FIELDS[tag]}
            _validate(tag, fields)
            return {"$": tag, "data": {k: _encode(v, depth + 1) for k, v in fields.items()}}
    raise ProtocolError(f"Unsupported value: {type(value).__name__}")


def _cosine(left, right):
    if len(left) != len(right):
        raise ProtocolError("Embedding dimensions do not match")
    norm = math.sqrt(sum(float(x) ** 2 for x in left) * sum(float(x) ** 2 for x in right))
    return sum(float(a) * float(b) for a, b in zip(left, right)) / norm if norm else 0.0


def _decode(value, depth=0):
    if depth > MAX_DEPTH:
        raise ProtocolError("Nesting limit exceeded")
    if isinstance(value, list):
        return [_decode(x, depth + 1) for x in value]
    if not isinstance(value, dict):
        if value is not None and type(value) not in (str, bool, int, float):
            raise ProtocolError("Invalid scalar")
        if isinstance(value, float) and not math.isfinite(value):
            raise ProtocolError("Non-finite number")
        return value
    if "$" not in value:
        return {k: _decode(v, depth + 1) for k, v in value.items()}
    if set(value) != {"$", "data"} or not isinstance(value["$"], str):
        raise ProtocolError("Invalid tagged value")
    tag, raw = value["$"], value["data"]
    if tag == "Bytes":
        try:
            return base64.b64decode(raw, validate=True)
        except (ValueError, TypeError, binascii.Error) as exc:
            raise ProtocolError("Invalid base64") from exc
    if tag == "Time":
        try:
            return datetime.fromisoformat(raw)
        except (ValueError, TypeError) as exc:
            raise ProtocolError("Invalid timestamp") from exc
    if tag in ("Tuple", "Set", "Vector"):
        if not isinstance(raw, list):
            raise ProtocolError("Expected list")
        items = [_decode(x, depth + 1) for x in raw]
        if tag == "Vector":
            if not _vectors([items]):
                raise ProtocolError("Invalid vector")
            import numpy as np
            return np.array(items, dtype=float)
        try:
            return tuple(items) if tag == "Tuple" else set(items)
        except TypeError as exc:
            raise ProtocolError("Invalid set members") from exc
    if tag == "Crud":
        from helper.utils import CrudCode
        if not isinstance(raw, str) or raw not in CrudCode.__members__:
            raise ProtocolError("Invalid operation")
        return CrudCode[raw]
    if tag not in FIELDS or not isinstance(raw, dict):
        raise ProtocolError("Unknown contract")
    data = {k: _decode(v, depth + 1) for k, v in raw.items()}
    _validate(tag, data)
    cls = _domain_types()[tag]
    result = cls.__new__(cls)
    for key, item in data.items():
        setattr(result, key, item)
    if tag == "Query":
        result.func_score_embedding = _cosine  # local fixed behavior, never from input
    if tag == "Heap":
        heapq.heapify(result.heap)
    return result


def dumps(value):
    try:
        payload = json.dumps({"version": VERSION, "payload": _encode(value)},
                             allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as exc:
        raise ProtocolError(str(exc)) from exc
    if len(payload) > MAX_MESSAGE_BYTES:
        raise ProtocolError("Message exceeds 10 MiB")
    return payload


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("Duplicate JSON key")
        result[key] = value
    return result


def loads(payload):
    if not isinstance(payload, (str, bytes, bytearray)) or len(payload) > MAX_MESSAGE_BYTES:
        raise ProtocolError("Invalid message size/type")
    try:
        if isinstance(payload, str) and len(payload.encode("utf-8")) > MAX_MESSAGE_BYTES:
            raise ProtocolError("Message exceeds 10 MiB")
        envelope = json.loads(payload, object_pairs_hook=_unique_object)
        if not isinstance(envelope, dict) or set(envelope) != {"version", "payload"}:
            raise ProtocolError("Invalid envelope")
        if type(envelope["version"]) is not int or envelope["version"] != VERSION:
            raise ProtocolError("Unsupported protocol version; restart all nodes together")
        return _decode(envelope["payload"])
    except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
        raise ProtocolError(str(exc)) from exc


def _read_exact(sock, size, deadline):
    chunks = bytearray()
    while len(chunks) < size:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Frame read deadline exceeded")
        sock.settimeout(remaining)
        part = sock.recv(size - len(chunks))
        if not part:
            raise ProtocolError("Connection closed during frame")
        chunks.extend(part)
    return bytes(chunks)


def send_frame(sock, payload):
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_MESSAGE_BYTES:
        raise ProtocolError("Invalid frame length")
    sock.settimeout(SOCKET_TIMEOUT)
    sock.sendall(struct.pack("!I", len(payload)) + payload)


def recv_frame(sock):
    deadline = time.monotonic() + SOCKET_TIMEOUT
    size = struct.unpack("!I", _read_exact(sock, 4, deadline))[0]
    if not 0 < size <= MAX_MESSAGE_BYTES:
        raise ProtocolError("Invalid frame length")
    return _read_exact(sock, size, deadline)
