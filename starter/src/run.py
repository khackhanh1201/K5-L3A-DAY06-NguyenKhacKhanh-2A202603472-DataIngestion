"""Day 06 pipeline entry point. Run from ``starter/``:

    python -m src.run ingest   # read + normalize PDFs -> results/pages.jsonl (for writing benchmark)
    python -m src.run check    # verify every benchmark evidence_quote exists on its gold page
    python -m src.run all      # chunk, embed, store (Chroma), retrieve A/B/C, metrics, audit sheets

Strategies (same corpus, model, store, questions):
    A: fixed 500 chars / overlap 50, no filter
    B: paragraph-aware, max 800 chars, no filter
    C: exactly index B + metadata filter, applied only when the question has one
"""
import csv
import json
import os
import platform
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .evaluation import evaluate_query, gold_list, norm, summarize
from .ingestion import load_pdf
from .models import Chunk, DocumentPage

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
MANIFEST = ROOT / "data" / "manifest.json"
BENCHMARK = ROOT / "benchmark" / "questions.json"
TOP_K = 3
MIN_CONTENT_PAGES = 30

INDEXES = {
    "A": {"chunker": "fixed_size", "size": 500, "overlap": 50},
    "B": {"chunker": "by_paragraph", "max_size": 800},
}
STRATEGIES = {
    "A": {"index": "A", "use_filter": False},
    "B": {"index": "B", "use_filter": False},
    "C": {"index": "B", "use_filter": True},
}
REQUIRED_MANIFEST = ["source_id", "title", "source_path_or_url", "license_or_permission",
                     "accessed_at", "page_range"]
REQUIRED_QUESTION = ["id", "split", "question", "expected_answer"]


# ---------------------------------------------------------------- helpers
def _read_json(path: Path) -> Any:
    if not path.exists():
        raise SystemExit(f"Missing {path.relative_to(ROOT)} - see starter/README.md")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _chunk(page: DocumentPage, cfg: dict[str, Any]) -> list[Chunk]:
    if cfg["chunker"] == "fixed_size":
        return fixed_size(page, cfg["size"], cfg["overlap"])
    return by_paragraph(page, cfg["max_size"])


# ---------------------------------------------------------------- ingest
def load_corpus() -> tuple[list[dict], list[DocumentPage], list[dict]]:
    manifest = _read_json(MANIFEST)
    ids = [d.get("source_id") for d in manifest]
    if len(set(ids)) != len(ids):
        raise SystemExit("Duplicate source_id in manifest")
    pages, errors = [], []
    for doc in manifest:
        missing = [k for k in REQUIRED_MANIFEST if not doc.get(k)]
        if missing:
            raise SystemExit(f"{doc.get('source_id')}: manifest missing {missing}")
        first, last = doc["page_range"]
        wanted = [p for p in range(first, last + 1) if p not in set(doc.get("exclude_pages", []))]
        pages += load_pdf(ROOT / doc["source_path_or_url"], doc["source_id"],
                          doc["source_path_or_url"], wanted, doc.get("metadata"), errors)
    return manifest, pages, errors


def cmd_ingest() -> list[DocumentPage]:
    RESULTS.mkdir(exist_ok=True)
    manifest, pages, errors = load_corpus()
    with open(RESULTS / "pages.jsonl", "w", encoding="utf-8") as f:
        for p in pages:
            f.write(json.dumps({"document_id": p.document_id, "page": p.page, "chars": len(p.text),
                                "metadata": p.metadata, "text": p.text}, ensure_ascii=False) + "\n")
    _write_json(RESULTS / "ingest_errors.json", errors)
    per_doc = {d["source_id"]: [{"page": p.page, "chars": len(p.text)} for p in pages
                                if p.document_id == d["source_id"]] for d in manifest}
    _write_json(RESULTS / "page_counts.json", per_doc)
    print(f"Content pages: {len(pages)} | errors/skipped: {len(errors)}")
    for doc_id, items in per_doc.items():
        print(f"  {doc_id}: {len(items)} pages, {sum(i['chars'] for i in items)} chars")
    for e in errors:
        print(f"  [skip] {e['document_id']} p{e['page']}: {e['error']}")
    if len(pages) < MIN_CONTENT_PAGES:
        raise SystemExit(f"Only {len(pages)} content pages (< {MIN_CONTENT_PAGES}). Add pages to the manifest.")
    print("Wrote results/pages.jsonl, page_counts.json, ingest_errors.json")
    return pages


# ---------------------------------------------------------------- benchmark check
def load_questions() -> list[dict]:
    questions = _read_json(BENCHMARK)
    problems = []
    seen = set()
    for q in questions:
        missing = [k for k in REQUIRED_QUESTION if not q.get(k)]
        if not q.get("gold") and not all(q.get(k) for k in ("gold_source_id", "gold_page", "evidence_quote")):
            missing.append("gold_source_id/gold_page/evidence_quote (or gold[])")
        if missing:
            problems.append(f"{q.get('id')}: missing {missing}")
        if q.get("split") not in ("dev", "test"):
            problems.append(f"{q.get('id')}: split must be dev/test")
        if q.get("id") in seen:
            problems.append(f"duplicate id {q.get('id')}")
        seen.add(q.get("id"))
    if problems:
        raise SystemExit("Benchmark problems:\n  " + "\n  ".join(problems))
    return questions


