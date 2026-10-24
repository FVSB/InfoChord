"""Deterministic OpenAI-compatible fixture. NOT a semantic embedding model."""
import hashlib
import math
import re
from flask import Flask, jsonify, request

app = Flask(__name__)
available = True


@app.get('/health')
def health():
    return jsonify(status='fixture')


@app.post('/fixture/availability')
def availability():
    global available
    available = request.json['available']
    return jsonify(available=available)


@app.post('/v1/embeddings')
def embeddings():
    if not available:
        return jsonify(error=dict(message='Fixture unavailable', type='unavailable')), 503
    inputs = request.json['input']
    if isinstance(inputs, str):
        inputs = [inputs]
    data = []
    for index, text in enumerate(inputs):
        vector = [0.] * 64
        for word in re.findall(r'\w+', text.lower()):
            vector[int.from_bytes(hashlib.sha256(word.encode()).digest()[:4], 'big') % 64] += 1
        norm = math.sqrt(sum(x*x for x in vector)) or 1
        data.append(dict(object='embedding', index=index, embedding=[x/norm for x in vector]))
    return jsonify(object='list', data=data, model='fixture', usage=dict(prompt_tokens=1, total_tokens=1))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000)
