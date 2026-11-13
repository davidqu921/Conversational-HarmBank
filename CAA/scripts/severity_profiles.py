"""Select preserved dual-layer V2 or restored Round 4 single-layer / V3."""
from dataclasses import dataclass
from pathlib import Path

from CAA.scripts.severity_contract import SCHEMA_VERSION, LEGACY_SCHEMA_VERSION, V2_CONTRACT, LEGACY_CONTRACT

LEGACY_SYSTEM = Path("CAA/prompts/caa_severity_system_simple.md")


@dataclass(frozen=True)
class EvaluatorProfile:
    rubric_version: str
    schema_version: str
    output_contract: str
    output_dir_name: str
    system_prompt: Path
    user_template: Path
    supervisor_system_prompt: Path
    supervisor_user_template: Path


def resolve_profile(family: str, double_layer: bool, version: str | None) -> EvaluatorProfile:
    if family not in {"conversation", "isolated"}:
        raise ValueError(f"Unknown evaluator family: {family}")
    if version not in {None, "v2", "v3"}:
        raise ValueError(f"Unknown evaluator version: {version}")
    if not double_layer and version == "v2":
        raise ValueError("V2 is retained for --double-layer only; single-layer uses the restored Round 4 prompt")
    stem = "caa" if family == "conversation" else "isolated"
    if double_layer and version != "v3":
        return EvaluatorProfile(
            "conversation_human_aligned_v2" if stem == "caa" else "isolated_output_only_v2",
            SCHEMA_VERSION, V2_CONTRACT,
            "dual-layer_human-aligned-v2_llama31_and_mistral" if stem == "caa" else "dual-layer_output-only-v2_llama31_and_mistral",
            Path(f"CAA/prompts/{stem}_severity_system.md"),
            Path(f"CAA/prompts/{stem}_severity_user_template.md"),
            Path(f"CAA/prompts/{stem}_severity_supervisor_system.md"),
            Path(f"CAA/prompts/{stem}_severity_supervisor_user_template.md"))
    template = Path(f"CAA/prompts/{stem}_severity_legacy_user_template.md")
    return EvaluatorProfile(
        f"{family}_round4_restored_v3", LEGACY_SCHEMA_VERSION, LEGACY_CONTRACT,
        "dual-layer_round4-v3_llama31_and_mistral" if double_layer else "single-layer_round4-v3_llama31",
        LEGACY_SYSTEM, template, LEGACY_SYSTEM, template)


def apply_prompt_paths(args, profile: EvaluatorProfile) -> None:
    """Keep V2 overrides; restored runs must use the exact shared legacy prompt."""
    for name in ("system_prompt", "user_template", "supervisor_system_prompt", "supervisor_user_template"):
        expected = getattr(profile, name)
        provided = getattr(args, name, None)
        if provided is not None and profile.output_contract == LEGACY_CONTRACT:
            from CAA.scripts.caa_common import resolve_project_path
            if resolve_project_path(provided) != resolve_project_path(expected):
                raise ValueError(f"--{name.replace('_', '-')} overrides are supported only for dual-layer V2")
        setattr(args, name, provided if provided is not None else expected)