def cmd_check(pages: list[DocumentPage] | None = None) -> list[dict]:
    pages = pages if pages is not None else load_corpus()[1]
    questions = load_questions()
    text_by_page = {(p.document_id, p.page): norm(p.text) for p in pages}
    filter_values: dict[str, set[str]] = {}
    for p in pages:
        for k, v in p.metadata.items():
            filter_values.setdefault(k, set()).add(str(v))
    bad = []
    for q in questions:
        for g in gold_list(q):
            page_text = text_by_page.get((g["source_id"], int(g["page"])))
            if page_text is None:
                bad.append(f"{q['id']}: page {g['source_id']} p{g['page']} not in ingested corpus")
            elif norm(g["evidence_quote"]) not in page_text:
                bad.append(f"{q['id']}: evidence_quote not found on {g['source_id']} p{g['page']}")
        for k, v in (q.get("filter") or {}).items():
            if str(v) not in filter_values.get(k, set()):
                bad.append(f"{q['id']}: filter {k}={v} does not exist in corpus metadata")
    dev = sum(q["split"] == "dev" for q in questions)
    test = len(questions) - dev
    filt_total = sum(bool(q.get("filter")) for q in questions)
    filt_test = sum(bool(q.get("filter")) and q["split"] == "test" for q in questions)
    print(f"Questions: {len(questions)} (dev {dev} / test {test}); "
          f"with filter: {filt_total} (test {filt_test})")
    warnings = []
    if len(questions) < 20: warnings.append("need >= 20 questions")
    if dev < 15: warnings.append("need >= 15 dev")
    if test < 5: warnings.append("need >= 5 test")
    if filt_total < 3: warnings.append("need >= 3 filter questions")
    if filt_test < 1: warnings.append("need >= 1 filter question in test")
    for w in warnings:
        print(f"  [warn] {w}")
    for b in bad:
        print(f"  [FAIL] {b}")
    if bad:
        raise SystemExit("Fix the benchmark before running experiments.")
    print("Evidence check OK" + (" (with warnings)" if warnings else ""))
    return questions


# ---------------------------------------------------------------- experiments
def _coherence_sheet(pages: list[DocumentPage], chunks_by_index: dict[str, list[Chunk]]) -> None:
    """10 fixed positions chosen BEFORE seeing scores: middle sentence of the first 10 pages
    sorted by (document_id, page). For each strategy, record the chunk containing it."""
    sample = sorted(pages, key=lambda p: (p.document_id, p.page))[:10]
    rows = []
    for pos, page in enumerate(sample, 1):
        flat = re.sub(r"\s+", " ", page.text)
        mid = len(flat) // 2
        start = flat.rfind(". ", 0, mid)
        start = start + 2 if start != -1 else 0
        anchor = flat[start:start + 60]
        key = norm(anchor[:40])
        for strategy, cfg in STRATEGIES.items():
            candidates = [c for c in chunks_by_index[cfg["index"]]
                          if c.document_id == page.document_id and c.page == page.page]
            found = next((c for c in candidates if key in norm(c.text)), None) \
                or next((c for c in candidates if norm(anchor[:20]) in norm(c.text)), None)
            rows.append([pos, strategy, page.document_id, page.page, anchor,
                         found.chunk_id if found else "NOT_FOUND", found.text if found else "", "", ""])
    with open(RESULTS / "audit_coherence.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["position", "strategy", "document_id", "page", "anchor_text", "chunk_id",
                    "chunk_text", "coherence_0_1_2", "reason"])
        w.writerows(rows)


def _audit_sheets(traces: list[dict]) -> None:
    with open(RESULTS / "audit_test_hits.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["strategy", "qid", "filter", "rank", "auto_hit", "score", "chunk_id", "document_id",
                    "page", "metadata", "chunk_text", "metadata_correct_0_1", "metadata_note"])
        for t in traces:
            if t["split"] != "test":
                continue
            for rank, (h, flag) in enumerate(zip(t["hits"], t["hit_flags"]), 1):
                w.writerow([t["strategy"], t["id"], json.dumps(t["filter"]), rank, int(flag),
                            round(h["score"], 4), h["chunk_id"], h["document_id"], h["page"],
                            json.dumps(h["metadata"], ensure_ascii=False), h["text"], "", ""])
    with open(RESULTS / "audit_grounding.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["strategy", "qid", "question", "expected_answer", "gold", "auto_hit_at_3",
                    "grounding_0_1_2", "reason"])
        for t in traces:
            if t["split"] == "test":
                w.writerow([t["strategy"], t["id"], t["question"], t["expected_answer"],
                            json.dumps(t["gold"], ensure_ascii=False), int(t["hit_at_3"]), "", ""])


