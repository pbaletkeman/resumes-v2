"""
cover_letter.py
Cover letter template — professional format for all output styles.
"""

COVER_LETTER = {
    "plaintext": """\
{{ candidate_name }}

{{ date }}

Dear {{ hiring_manager | default('Hiring Manager') }},

{{ opening_paragraph }}

{{ body_paragraph }}

{{ closing_paragraph }}

Sincerely,
{{ candidate_name }}""",

    "markdown": """\
# {{ candidate_name }}

*{{ date }}*

Dear {{ hiring_manager | default('Hiring Manager') }},

{{ opening_paragraph }}

{{ body_paragraph }}

{{ closing_paragraph }}

Sincerely,

**{{ candidate_name }}**""",
}
