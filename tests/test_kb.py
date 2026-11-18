"""KB tests: idempotent ingest + retrieval (fake embeddings, tmp Chroma)."""
import hashlib
import math
import re

import pytest

from app import kb

DIM = 256


def fake_embed(texts):
    """Bag-of-words hashed embeddings so keyword queries match their docs."""
    vecs = []
    for text in texts:
        vec = [0.0] * DIM
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            vec[int(hashlib.md5(token.encode()).hexdigest(), 16) % DIM] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vecs.append([v / norm for v in vec])
    return vecs


@pytest.fixture()
def collection(tmp_path):
    return kb._get_collection(tmp_path / "chroma")


def test_ingest_is_idempotent(collection):
    n1 = kb.ingest(collection=collection, embed_fn=fake_embed)
    n2 = kb.ingest(collection=collection, embed_fn=fake_embed)
    assert n1 == n2 == 15
    assert collection.count() == 15


def test_vpn_query_retrieves_vpn_doc(collection):
    kb.ingest(collection=collection, embed_fn=fake_embed)
    hits = kb.retrieve("VPN keeps disconnecting", collection=collection,
                       embed_fn=fake_embed, min_score=0.0)
    assert hits and hits[0]["doc_id"] == "kb-004"
    assert hits[0]["score"] > 0


def test_lunch_menu_query_returns_empty(collection):
    kb.ingest(collection=collection, embed_fn=fake_embed)
    assert kb.retrieve("what is the lunch menu", collection=collection,
                       embed_fn=fake_embed, min_score=0.35) == []


def test_admin_access_query_retrieves_admin_policy(collection):
    kb.ingest(collection=collection, embed_fn=fake_embed)
    hits = kb.retrieve("need admin access to the trial database",
                       collection=collection, embed_fn=fake_embed,
                       min_score=0.0)
    assert hits and hits[0]["doc_id"] == "kb-014"


def test_category_filter(collection):
    kb.ingest(collection=collection, embed_fn=fake_embed)
    hits = kb.retrieve("VPN disconnecting", category="Network/VPN",
                       collection=collection, embed_fn=fake_embed,
                       min_score=0.0)
    assert hits and all(h["doc_id"] in ("kb-004", "kb-005") for h in hits)
