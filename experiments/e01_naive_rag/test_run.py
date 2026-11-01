import json
from pathlib import Path

from . import run

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "data" / "raw" / "peps"


def test_corpus_has_100_pinned_documents():
    names = (CORPUS / "MANIFEST.txt").read_text(encoding="utf-8").split()
    assert len(names) >= 100
    assert all((CORPUS / name).is_file() for name in names)


def test_rank_saves_the_definition_passage(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(run, "RESULTS", tmp_path)
    monkeypatch.setattr("sys.argv", ["run", "string literal that occurs as the first statement"])
    run.main()
    assert "pep-0257.rst" in capsys.readouterr().out
    saved = json.loads((tmp_path / "last_run.json").read_text())
    assert any(hit["doc_id"] == "pep-0257.rst" and "first statement" in hit["text"] for hit in saved["retrieval"])


def test_prompt_uses_only_the_configured_context(monkeypatch):
    chunks = [(i, f"[doc-{i}] unique-{i}") for i in range(5)]
    monkeypatch.setattr(run, "top_k", lambda query, chunks, k: [(1.0, start, text) for start, text in chunks[:k]])
    received = []

    def model(prompt, *args, **kwargs):
        received.append(prompt)
        return {"text": "answer", "finish_reason": "stop"}

    monkeypatch.setattr(run, "complete", model)
    row = run.run_query("question", chunks, with_answer=True)
    assert len(row["retrieval"]) == 5
    assert len(row["context_doc_ids"]) == 3
    assert "unique-2" in received[0] and "unique-3" not in received[0]
    assert row["answer"] == "answer" and row["answer_error"] is None


def test_truncated_generation_is_a_failure_with_trace(monkeypatch):
    monkeypatch.setattr(run, "complete", lambda *args, **kwargs: {"text": "partial", "finish_reason": "length"})
    row = run.run_query("a", [(0, "[a] a")], with_answer=True)
    assert row["answer"] is None
    assert "length" in row["answer_error"]
    assert row["generation"]["text"] == "partial"


def test_eval_uses_the_cli_pipeline_and_keeps_no_answer_rows(tmp_path, monkeypatch):
    from . import eval as evaluation

    questions = tmp_path / "questions.csv"
    questions.write_text("question,expected_doc_ids,type\na,a|b,multi-hop\nz,,no-answer\n", encoding="utf-8")
    monkeypatch.setattr(evaluation, "QUESTIONS", questions)
    monkeypatch.setattr(evaluation, "run_config", lambda *args: {})
    monkeypatch.setattr(evaluation, "fixed_chunks_by_manifest", lambda *args: [(0, "[a] a")])
    monkeypatch.setattr(run, "complete", lambda *args, **kwargs: {"text": "I do not know.", "finish_reason": "stop"})
    metrics = evaluation.evaluate(with_answer=True, output=tmp_path / "results")
    assert metrics["recall_at_5"] == 0.5
    assert metrics["scored_questions"] == 1
    assert metrics["no_answer_refusals"] == 1
    rows = json.loads((tmp_path / "results/questions.json").read_text())
    assert rows[1]["recall_at_5"] is None
    assert rows[0]["prompt"] and rows[0]["generation"]


def test_pinned_baseline_reproduces_rankings_and_scores(tmp_path):
    from .eval import evaluate

    first = evaluate(output=tmp_path / "first")
    second = evaluate(output=tmp_path / "second")
    assert first["config"] == second["config"]
    for metric in ["recall_at_5", "mrr_at_5", "all_docs_at_5", "context_recall", "by_type"]:
        assert first[metric] == second[metric]
    rows = [json.loads((tmp_path / name / "questions.json").read_text()) for name in ["first", "second"]]
    assert len(rows[0]) == len(rows[1]) == 30
    for left, right in zip(*rows):
        assert left["retrieval"] == right["retrieval"]
        assert left["prompt"] == right["prompt"]
