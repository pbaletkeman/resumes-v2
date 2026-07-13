"""
resume_processor.py
Orchestrates resume optimization: parses formats, extracts data, runs agents.
"""

import asyncio
from client.model_client import ModelClient
from client.format_detector import FormatDetector


class ResumeProcessor:
    """Processes job descriptions and resumes for optimization."""

    def __init__(self, client: ModelClient):
        self.client = client

    async def optimize_resume(self, job_description: str, resume: str) -> dict:
        """
        Optimize resume for job description.

        Args:
            job_description: Raw job description (any format)
            resume: Raw resume (any format)

        Returns:
            dict with optimized resume and analysis
        """
        # Step 1: Parse both documents (fast, no LLM)
        jd_parsed = FormatDetector.parse_job_description(job_description)
        resume_parsed = FormatDetector.parse_resume(resume)

        # Step 2: Extract gap analysis (fast LLM call, focused)
        gap_analysis = await self._gap_analysis(jd_parsed, resume_parsed)

        # Step 3: Rewrite resume (fast LLM call, focused)
        rewritten = await self._rewrite_resume(resume_parsed, gap_analysis)

        # Step 4: ATS compliance check (fast LLM call)
        ats_check = await self._ats_compliance(rewritten)

        return {
            "parsed_jd": jd_parsed,
            "parsed_resume": resume_parsed,
            "gap_analysis": gap_analysis,
            "rewritten_resume": rewritten,
            "ats_compliance": ats_check,
        }

    async def _gap_analysis(self, jd: dict, resume: dict) -> str:
        """Analyze gaps between JD and resume."""
        prompt = f"""
Compare this resume with the job description.
List:
1. Missing skills
2. Weak areas
3. Keyword gaps
4. Recommendation

Resume skills: {', '.join(resume['skills'][:10])}
JD requirements: {', '.join(jd['requirements'][:10])}
"""
        result = await self.client.chat(
            purpose="Gap analysis specialist",
            prompt=prompt,
            output=["missing_skills", "weak_areas", "keywords", "recommendation"],
            rules=["Be concise", "Focus on job match"],
            inputs=[resume.get("raw", "")[:500], jd.get("raw", "")[:500]]
        )
        return result

    async def _rewrite_resume(self, resume: dict, gap_analysis: str) -> str:
        """Rewrite resume to match job."""
        prompt = f"""
Rewrite these resume bullet points to match the job better.
Address these gaps: {gap_analysis[:200]}

Current bullets:
{chr(10).join(resume['experience'][:5])}

Produce rewritten bullets only.
"""
        result = await self.client.chat(
            purpose="Resume rewriter",
            prompt=prompt,
            output=["rewritten_bullets"],
            rules=["Use strong action verbs", "Include metrics", "Match keywords"],
            inputs=[gap_analysis[:300]]
        )
        return result

    async def _ats_compliance(self, rewritten: str) -> str:
        """Check ATS compliance."""
        prompt = f"""
Check ATS compliance of this resume excerpt:
{rewritten[:300]}

Score 0-100 and list any issues.
"""
        result = await self.client.chat(
            purpose="ATS compliance checker",
            prompt=prompt,
            output=["ats_score", "issues"],
            rules=["Be specific", "Provide fixes"],
            inputs=[rewritten[:300]]
        )
        return result
