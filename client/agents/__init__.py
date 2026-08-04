"""Dedicated agent classes for the resume optimization pipeline.

All 7 pipeline agents are exported here so callers can wire up the full
chain with a single import::

    from client.agents import (
        JDParsingAgent,
        ResumeParsingAgent,
        GapAnalysisAgent,
        ResumeRewriteAgent,
        ATSComplianceAgent,
        TonePolishingAgent,
        CoverLetterAgent,
    )
"""

from client.agents.ats_compliance import ATSComplianceAgent
from client.agents.cover_letter import CoverLetterAgent
from client.agents.gap_analysis import GapAnalysisAgent
from client.agents.jd_parsing import JDParsingAgent
from client.agents.resume_parsing import ResumeParsingAgent
from client.agents.resume_rewrite import ResumeRewriteAgent
from client.agents.tone_polishing import TonePolishingAgent

__all__ = [
    "ATSComplianceAgent",
    "CoverLetterAgent",
    "GapAnalysisAgent",
    "JDParsingAgent",
    "ResumeParsingAgent",
    "ResumeRewriteAgent",
    "TonePolishingAgent",
]
