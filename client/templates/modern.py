"""
modern.py
Modern resume template — clean lines, bold section headers, compact layout.

The ``MODERN_RESUME`` dict contains the Jinja2 template strings for the
modern style: one ``"plaintext"`` source and one ``"markdown"`` source.
These drive ``ResumeRenderer.render_plaintext`` /
``render_markdown`` (via the ``"modern"`` key in ``client.templates``)
and, through the shared context, the DOCX/PDF writers in
``client/templates/renderer.py``.
"""

# MODERN_RESUME: modern-style resume templates.
# {"plaintext", "markdown"} Jinja2 sources consumed by ResumeRenderer's
# render_plaintext / render_markdown (template key "modern") and the
# DOCX/PDF writers that share the same context.
MODERN_RESUME = {
    "plaintext": """\
{{ name }}

{% if title %}{{ title }}{% endif %}

SUMMARY
{{ summary }}

SKILLS
{% for skill in skills %}- {{ skill }}
{% endfor %}

EXPERIENCE
{% for job in experience %}
{{ job.title }} at {{ job.company }} ({{ job.dates }})
{% for r in job.responsibilities %}- {{ r }}
{% endfor %}{% for a in job.achievements %}- {{ a }}
{% endfor %}{% for m in job.metrics %}- {{ m }}
{% endfor %}{% endfor %}

{% if certifications %}
CERTIFICATIONS
{% for cert in certifications %}- {{ cert }}
{% endfor %}
{% endif %}

{% if projects %}
PROJECTS
{% for project in projects %}- {{ project }}
{% endfor %}
{% endif %}

EDUCATION
{% for edu in education %}- {{ edu }}
{% endfor %}""",
    "markdown": """\
# {{ name }}

{% if title %}**{{ title }}**{% endif %}

## Summary

{{ summary }}

## Skills

{% for skill in skills %}- {{ skill }}
{% endfor %}

## Experience

{% for job in experience %}
### **{{ job.title }}** at **{{ job.company }}** ({{ job.dates }})

{% for r in job.responsibilities %}- {{ r }}
{% endfor %}{% for a in job.achievements %}- {{ a }}
{% endfor %}{% for m in job.metrics %}- {{ m }}
{% endfor %}{% endfor %}

{% if certifications %}
## Certifications

{% for cert in certifications %}- {{ cert }}
{% endfor %}
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
