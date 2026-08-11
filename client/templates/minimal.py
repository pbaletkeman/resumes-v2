"""
minimal.py
Minimal resume template — clean, whitespace-focused, no decorative elements.

The ``MINIMAL_RESUME`` dict contains the Jinja2 template strings for the
minimal style: one ``"plaintext"`` source and one ``"markdown"`` source.
These drive ``ResumeRenderer.render_plaintext`` /
``render_markdown`` (via the ``"minimal"`` key in ``client.templates``)
and, through the shared context, the DOCX/PDF writers in
``client/templates/renderer.py``.
"""

# MINIMAL_RESUME: minimal-style resume templates.
# {"plaintext", "markdown"} Jinja2 sources consumed by ResumeRenderer's
# render_plaintext / render_markdown (template key "minimal") and the
# DOCX/PDF writers that share the same context.
MINIMAL_RESUME = {
    "plaintext": """\
{{ name }}
{{ title }}

{{ summary }}

Skills: {{ skills | join(', ') }}

{% for job in experience %}
{{ job.title }}, {{ job.company }} ({{ job.dates }})
{% for r in job.responsibilities %}{{ r }}
{% endfor %}{% for a in job.achievements %}{{ a }}
{% endfor %}{% for m in job.metrics %}{{ m }}
{% endfor %}{% endfor %}

{% if certifications %}
Certifications: {{ certifications | join(', ') }}
{% endif %}

{% if projects %}
Projects:
{% for project in projects %}{{ project }}
{% endfor %}{% endif %}

Education:
{% for edu in education %}{{ edu }}
{% endfor %}""",
    "markdown": """\
# {{ name }}

{{ title }}

{{ summary }}

**Skills:** {{ skills | join(', ') }}

{% for job in experience %}
## {{ job.title }}, {{ job.company }}

*{{ job.dates }}*

{% for r in job.responsibilities %}- {{ r }}
{% endfor %}{% for a in job.achievements %}- {{ a }}
{% endfor %}{% for m in job.metrics %}- {{ m }}
{% endfor %}{% endfor %}

{% if certifications %}
## Certifications

{{ certifications | join(', ') }}
{% endif %}

{% if projects %}
## Projects

{% for project in projects %}- {{ project }}
{% endfor %}
{% endif %}

## Education

{% for edu in education %}- {{ edu }}
{% endfor %}""",
}
