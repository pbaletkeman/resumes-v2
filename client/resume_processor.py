"""
resume_processor.py
End-to-end resume optimization pipeline.

Orchestrates format detection, gap analysis, resume rewriting, and
ATS compliance checking using an LLM client and the FormatDetector.
"""

from client.model_client import ModelClient
from client.format_detector import FormatDetector


class ResumeProcessor:
    """Processes a job description and resume through an optimization pipeline.

    Steps:
        1. Parse both documents with ``FormatDetector`` (no LLM).
        2. Run gap analysis via LLM.
        3. Rewrite the resume via LLM.
        4. Check ATS compliance via LLM.

    Args:
        client: An LLM client implementing ``ModelClient.chat``.
    """

    def __init__(self, client: ModelClient) -> None:
        """Initialize the processor with an LLM client.

        Args:
            client: An LLM client implementing ``ModelClient.chat``.
        """
        self.client = client

    async def optimize_resume(
        self, job_description: str, resume: str
    ) -> dict[str, str | dict[str, str | list[str]]]:
        """Run the full resume optimization pipeline.

        Args:
            job_description: Raw job description text (any format).
            resume: Raw resume text (any format).

        Returns:
            Dictionary containing:
                - ``parsed_jd``: Structured job description.
                - ``parsed_resume``: Structured resume.
                - ``gap_analysis``: LLM-generated gap analysis.
                - ``rewritten_resume``: Rewritten resume text.
                - ``ats_compliance``: ATS compliance score and issues.
        """
        jd_parsed = FormatDetector.parse_job_description(job_description)
        resume_parsed = FormatDetector.parse_resume(resume)

        gap_analysis = await self._gap_analysis(jd_parsed, resume_parsed)
        rewritten = await self._rewrite_resume(resume_parsed, gap_analysis)
        ats_check = await self._ats_compliance(rewritten)

        return {
            "parsed_jd": jd_parsed,
            "parsed_resume": resume_parsed,
            "gap_analysis": gap_analysis,
            "rewritten_resume": rewritten,
            "ats_compliance": ats_check,
        }

    async def _gap_analysis(
        self, jd: dict[str, str | list[str]], resume: dict[str, str | list[str]]
    ) -> str:
        """Analyze gaps between a job description and resume.

        Args:
            jd: Parsed job description dictionary.
            resume: Parsed resume dictionary.

        Returns:
            LLM-generated gap analysis text.
        """
        prompt = f"""\
Compare this resume with the job description.
List:
1. Missing skills
2. Weak areas
3. Keyword gaps
4. Recommendation

Resume skills: {', '.join(resume['skills'][:10])}
JD requirements: {', '.join(jd['requirements'][:10])}"""
        result = await self.client.chat(
            purpose="Gap analysis specialist",
            prompt=prompt,
            output=["missing_skills", "weak_areas", "keywords", "recommendation"],
            rules=["Be concise", "Focus on job match"],
            inputs=[resume.get("raw", ""), jd.get("raw", "")],
        )
        return result

    async def _rewrite_resume(
        self, resume: dict[str, str | list[str]], gap_analysis: str
    ) -> str:
        """Rewrite resume bullet points to better match the target job.

        Args:
            resume: Parsed resume dictionary.
            gap_analysis: Gap analysis text from ``_gap_analysis``.

        Returns:
            LLM-rewritten resume bullet points.
        """
        prompt = f"""\
Rewrite these resume bullet points to match the job better.
Address these gaps: {gap_analysis[:200]}

Current bullets:
{chr(10).join(resume['experience'][:5])}

Produce rewritten bullets only."""
        result = await self.client.chat(
            purpose="Resume rewriter",
            prompt=prompt,
            output=["rewritten_bullets"],
            rules=["Use strong action verbs", "Include metrics", "Match keywords"],
            inputs=[gap_analysis[:300]],
        )
        return result

    async def _ats_compliance(self, rewritten: str) -> str:
        """Check a rewritten resume for ATS compliance.

        Args:
            rewritten: The rewritten resume text.

        Returns:
            LLM-generated ATS compliance report with score and issues.
        """
        prompt = f"""\
Check ATS compliance of this resume excerpt:
{rewritten[:300]}

Score 0-100 and list any issues."""
        result = await self.client.chat(
            purpose="ATS compliance checker",
            prompt=prompt,
            output=["ats_score", "issues"],
            rules=["Be specific", "Provide fixes"],
            inputs=[rewritten[:300]],
        )
        return result
