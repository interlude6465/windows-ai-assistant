import json
from datetime import datetime
from pathlib import Path

from spectral.memory_models import ExecutionMemory
from spectral.memory_search import MemorySearch


def test_execution_memory_filters_none_file_locations() -> None:
    mem = ExecutionMemory(
        execution_id="exec-1",
        timestamp=datetime.now(),
        user_request="do something",
        description="test",
        code_generated="print('hi')",
        file_locations=[None, "", "C:\\temp\\file.py"],
        output="ok",
        success=True,
        tags=[],
    )

    assert mem.file_locations == ["C:\\temp\\file.py"]


def test_memory_search_load_execution_metadata_filters_none(tmp_path, monkeypatch) -> None:
    # Arrange: create a fake ~/.spectral/execution_metadata directory
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    metadata_dir = tmp_path / ".spectral" / "execution_metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    meta_path = metadata_dir / "test.json"
    meta = {
        "run_id": "run-1",
        "timestamp": datetime.now().isoformat(),
        "prompt": "do something",
        "filename": "main.py",
        "code": "print('hi')",
        "execution_status": "success",
        "execution_output": "ok",
        "execution_error": "",
        "desktop_path": None,
        "sandbox_path": None,
        "file_locations": [None, "C:\\Users\\test\\Desktop\\main.py"],
    }
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    # Act
    search = MemorySearch()
    executions = search.load_execution_metadata()

    # Assert
    assert len(executions) == 1
    assert executions[0].file_locations == ["C:\\Users\\test\\Desktop\\main.py"]

    # Self-heal should persist cleaned file_locations back to the JSON metadata
    updated = json.loads(meta_path.read_text(encoding="utf-8"))
    assert updated["file_locations"] == ["C:\\Users\\test\\Desktop\\main.py"]
