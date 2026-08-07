"""Live end-to-end integration test for the full 7-agent pipeline.

Deliberately NOT in ``tests/`` — depends on a live Ollama. Run manually:

    uv run python test_real_files.py

or, under pytest with the guard set:

    $env:RUN_LIVE_PIPELINE=1; uv run pytest test_real_files.py

When the guard is unset and pytest is used, the test is skipped rather than
failed (deterministic guard, Phase 7.1.16).
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any, cast

import pytest

from logging_config import configure_logging
from pipeline import create_runner_from_config, run_resume_pipeline

configure_logging()

ROOT = Path(__file__).resolve().parent
JOB_PATH = ROOT / "sample" / "jobs" / "3Pillar.txt"
RESUME_PATH = ROOT / "sample" / "resume" / "Peter-Letkeman-Resume.txt"

CANDIDATE_NAME = "Peter Letkeman"
COMPANY_NAME = "3Pillar"

_RUN_LIVE = os.environ.get("RUN_LIVE_PIPELINE", "").strip().lower() in {
    "1",
    "true",
    "yes",
}

_CHECKS: list[tuple[str, bool, str]] = []


def _check(name: str, ok: bool, detail: str = "") -> None:
    _CHECKS.append((name, ok, detail))


def _field(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return cast(dict[str, Any], obj).get(key)
    return getattr(obj, key, None)


def _load_job() -> str:
    if not JOB_PATH.is_file():
        raise FileNotFoundError(f"Sample JD not found: {JOB_PATH}")
    return JOB_PATH.read_text(encoding="utf-8")


def _load_resume() -> str:
    if not RESUME_PATH.is_file():
        raise FileNotFoundError(f"Sample resume not found: {RESUME_PATH}")
    return RESUME_PATH.read_text(encoding="utf-8")


def _start_year(dates: str) -> int | None:
    match = re.search(r"(\d{4})", dates)
    return int(match.group(1)) if match else None


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _strip_markdown(text: str) -> str:
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_>`~]", "", text)
    text = re.sub(r"^[\s]*[-|•]\s*", "", text, flags=re.MULTILINE)
    return text


def _run_pipeline() -> dict[str, Any]:
    job = _load_job()
    resume = _load_resume()
    runner = create_runner_from_config()
    return run_resume_pipeline(
        runner,
        job,
        resume,
        candidate_name=CANDIDATE_NAME,
        company_name=COMPANY_NAME,
    )


def _assert_structure(result: dict[str, Any]) -> None:
    expected = [
        "parsed_job_description",
        "parsed_resume",
        "tailoring_strategy",
        "rewritten_resume",
        "ats_optimized_resume",
        "polished_resume",
        "cover_letter",
    ]
    missing = [key for key in expected if key not in result]
    _check("result keys (7)", not missing, f"missing={missing}")


def _assert_jd_parsing(result: dict[str, Any]) -> None:
    jd = result["parsed_job_description"]
    role_title = _field(jd, "role_title")
    required: list[Any] = _field(jd, "required_skills") or []
    _check("JD role_title non-empty", bool(role_title), repr(role_title))
    _check("JD required_skills non-empty list", bool(required), str(len(required)))


def _assert_resume_parsing(result: dict[str, Any]) -> None:
    parsed = result["parsed_resume"]
    experience: list[Any] = _field(parsed, "experience") or []
    name = _field(parsed, "name") or ""
    _check("resume experience non-empty list", bool(experience), str(len(experience)))
    _check(
        "resume name corresponds to input file",
        "letkeman" in _normalize(name),
        repr(name),
    )


def _assert_gap_analysis(result: dict[str, Any]) -> None:
    strategy = result["tailoring_strategy"]
    missing: list[Any] = _field(strategy, "missing_skills") or []
    _check("gap missing_skills non-empty", bool(missing), str(len(missing)))


def _assert_rewrite_outputs(result: dict[str, Any]) -> None:
    ats = result["ats_optimized_resume"]
    polished = result["polished_resume"]
    _check("ats_optimized_resume truthy", bool(ats), type(ats).__name__)
    _check("polished_resume truthy", bool(polished), type(polished).__name__)


def _assert_cover_letter(result: dict[str, Any]) -> None:
    letter = result["cover_letter"]
    words = len(_strip_markdown(str(letter)).split()) if letter else 0
    _check("cover_letter word count 450-600", 450 <= words <= 600, f"{words} words")


def _assert_chronological(result: dict[str, Any]) -> None:
    parsed = result["parsed_resume"]
    experience: list[Any] = _field(parsed, "experience") or []
    years: list[int] = []
    for entry in experience:
        dates = _field(entry, "dates") or ""
        start = _start_year(dates)
        if start is not None:
            years.append(start)
    ordered = years == sorted(years, reverse=True)
    _check("experience most-recent-first", ordered, str(years))


def _assert_no_fabricated_experience(result: dict[str, Any]) -> None:
    input_text = _load_resume()
    input_companies = set(
        _normalize(company)
        for match in re.finditer(r"^\s*.+?\|\s*([^,(]+)", input_text, re.MULTILINE)
        for company in [match.group(1)]
        if company
    )
    rewrite = result["rewritten_resume"]
    experience: list[Any] = _field(rewrite, "experience") or []
    output_companies = {
        _normalize(_field(entry, "company") or "")
        for entry in experience
        if _field(entry, "company")
    }
    fabricated = output_companies - input_companies
    _check("no fabricated experience", not fabricated, repr(sorted(fabricated)))


def _assert_certifications(result: dict[str, Any]) -> None:
    input_text = _load_resume()
    input_certs = set(
        _normalize(match.group(0))
        for match in re.finditer(r"Certified [A-Za-z0-9 &./-]+", input_text)
    )
    if not input_certs:
        return
    rewrite = result["rewritten_resume"]
    output_text = " ".join(
        [
            _field(rewrite, "summary") or "",
            " ".join(_field(rewrite, "certifications") or []),
            str(result["ats_optimized_resume"] or ""),
            str(result["polished_resume"] or ""),
        ]
    )
    output_norm = _normalize(output_text)
    preserved = [cert for cert in input_certs if _normalize(cert) in output_norm]
    _check(
        "certifications preserved",
        len(preserved) == len(input_certs),
        f"{len(preserved)}/{len(input_certs)}",
    )


def _assert_output_files(result: dict[str, Any]) -> None:
    raw_files: dict[str, Any] = result.get("output_files") or {}
    files: dict[str, Path] = {str(k): Path(v) for k, v in raw_files.items()}
    expected_keys = [
        "resume_plaintext",
        "resume_markdown",
        "resume_docx",
        "resume_pdf",
        "cover_letter_plaintext",
        "cover_letter_markdown",
    ]
    _check(
        "output_files has 6 keys", set(files) == set(expected_keys), str(sorted(files))
    )
    for key in expected_keys:
        path = files[key]
        exists = path.is_file()
        non_empty = exists and path.stat().st_size > 0
        _check(f"{key} written non-empty", exists and non_empty, str(path))
    pattern = re.compile(r"^\d{8}_\d{4}_[a-z0-9-]+_[a-z0-9-]+_(resume|cover_letter)\.")
    _check(
        "output filename pattern",
        all(pattern.search(path.name) for path in files.values()),
        "; ".join(path.name for path in files.values()),
    )


def _run_all() -> None:
    start = time.monotonic()
    result = _run_pipeline()
    elapsed = time.monotonic() - start

    _assert_structure(result)
    _assert_jd_parsing(result)
    _assert_resume_parsing(result)
    _assert_gap_analysis(result)
    _assert_rewrite_outputs(result)
    _assert_cover_letter(result)
    _assert_chronological(result)
    _assert_no_fabricated_experience(result)
    _assert_certifications(result)
    _assert_output_files(result)

    print("\n=== Pipeline Verification Summary ===")
    print(f"elapsed: {elapsed:.1f}s")
    for name, ok, detail in _CHECKS:
        marker = "PASS" if ok else "FAIL"
        suffix = f" ({detail})" if detail else ""
        print(f"  [{marker}] {name}{suffix}")


def main() -> int:
    _run_all()
    failures = [name for name, ok, _ in _CHECKS if not ok]
    if failures:
        print(f"\n{len(failures)} check(s) FAILED: {failures}")
        return 1
    print("\nAll checks passed.")
    return 0


def test_real_files() -> None:
    if not _RUN_LIVE:
        pytest.skip("Set RUN_LIVE_PIPELINE=1 to run the live pipeline integration test")
    _run_all()
    failures = [name for name, ok, _ in _CHECKS if not ok]
    assert not failures, f"Live pipeline checks failed: {failures}"


if __name__ == "__main__":
    raise SystemExit(main())
