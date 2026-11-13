"""Automatic retrieval metrics (Hit@1, Evidence Hit@3) with full per-query traces.

A retrieved chunk is a *hit* when it comes from a gold (source_id, page) AND
contains the whole gold evidence quote after whitespace/Unicode normalization.
Coherence and grounding are NOT inferred here; they are labelled by hand.
"""
import re
import unicodedata
from collections import defaultdict
from typing import Any

from .ingestion import normalize_text


def norm(text: str) -> str:
    """Normalization used for matching evidence (same pipeline as ingestion + lowercase)."""
    text = normalize_text(unicodedata.normalize("NFC", text))
    return re.sub(r"\s+", " ", text).strip().lower()


def gold_list(question: dict[str, Any]) -> list[dict[str, Any]]:
    """All accepted gold evidences; ``gold`` (list) overrides the single-gold fields."""
    if question.get("gold"):
        return question["gold"]
    return [{"source_id": question["gold_source_id"], "page": question["gold_page"],
             "evidence_quote": question["evidence_quote"]}]


def is_hit(hit: dict[str, Any], question: dict[str, Any]) -> bool:
    text = norm(hit["text"])
    return any(hit["document_id"] == g["source_id"] and int(hit["page"]) == int(g["page"])
               and norm(g["evidence_quote"]) in text for g in gold_list(question))


def _same_page(hit: dict[str, Any], question: dict[str, Any]) -> bool:
    return any(hit["document_id"] == g["source_id"] and int(hit["page"]) == int(g["page"])
               for g in gold_list(question))


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]],
                   applied_filter: dict[str, Any] | None = None) -> dict[str, Any]:
    flags = [is_hit(h, question) for h in hits]
    page_flags = [_same_page(h, question) for h in hits]
    filt = question.get("filter")
    compliance = None
    if filt:  # does every returned chunk satisfy the question's filter? (checked for all strategies)
        compliance = all(all(str(h["metadata"].get(k)) == str(v) for k, v in filt.items())
                         for h in hits) if hits else False
    return {
        "id": question["id"],
        "split": question["split"],
        "type": question.get("type"),
        "question": question["question"],
        "expected_answer": question.get("expected_answer"),
        "gold": gold_list(question),
        "filter": filt,
        "applied_filter": applied_filter,
        "n_hits": len(hits),
        "hit_at_1": bool(flags and flags[0]),
        "hit_at_3": any(flags[:3]),
        "hit_flags": flags,
        # gold page retrieved but quote not fully inside one chunk -> likely split evidence
        "gold_page_without_full_evidence": any(p and not f for p, f in zip(page_flags[:3], flags[:3]))
                                           and not any(flags[:3]),
        "filter_compliance_top3": compliance,
        "hits": hits,
    }


def summarize(traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for t in traces:
        groups[(t["strategy"], t["split"])].append(t)
    rows = []
    for (strategy, split), ts in sorted(groups.items()):
        n = len(ts)
        h1 = sum(t["hit_at_1"] for t in ts)
        h3 = sum(t["hit_at_3"] for t in ts)
        filtered = [t for t in ts if t["filter"]]
        fc = sum(bool(t["filter_compliance_top3"]) for t in filtered)
        rows.append({
            "strategy": strategy, "split": split, "n": n,
            "hit1": h1, "hit3": h3,
            "hit1_str": f"{h1}/{n}", "hit3_str": f"{h3}/{n}",
            "hit1_pct": round(100 * h1 / n, 1) if n else None,
            "hit3_pct": round(100 * h3 / n, 1) if n else None,
            "filter_compliance_str": f"{fc}/{len(filtered)}" if filtered else "N/A",
            "split_evidence_cases": [t["id"] for t in ts if t["gold_page_without_full_evidence"]],
            "misses_at_3": [t["id"] for t in ts if not t["hit_at_3"]],
        })
    return rows
