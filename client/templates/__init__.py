"""
templates/
Resume and cover letter templates for multi-format output.
"""

from client.templates.classic import CLASSIC_RESUME
from client.templates.cover_letter import COVER_LETTER as COVER_LETTER
from client.templates.minimal import MINIMAL_RESUME
from client.templates.modern import MODERN_RESUME

TEMPLATES = {
    "modern": MODERN_RESUME,
    "classic": CLASSIC_RESUME,
    "minimal": MINIMAL_RESUME,
}
