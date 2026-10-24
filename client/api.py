"""Bounded client operations for the versioned InfoChord demo protocol."""

import os
from pathlib import Path
import socket
import time

import requests

from discovery import SearchServers
from config import CHORD_PORT, HTTP_PORT
from infochord_protocol import codec as wire

_servers = None
REQUEST_TIMEOUT = (5, 65)
MAX_ATTEMPTS = 3
MAX_REDIRECTS = 8
PROGRESS_TIMEOUT = 120


class ClientError(RuntimeError):
    """A recoverable, user-visible cluster/provider failure."""


def _get_servers():
    global _servers
    if _servers is None:
        _servers = SearchServers(socket.gethostbyname(socket.gethostname()), CHORD_PORT)
    return _servers


def _server_ip():
    try:
        return _get_servers().get_random_server_ip()
    except TimeoutError as exc:
        raise ClientError(str(exc)) from exc


def _read_response(response):
    body = bytearray()
    try:
        response.raise_for_status()
        for chunk in response.iter_content(65536):
            body.extend(chunk)
            if len(body) > wire.MAX_MESSAGE_BYTES:
                raise ClientError("Server response exceeds 10 MiB")
        return bytes(body)
    finally:
        response.close()


def _make_get_ask_to_server(server_ip, sub_url, params):
    try:
        response = requests.get(
            f"http://{server_ip}:{HTTP_PORT}/{sub_url}", params=params,
            timeout=REQUEST_TIMEOUT, stream=True,
        )
        import json
        return json.loads(_read_response(response))
    except (requests.RequestException, ValueError) as exc:
        raise ClientError(f"Node unavailable or rejected request ({type(exc).__name__})") from exc


def make_query(query, posibles_extensions, max_results=10, min_score=0):
    if not query.strip() or not 1 <= max_results <= 100:
        raise ClientError("Provide a query and 1..100 maximum results")
    params = dict(query=query, extensions=posibles_extensions,
                  max_results=max_results, min_score=min_score)
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = _make_get_ask_to_server(_server_ip(), "query", params)
            if "results" not in response:
                raise ClientError("Cluster is stabilizing; try again shortly")
            return response["results"]
        except ClientError:
            if attempt == MAX_ATTEMPTS - 1:
                raise
            time.sleep(1)


def make_crud_post(server_ip, sub_route, data):
    payload = wire.dumps(data)
    visited = set()
    for _ in range(MAX_REDIRECTS):
        if server_ip in visited:
            raise ClientError("Node redirection loop")
        visited.add(server_ip)
        try:
            response = requests.post(
                f"http://{server_ip}:{HTTP_PORT}/{sub_route}", data=payload,
                headers={"Content-Type": "application/json"}, timeout=REQUEST_TIMEOUT,
                allow_redirects=False,
            )
            with response:
                if response.status_code == 301:
                    import ipaddress
                    server_ip = str(ipaddress.IPv4Address(response.json()["ip"]))
                    continue
                response.raise_for_status()
                return response.json(), server_ip
        except (requests.RequestException, ValueError, KeyError) as exc:
            # Do not retry writes: a timeout does not prove that a write failed.
            raise ClientError("Write failed or outcome unknown; check the document before retrying") from exc
    raise ClientError("Too many node redirects")


def _insert_update_helper(title, text, is_insert):
    if not title.strip() or not text.strip():
        raise ClientError("Document title and text must not be empty")
    response, ip = make_crud_post(_server_ip(), "upload" if is_insert else "update", (title, text))
    if "guid" not in response:
        return response
    operation_guid = response["guid"]
    deadline = time.monotonic() + PROGRESS_TIMEOUT
    while time.monotonic() < deadline:
        response = _make_get_ask_to_server(ip, "progress_document", {"guid": operation_guid})
        if response.get("is_error"):
            raise ClientError("Document processing failed; check embedding provider and node status")
        if response.get("is_finish"):
            response["owner_ip"] = ip
            return response
        time.sleep(1)
    raise ClientError("Document processing timed out; check outcome before retrying")


def insert_document(title, text):
    return _insert_update_helper(title, text, True)


def update_document(title, text):
    return _insert_update_helper(title, text, False)


def delete_document(title):
    return make_crud_post(_server_ip(), "delete_file", title)[0]


def _download_file(url, file):
    try:
        response = requests.get(url, params={"name": file}, timeout=REQUEST_TIMEOUT, stream=True)
        text = wire.loads(_read_response(response))
        if not isinstance(text, str):
            raise ClientError("Document not found or deleted")
        return text
    except (requests.RequestException, ValueError) as exc:
        raise ClientError("Cannot retrieve document") from exc


def download_file(title, save_file=False):
    url = f"http://{_server_ip()}:{HTTP_PORT}/get_document_by_name"
    text = _download_file(url, title)
    if save_file:
        folder = Path(os.getenv("DOWNLOAD_DIR", "/app/downloads"))
        folder.mkdir(parents=True, exist_ok=True)
        (folder / Path(title.replace("\\", "/")).name).write_text(text, encoding="utf-8")
    return text
