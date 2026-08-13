"""AgentRunner / run_resume_pipeline orchestration tests (Phase 7.2.2).

Runs the full 7-agent chain with stub agents (no real LLM) and asserts the
result contract: the 7 stage keys plus ``output_files`` with its 6 formats.
Because ``run_resume_pipeline`` wraps ``_run_pipeline_core`` in ``asyncio.run``
(see AGENTS.md), the async tests drive ``_run_pipeline_core`` directly, and a
sync test exercises the public ``run_resume_pipeline`` wrapper.

Covers Phase 7.2.2.1 (async end-to-end), 7.2.2.2 (dependency threading),
7.2.2.3 (error propagation), 7.2.2.4 (company/candidate passthrough), and
7.2.2.5 (``AgentRunner`` unit).
"""

from pathlib import Path
from typing import Any

import pytest

from client.errors import LLMConnectionError
from client.models import (
    ATSComplianceOutput,
    CoverLetterOutput,
    ExperienceEntry,
    GapAnalysisOutput,
    JDParsingOutput,
    ResumeParsingOutput,
    RewriteOutput,
    TonePolishingOutput,
)
from client.templates.renderer import ResumeRenderer
from pipeline import AgentRunner, PipelineAgent, _run_pipeline_core, run_resume_pipeline

JD_TEXT = "Senior Backend Engineer at Acme Corp"
RESUME_TEXT = "Jane Doe, senior engineer with 10 years of experience."


class StubAgent:
    """Minimal agent stub returning a fixed output and recording its inputs."""

    def __init__(self, output: Any) -> None:
        self.output = output
        self.inputs: list[dict[str, Any]] = []

    async def run(self, inputs: dict[str, Any]) -> Any:
        self.inputs.append(inputs)
        return self.output


def _stub_runner() -> tuple[AgentRunner, dict[str, StubAgent]]:
    """Build a runner wired to 7 stub agents returning fixed model outputs."""
    jd = JDParsingOutput(
        role_title="Senior Backend Engineer",
        company_name="Acme Corp",
        seniority_level="senior",
        required_skills=["Python", "PostgreSQL"],
    )
    resume = ResumeParsingOutput(
        name="Jane Doe",
        summary="Senior engineer with 10 years of experience.",
        skills=["Python", "PostgreSQL"],
        experience=[
            ExperienceEntry(
                title="Staff Engineer",
                company="Acme Corp",
                dates="2020-2024",
                responsibilities=["Led platform team"],
            )
        ],
        education=["B.Sc. Computer Science"],
    )
    gap = GapAnalysisOutput(
        missing_skills=["Kubernetes"],
        strong_matches=["Python"],
    )
    rewrite = RewriteOutput(
        summary="Senior engineer with 10+ years experience.",
        skills=["Python", "PostgreSQL", "Kubernetes"],
        experience=[
            ExperienceEntry(
                title="Staff Engineer",
                company="Acme Corp",
                dates="2020-2024",
                responsibilities=["Led platform team"],
            )
        ],
    )
    ats = ATSComplianceOutput(
        ats_score=95,
        missing_keywords=[],
        final_resume="Optimized resume body.",
    )
    tone = TonePolishingOutput(polished_resume="Polished resume body.")
    cover = CoverLetterOutput(
        cover_letter=(
            "Dear Hiring Manager,\n\nI am excited to apply for the role.\n\n"
            "Sincerely,\nJane Doe"
        )
    )

    agents = {
        "jd_parsing_agent": StubAgent(jd),
        "resume_parsing_agent": StubAgent(resume),
        "gap_analysis_agent": StubAgent(gap),
        "resume_rewrite_agent": StubAgent(rewrite),
        "ats_compliance_agent": StubAgent(ats),
        "tone_polishing_agent": StubAgent(tone),
        "cover_letter_agent": StubAgent(cover),
    }
    runner = AgentRunner(agents)
    return runner, agents


def _fake_render_all(
    self,
    resume,
    cover_letter,
    *,
    candidate_name: str,
    company_name: str,
    output_dir,
    **kwargs,
) -> dict[str, Path]:
    """Stand-in for ``ResumeRenderer.render_all`` returning the 6 format keys."""
    return {
        "resume_plaintext": Path(output_dir) / "resume.txt",
        "resume_markdown": Path(output_dir) / "resume.md",
        "resume_docx": Path(output_dir) / "resume.docx",
        "resume_pdf": Path(output_dir) / "resume.pdf",
        "cover_letter_plaintext": Path(output_dir) / "cover_letter.txt",
        "cover_letter_markdown": Path(output_dir) / "cover_letter.md",
    }


