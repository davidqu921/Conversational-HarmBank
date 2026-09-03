from types import SimpleNamespace

from CAA.scripts.code_caa_severity_with_hf import (
    merge_supervised_records,
    model_config_for_id,
    render_supervisor_prompt,
)


def coding(record_id: str, severity: str, *, error: str | None = None) -> dict:
    return {
        "id": record_id,
        "llm_output": None if error else {"severity": severity, "reasoning": "evidence"},
        "error": error,
        "duration_s": 1.0,
    }


def test_supervisor_changes_only_positive_first_layer_records() -> None:
    first = [coding("safe", "0 - Safe"), coding("false-positive", "2 - Major")]
    supervisor = [coding("false-positive", "0 - Safe")]

    merged = merge_supervised_records(first, supervisor, "mistral")
    by_id = {row["id"]: row for row in merged}

    assert by_id["safe"]["llm_output"]["severity"] == "0 - Safe"
    assert by_id["safe"]["supervision_status"] == "not_requested"
    assert by_id["false-positive"]["first_layer_output"]["severity"] == "2 - Major"
    assert by_id["false-positive"]["llm_output"]["severity"] == "0 - Safe"
    assert by_id["false-positive"]["supervision_status"] == "completed"


def test_supervisor_can_raise_positive_severity_and_errors_fall_back() -> None:
    first = [coding("raised", "1 - Minor"), coding("fallback", "1 - Minor")]
    supervisor = [coding("raised", "2 - Major"), coding("fallback", "0 - Safe", error="timeout")]

    merged = merge_supervised_records(first, supervisor, "mistral")
    by_id = {row["id"]: row for row in merged}

    assert by_id["raised"]["llm_output"]["severity"] == "2 - Major"
    assert by_id["fallback"]["llm_output"]["severity"] == "1 - Minor"
    assert by_id["fallback"]["supervision_status"] == "error_fallback"


def test_supervisor_prompt_includes_provisional_result() -> None:
    prompt = render_supervisor_prompt(
        "{{CONVERSATION_ID}}|{{ATTEMPT}}|{{SOURCE_PRIMARY_ATTACK_VECTOR}}|"
        "{{FIRST_LAYER_SEVERITY}}|{{FIRST_LAYER_REASONING}}|{{TRANSCRIPT}}",
        {"id": "caa_1", "transcript_text": "Student: x\nSteve: no"},
        {"attempt": "Slur", "source_primary_attack_vector": "Text trick"},
        {"severity": "1 - Minor", "reasoning": "proposal"},
    )
    assert prompt == "caa_1|Slur|Text trick|1 - Minor|proposal|Student: x\nSteve: no"


def test_model_change_drops_incompatible_local_path() -> None:
    config = SimpleNamespace(raw={"attacker_model": {
        "model_id": "meta-llama/Llama-3.1-8B-Instruct",
        "local_path": "/cache/llama",
        "device_map": "auto",
    }})

    supervisor = model_config_for_id(config, "mistralai/Mistral-7B-Instruct-v0.3")

    assert "local_path" not in supervisor
    assert supervisor["model_id"] == "mistralai/Mistral-7B-Instruct-v0.3"
    assert supervisor["device_map"] == "auto"
