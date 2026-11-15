import json
from lesson_generator.memory.store import MemoryStore

def test_persistence_and_recurring_guidance(tmp_path):
    db = tmp_path / "memory.sqlite"
    store = MemoryStore(db)
    for n in range(2):
        run_id = store.new_run_id(); store.start_run(run_id, "Introduction to RAG")
        store.record_attempt(run_id, 1, "draft", {"overall_status":"FAIL"},
            [{"criterion":"beginner_friendly_language", "explanation":"too complex"}],
            ["beginner_friendly_language: use short sentences"])
        store.finish_run(run_id, "rejected")
        assert len(store.history(run_id)) == 1
    reopened = MemoryStore(db)
    guidance = reopened.historical_guidance("Introduction to RAG")
    assert len(guidance) == 1
    assert "2 prior failures" in guidance[0]
    assert "short sentences" in guidance[0]

def test_new_runs_keep_updating_memory(tmp_path):
    store = MemoryStore(tmp_path / "db.sqlite")
    rid = store.new_run_id(); store.start_run(rid, "RAG")
    store.record_attempt(rid, 1, "draft", {"overall_status":"PASS"}, [], [], ["logical_teaching_flow"])
    store.finish_run(rid, "approved")
    assert store.history(rid)[0]["successful_corrections"] == ["logical_teaching_flow"]
