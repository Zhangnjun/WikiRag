from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.main import app

EXAMPLES_DIR = ROOT / "examples"
OUTPUTS_DIR = ROOT / "outputs"
API_KEY = "change-me"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def seed_demo_data(client: TestClient) -> None:
    demo_sources = load_json(EXAMPLES_DIR / "demo_sources.json")
    headers = {"X-API-Key": API_KEY}
    for item in demo_sources:
        source_resp = client.post(
            "/api/source/import",
            json={**item, "skip_if_exists": True, "overwrite_if_exists": False},
            headers=headers,
        )
        source_resp.raise_for_status()
        source_id = source_resp.json()["source_id"]
        normalize_resp = client.post(
            "/api/knowledge/normalize",
            json={"source_id": source_id, "use_ai": False},
            headers=headers,
        )
        normalize_resp.raise_for_status()


def evaluate_case(client: TestClient, case: dict) -> dict:
    headers = {"X-API-Key": API_KEY}
    session_id = None
    for pre_query in case.get("pre_queries", []):
        response = client.post(
            "/api/rag/query",
            json={
                "query": pre_query,
                "top_k": 3,
                "use_rerank": True,
                "use_ai": False,
                "filters": {"doc_type": case.get("expected_doc_type")},
                "debug": False,
                "session_id": session_id,
            },
            headers=headers,
        )
        response.raise_for_status()
        session_id = response.json()["session_id"]

    response = client.post(
        "/api/rag/query",
        json={
            "query": case["query"],
            "top_k": 3,
            "use_rerank": True,
            "use_ai": False,
            "filters": {"doc_type": case.get("expected_doc_type")},
            "debug": True,
            "session_id": session_id,
        },
        headers=headers,
    )
    response.raise_for_status()
    body = response.json()

    retrieved_text = "\n".join(item["content"] for item in body["retrieved_chunks"])
    citation_titles = [item["doc_title"] for item in body["citations"]]
    matched_keywords = [kw for kw in case.get("expected_keywords", []) if kw in retrieved_text or kw in body["answer"]]
    matched_sections = [
        section
        for section in case.get("expected_should_hit_sections", [])
        if any(section in item["section_title"] for item in body["retrieved_chunks"])
    ]
    matched_not_miss = [item for item in case.get("expected_should_not_miss", []) if item in retrieved_text or item in body["answer"]]

    hit_score = len(matched_keywords) + len(matched_sections) + len(matched_not_miss)
    total_expect = (
        len(case.get("expected_keywords", []))
        + len(case.get("expected_should_hit_sections", []))
        + len(case.get("expected_should_not_miss", []))
    ) or 1
    ratio = hit_score / total_expect
    if ratio >= 0.7:
        verdict = "success-like"
    elif ratio >= 0.35:
        verdict = "weak-hit"
    else:
        verdict = "miss"

    return {
        "case_id": case["case_id"],
        "title": case["title"],
        "query": case["query"],
        "verdict": verdict,
        "answer_summary": body["answer"][:240],
        "citations": citation_titles,
        "retrieved_top_chunks": [
            {
                "chunk_id": item["chunk_id"],
                "section_title": item["section_title"],
                "score": item["score"],
                "content_summary": item["content"][:180],
            }
            for item in body["retrieved_chunks"]
        ],
        "matched_keywords": matched_keywords,
        "matched_sections": matched_sections,
        "matched_should_not_miss": matched_not_miss,
        "session_id": body["session_id"],
        "debug_info": body.get("debug_info", {}),
        "notes": case.get("notes", ""),
    }


def write_reports(results: list) -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "total_cases": len(results),
        "success_like_count": sum(1 for item in results if item["verdict"] == "success-like"),
        "weak_hit_count": sum(1 for item in results if item["verdict"] == "weak-hit"),
        "miss_count": sum(1 for item in results if item["verdict"] == "miss"),
    }
    json_payload = {"summary": summary, "results": results}
    (OUTPUTS_DIR / "rag_eval_report.json").write_text(
        json.dumps(json_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# RAG Eval Report",
        "",
        "## Summary",
        "",
        "- total cases: %s" % summary["total_cases"],
        "- success-like count: %s" % summary["success_like_count"],
        "- weak-hit count: %s" % summary["weak_hit_count"],
        "- miss count: %s" % summary["miss_count"],
        "",
        "## Cases",
        "",
    ]
    for item in results:
        lines.extend(
            [
                "### %s %s" % (item["case_id"], item["title"]),
                "",
                "- verdict: %s" % item["verdict"],
                "- query: %s" % item["query"],
                "- citations: %s" % ", ".join(item["citations"]),
                "- matched keywords: %s" % ", ".join(item["matched_keywords"]),
                "- matched sections: %s" % ", ".join(item["matched_sections"]),
                "- matched should-not-miss: %s" % ", ".join(item["matched_should_not_miss"]),
                "- answer summary: %s" % item["answer_summary"],
                "",
            ]
        )
    (OUTPUTS_DIR / "rag_eval_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    client = TestClient(app)
    seed_demo_data(client)
    cases = load_json(EXAMPLES_DIR / "rag_eval_cases.json")
    results = [evaluate_case(client, case) for case in cases]
    write_reports(results)

    summary = {
        "total cases": len(results),
        "success-like count": sum(1 for item in results if item["verdict"] == "success-like"),
        "weak-hit count": sum(1 for item in results if item["verdict"] == "weak-hit"),
        "miss count": sum(1 for item in results if item["verdict"] == "miss"),
    }
    print("RAG Eval Summary")
    for key, value in summary.items():
        print("- %s: %s" % (key, value))
    print("Reports written to:")
    print("- %s" % (OUTPUTS_DIR / "rag_eval_report.md"))
    print("- %s" % (OUTPUTS_DIR / "rag_eval_report.json"))


if __name__ == "__main__":
    main()
