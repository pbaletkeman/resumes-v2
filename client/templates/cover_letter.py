"""
cover_letter.py
Cover letter template — professional format for all output styles.

The ``COVER_LETTER`` dict contains the Jinja2 template strings for the
cover letter: one ``"plaintext"`` source and one ``"markdown"`` source.
These drive ``ResumeRenderer.render_cover_letter_plaintext`` /
``render_cover_letter_markdown``.  Unlike the resume styles this is a
single shared template (no per-style variants).
"""

# COVER_LETTER: cover letter templates.
# {"plaintext", "markdown"} Jinja2 sources consumed by
# ResumeRenderer's render_cover_letter_plaintext / render_cover_letter_markdown.
# The template expects candidate_name, date, opening/body/closing paragraphs,
# and optional contact_line (see ResumeRenderer._build_cover_letter_context).
COVER_LETTER = {
    "plaintext": """\
{{ candidate_name }}
{% if contact_line %}{{ contact_line }}
{% endif %}{{ date }}

Dear {{ hiring_manager | default('Hiring Manager') }},

{{ opening_paragraph }}

{{ body_paragraph }}

{{ closing_paragraph }}

Sincerely,
{{ candidate_name }}""",
    "markdown": """\
# {{ candidate_name }}
{% if contact_line %}*{{ contact_line }}*

{% endif %}*{{ date }}*

Dear {{ hiring_manager | default('Hiring Manager') }},

{{ opening_paragraph }}

{{ body_paragraph }}

{{ closing_paragraph }}

Sincerely,

**{{ candidate_name }}**""",
}