class TestPipelineEndToEnd:
    """7.2.2.1: async end-to-end run with stub agents."""

    STAGE_KEYS = (
        "parsed_job_description",
        "parsed_resume",
        "tailoring_strategy",
        "rewritten_resume",
        "ats_optimized_resume",
        "polished_resume",
        "cover_letter",
    )

    async def test_async_core_returns_all_stage_keys(self, monkeypatch) -> None:
        runner, agents = _stub_runner()
        monkeypatch.setattr(ResumeRenderer, "render_all", _fake_render_all)

        result = await _run_pipeline_core(
            runner,
            JD_TEXT,
            RESUME_TEXT,
            candidate_name="Jane Doe",
            company_name="Acme Corp",
        )

        for key in self.STAGE_KEYS:
            assert key in result
        assert len(result["output_files"]) == 6
        assert all(isinstance(p, Path) for p in result["output_files"].values())

    async def test_each_stub_agent_runs_exactly_once(self, monkeypatch) -> None:
        runner, agents = _stub_runner()
        monkeypatch.setattr(ResumeRenderer, "render_all", _fake_render_all)

        await _run_pipeline_core(
            runner,
            JD_TEXT,
            RESUME_TEXT,
            candidate_name="Jane Doe",
            company_name="Acme Corp",
        )

        for name, agent in agents.items():
            assert len(agent.inputs) == 1, (
                f"{name} was called {len(agent.inputs)} times"
            )

    async def test_stage_outputs_thread_through_results(self, monkeypatch) -> None:
        runner, agents = _stub_runner()
        monkeypatch.setattr(ResumeRenderer, "render_all", _fake_render_all)

        result = await _run_pipeline_core(
            runner,
            JD_TEXT,
            RESUME_TEXT,
            candidate_name="Jane Doe",
            company_name="Acme Corp",
        )

        assert isinstance(result["parsed_job_description"], JDParsingOutput)
        assert isinstance(result["parsed_resume"], ResumeParsingOutput)
        assert isinstance(result["tailoring_strategy"], GapAnalysisOutput)
        assert isinstance(result["rewritten_resume"], RewriteOutput)
        assert result["ats_optimized_resume"] == "Optimized resume body."
        assert result["polished_resume"] == "Polished resume body."
        assert "cover_letter" in result

    def test_run_resume_pipeline_wrapper_returns_same_contract(
        self, monkeypatch
    ) -> None:
        runner, agents = _stub_runner()
        monkeypatch.setattr(ResumeRenderer, "render_all", _fake_render_all)

        result = run_resume_pipeline(
            runner,
            JD_TEXT,
            RESUME_TEXT,
            candidate_name="Jane Doe",
            company_name="Acme Corp",
        )

        for key in self.STAGE_KEYS:
            assert key in result
        assert len(result["output_files"]) == 6