def cmd_all() -> None:
    load_dotenv(ROOT / ".env")
    from .embeddings import DEFAULT_MODEL, MyEmbedder
    from .store import ChromaStore
    import chromadb

    pages = cmd_ingest()
    questions = cmd_check(pages)

    model_name = os.getenv("EMBEDDING_MODEL") or DEFAULT_MODEL
    t0 = time.perf_counter()
    embedder = MyEmbedder(model_name)
    model_load_s = round(time.perf_counter() - t0, 2)
    store = ChromaStore(ROOT / os.getenv("CHROMA_DIR", "chroma_db"), embedder.dimensions)
    store.create_schema()

    stats: dict[str, Any] = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": platform.python_version(), "chromadb": chromadb.__version__,
        "embedding_model": model_name, "dimensions": embedder.dimensions,
        "metric": "cosine (Chroma HNSW, approximate)", "model_load_seconds": model_load_s,
        "cost_usd": 0, "content_pages": len(pages), "indexes": {},
    }
    chunks_by_index: dict[str, list[Chunk]] = {}
    for name, cfg in INDEXES.items():
        rows_before = store.count(name)
        t0 = time.perf_counter()
        chunks = [c for p in pages for c in _chunk(p, cfg)]
        t_chunk = time.perf_counter() - t0
        vectors = embedder.embed_documents([c.text for c in chunks])
        t_embed = time.perf_counter() - t0 - t_chunk
        store.upsert(name, chunks, vectors)
        t_total = time.perf_counter() - t0
        lengths = [len(c.text) for c in chunks]
        chunks_by_index[name] = chunks
        stats["indexes"][name] = {
            **cfg, "chunks": len(chunks), "rows_before": rows_before, "rows_after": store.count(name),
            "total_chars": sum(lengths), "min_chars": min(lengths),
            "median_chars": statistics.median(lengths), "mean_chars": round(statistics.mean(lengths), 1),
            "max_chars": max(lengths), "chunk_seconds": round(t_chunk, 3),
            "embed_seconds": round(t_embed, 2), "ingest_total_seconds": round(t_total, 2),
        }
        if stats["indexes"][name]["rows_after"] != len(chunks):
            raise SystemExit(f"Index {name}: {store.count(name)} rows in store but {len(chunks)} chunks")

    query_vectors = embedder.embed_queries([q["question"] for q in questions])
    traces = []
    for strategy, cfg in STRATEGIES.items():
        t0 = time.perf_counter()
        for q, qv in zip(questions, query_vectors):
            applied = q.get("filter") if cfg["use_filter"] and q.get("filter") else None
            hits = store.search(cfg["index"], qv, TOP_K, applied)
            trace = evaluate_query(q, hits, applied)
            trace.update(strategy=strategy, index=cfg["index"])
            traces.append(trace)
        stats.setdefault("retrieval_seconds", {})[strategy] = round(time.perf_counter() - t0, 3)

    RESULTS.mkdir(exist_ok=True)
    with open(RESULTS / "traces.jsonl", "w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    metrics = summarize(traces)
    _write_json(RESULTS / "config.json", {"indexes": INDEXES, "strategies": STRATEGIES, "top_k": TOP_K})
    _write_json(RESULTS / "summary.json", {"stats": stats, "metrics": metrics})
    with open(RESULTS / "ingest_runs.jsonl", "a", encoding="utf-8") as f:  # evidence for re-ingest check
        f.write(json.dumps({"run_at": stats["run_at"], **{k: {"chunks": v["chunks"],
                "rows_before": v["rows_before"], "rows_after": v["rows_after"]}
                for k, v in stats["indexes"].items()}}) + "\n")
    _coherence_sheet(pages, chunks_by_index)
    _audit_sheets(traces)

    print(f"\nModel {model_name} ({embedder.dimensions}d) | chromadb {chromadb.__version__}")
    for name, s in stats["indexes"].items():
        print(f"Index {name}: {s['chunks']} chunks (rows before {s['rows_before']} -> after {s['rows_after']}), "
              f"median {s['median_chars']} chars, ingest {s['ingest_total_seconds']}s")
    print(f"\n{'Strategy':<9}{'Split':<6}{'Hit@1':>8}{'Hit@3':>8}{'Filter':>9}  misses@3")
    for m in metrics:
        print(f"{m['strategy']:<9}{m['split']:<6}{m['hit1_str']:>8}{m['hit3_str']:>8}"
              f"{m['filter_compliance_str']:>9}  {', '.join(m['misses_at_3'])}")
    print("\nWrote results/: traces.jsonl, summary.json, config.json, ingest_runs.jsonl, "
          "audit_coherence.csv, audit_test_hits.csv, audit_grounding.csv")


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "all"
    commands = {"ingest": cmd_ingest, "check": cmd_check, "all": cmd_all}
    if command not in commands:
        raise SystemExit(f"Usage: python -m src.run [{'|'.join(commands)}]")
    commands[command]()


if __name__ == "__main__":
    main()