class TestPipelineDependencyThreading:
    """7.2.2.2: each agent receives the preceding stage's output."""

    async def test_gap_analysis_receives_jd_and_resume(self, monkeypatch) -> None:
        runner, agents = _stub_runner()
        monkeypatch.setattr(ResumeRenderer, "render_all", _fake_render_all)

        await _run_pipeline_core(
            runner,
            JD_TEXT,
            RESUME_TEXT,
            candidate_name="Jane Doe",
            company_name="Acme Corp",
        )

        gap_inputs = agents["gap_analysis_agent"].inputs[0]
        assert gap_inputs["parsed_job_description"] == agents["jd_parsing_agent"].output
        assert isinstance(gap_inputs["parsed_resume"], ResumeParsingOutput)

    async def test_rewrite_receives_resume_and_tailoring(self, monkeypatch) -> None:
        runner, agents = _stub_runner()
        monkeypatch.setattr(ResumeRenderer, "render_all", _fake_render_all)

        await _run_pipeline_core(
            runner,
            JD_TEXT,
            RESUME_TEXT,
            candidate_name="Jane Doe",
            company_name="Acme Corp",
        )

        rewrite_inputs = agents["resume_rewrite_agent"].inputs[0]
        assert isinstance(rewrite_inputs["parsed_resume"], ResumeParsingOutput)
        assert (
            rewrite_inputs["tailoring_strategy"] == agents["gap_analysis_agent"].output
        )

    async def test_ats_receives_rewritten_resume(self, monkeypatch) -> None:
        runner, agents = _stub_runner()
        monkeypatch.setattr(ResumeRenderer, "render_all", _fake_render_all)

        await _run_pipeline_core(
            runner,
            JD_TEXT,
            RESUME_TEXT,
            candidate_name="Jane Doe",
            company_name="Acme Corp",
        )

        ats_inputs = agents["ats_compliance_agent"].inputs[0]
        assert isinstance(ats_inputs["rewritten_resume"], RewriteOutput)

    async def test_tone_receives_ats_frame(self, monkeypatch) -> None:
        runner, agents = _stub_runner()
        monkeypatch.setattr(ResumeRenderer, "render_all", _fake_render_all)

        await _run_pipeline_core(
            runner,
            JD_TEXT,
            RESUME_TEXT,
            candidate_name="Jane Doe",
            company_name="Acme Corp",
        )

        tone_inputs = agents["tone_polishing_agent"].inputs[0]
        assert tone_inputs["ats_optimized_resume"] == "Optimized resume body."

    async def test_cover_letter_receives_chain_outputs(self, monkeypatch) -> None:
        runner, agents = _stub_runner()
        monkeypatch.setattr(ResumeRenderer, "render_all", _fake_render_all)

        await _run_pipeline_core(
            runner,
            JD_TEXT,
            RESUME_TEXT,
            candidate_name="Jane Doe",
            company_name="Acme Corp",
        )

        cover_inputs = agents["cover_letter_agent"].inputs[0]
        assert (
            cover_inputs["parsed_job_description"] == agents["jd_parsing_agent"].output
        )
        assert isinstance(cover_inputs["parsed_resume"], ResumeParsingOutput)
        assert cover_inputs["tailoring_strategy"] == agents["gap_analysis_agent"].output


class RaisingAgent:
    """Stub agent that raises a fixed exception from ``run``."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    async def run(self, inputs: dict[str, Any]) -> Any:
        raise self.error


class TestPipelineErrorPropagation:
    """7.2.2.3: LLM failures surface and no missing key is fabricated."""

    async def test_raising_agent_propagates_llm_error(self, monkeypatch) -> None:
        runner, agents = _stub_runner()
        agents["tone_polishing_agent"] = RaisingAgent(LLMConnectionError("ollama down"))
        failing_runner = AgentRunner(agents)
        monkeypatch.setattr(ResumeRenderer, "render_all", _fake_render_all)

        with pytest.raises(LLMConnectionError):
            await _run_pipeline_core(
                failing_runner,
                JD_TEXT,
                RESUME_TEXT,
                candidate_name="Jane Doe",
                company_name="Acme Corp",
            )

    def test_run_resume_pipeline_wrapper_surfaces_error(self, monkeypatch) -> None:
        runner, agents = _stub_runner()
        agents["cover_letter_agent"] = RaisingAgent(LLMConnectionError("ollama down"))
        failing_agent = AgentRunner(agents)
        monkeypatch.setattr(ResumeRenderer, "render_all", _fake_render_all)

        with pytest.raises(LLMConnectionError):
            run_resume_pipeline(
                failing_agent,
                JD_TEXT,
                RESUME_TEXT,
                candidate_name="Jane Doe",
                company_name="Acme Corp",
            )


class _RecordingRenderAll:
    """Records render_all kwargs while delegating to ``_fake_render_all``."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        resume,
        cover_letter,
        *,
        candidate_name: str,
        company_name: str,
        output_dir,
        **kwargs,
    ) -> dict[str, Path]:
        self.calls.append(
            {
                "candidate_name": candidate_name,
                "company_name": company_name,
                "output_dir": output_dir,
                "resume_template": kwargs.get("resume_template", "modern"),
                "resume_templates": kwargs.get("resume_templates"),
            }
        )
        return {
            "resume_plaintext": Path(output_dir) / "resume.txt",
            "resume_markdown": Path(output_dir) / "resume.md",
            "resume_docx": Path(output_dir) / "resume.docx",
            "resume_pdf": Path(output_dir) / "resume.pdf",
            "cover_letter_plaintext": Path(output_dir) / "cover_letter.txt",
            "cover_letter_markdown": Path(output_dir) / "cover_letter.md",
        }


class TestCompanyCandidatePassthrough:
    """7.2.2.4: candidate/company reach render_all and gate rendering."""

    async def test_name_and_company_reach_renderer(self, monkeypatch) -> None:
        runner, _ = _stub_runner()
        recorder = _RecordingRenderAll()
        monkeypatch.setattr(ResumeRenderer, "render_all", recorder)

        result = await _run_pipeline_core(
            runner,
            JD_TEXT,
            RESUME_TEXT,
            candidate_name="Jane Doe",
            company_name="Acme Corp",
        )

        assert len(recorder.calls) == 1
        assert recorder.calls[0]["candidate_name"] == "Jane Doe"
        assert recorder.calls[0]["company_name"] == "Acme Corp"
        assert "output_files" in result

    async def test_empty_candidate_name_skips_rendering(self, monkeypatch) -> None:
        runner, _ = _stub_runner()
        recorder = _RecordingRenderAll()
        monkeypatch.setattr(ResumeRenderer, "render_all", recorder)

        result = await _run_pipeline_core(
            runner, JD_TEXT, RESUME_TEXT, candidate_name=""
        )

        assert len(recorder.calls) == 0
        assert result["output_files"] == {}

    async def test_resume_template_reaches_renderer(self, monkeypatch) -> None:
        runner, _ = _stub_runner()
        recorder = _RecordingRenderAll()
        monkeypatch.setattr(ResumeRenderer, "render_all", recorder)

        await _run_pipeline_core(
            runner,
            JD_TEXT,
            RESUME_TEXT,
            candidate_name="Jane Doe",
            company_name="Acme Corp",
            resume_template="classic",
        )

        assert len(recorder.calls) == 1
        assert recorder.calls[0]["resume_template"] == "classic"
        assert recorder.calls[0]["resume_templates"] is None

    async def test_resume_templates_list_reaches_renderer(self, monkeypatch) -> None:
        runner, _ = _stub_runner()
        recorder = _RecordingRenderAll()
        monkeypatch.setattr(ResumeRenderer, "render_all", recorder)

        await _run_pipeline_core(
            runner,
            JD_TEXT,
            RESUME_TEXT,
            candidate_name="Jane Doe",
            company_name="Acme Corp",
            resume_templates=["modern", "classic", "minimal"],
        )

        assert len(recorder.calls) == 1
        assert recorder.calls[0]["resume_templates"] == ["modern", "classic", "minimal"]

    async def test_default_resume_template_is_modern(self, monkeypatch) -> None:
        runner, _ = _stub_runner()
        recorder = _RecordingRenderAll()
        monkeypatch.setattr(ResumeRenderer, "render_all", recorder)

        await _run_pipeline_core(
            runner,
            JD_TEXT,
            RESUME_TEXT,
            candidate_name="Jane Doe",
            company_name="Acme Corp",
        )

        assert len(recorder.calls) == 1
        assert recorder.calls[0]["resume_template"] == "modern"


class TestAgentRunnerUnit:
    """7.2.2.5: AgentRunner dispatch, chat contract, and failure handling."""

    async def test_run_agent_async_dispatches_correct_agent(self) -> None:
        runner, agents = _stub_runner()

        output = await runner.run_agent_async(
            "resume_parsing_agent", {"resume": RESUME_TEXT}
        )

        assert output is agents["resume_parsing_agent"].output
        assert agents["resume_parsing_agent"].inputs[0] == {"resume": RESUME_TEXT}

    async def test_run_agent_async_unknown_agent_raises_key_error(self) -> None:
        runner, _ = _stub_runner()
        with pytest.raises(KeyError):
            await runner.run_agent_async("bogus_agent", {})

    async def test_pipeline_agent_carries_chat_contract(self, fake_client) -> None:
        client = fake_client(response="{}")
        agent = PipelineAgent(client, "test-purpose")

        await agent.run(
            {
                "prompt": "Do the thing",
                "output": ["result"],
                "rules": ["Be strict"],
                "context_key": "context value",
            }
        )

        assert len(client.calls) == 1
        call = client.calls[0]
        assert call["purpose"] == "test-purpose"
        assert call["response_format"] == "json"
        assert call["inputs"] == ["context_key: context value"]
        assert call["json_schema"] is None

    async def test_runner_propagates_agent_exception(self) -> None:
        failing = RaisingAgent(LLMConnectionError("down"))
        runner = AgentRunner({"gap_analysis_agent": failing})

        with pytest.raises(LLMConnectionError):
            await runner.run_agent_async("gap_analysis_agent", {})
