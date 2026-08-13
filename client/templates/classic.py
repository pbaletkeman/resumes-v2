"""
classic.py
Classic resume template — traditional format with underlined section headers.

The ``CLASSIC_RESUME`` dict contains the Jinja2 template strings for the
classic style: one ``"plaintext"`` source and one ``"markdown"`` source.
These drive ``ResumeRenderer.render_plaintext`` /
``render_markdown`` (via the ``"classic"`` key in ``client.templates``)
and, through the shared context, the DOCX/PDF writers in
``client/templates/renderer.py``.
"""

# CLASSIC_RESUME: classic-style resume templates.
# {"plaintext", "markdown"} Jinja2 sources consumed by ResumeRenderer's
# render_plaintext / render_markdown (template key "classic") and the
# DOCX/PDF writers that share the same context.
CLASSIC_RESUME = {
    "plaintext": """\
{{ name }}
{% if title %}{{ title }}{% endif %}

--------------------------------------------------------------------------------

Professional Summary
{{ summary }}

--------------------------------------------------------------------------------

Core Competencies
{% for skill in skills %}  * {{ skill }}
{% endfor %}

--------------------------------------------------------------------------------

Professional Experience
{% for job in experience %}
{{ job.title }}
{{ job.company }} | {{ job.dates }}

Responsibilities:
{% for r in job.responsibilities %}  * {{ r }}
{% endfor %}
{% if job.achievements %}
Achievements:
{% for a in job.achievements %}  * {{ a }}
{% endfor %}{% endif %}
{% if job.metrics %}
Metrics:
{% for m in job.metrics %}  * {{ m }}
{% endfor %}{% endif %}{% endfor %}

--------------------------------------------------------------------------------
{% if certifications %}
Certifications
{% for cert in certifications %}  * {{ cert }}
{% endfor %}

--------------------------------------------------------------------------------
{% endif %}
{% if projects %}
Projects
{% for project in projects %}  * {{ project }}
{% endfor %}

--------------------------------------------------------------------------------
{% endif %}
Education
{% for edu in education %}  * {{ edu }}
{% endfor %}""",
    "markdown": """\
# {{ name }}

{% if title %}**{{ title }}**{% endif %}

---

## Professional Summary

{{ summary }}

---

## Core Competencies

{% for skill in skills %}* {{ skill }}
{% endfor %}

---

## Professional Experience

{% for job in experience %}
### {{ job.title }}

**{{ job.company }}** | {{ job.dates }}

**Responsibilities:**
{% for r in job.responsibilities %}* {{ r }}
{% endfor %}
{% if job.achievements %}
**Achievements:**
{% for a in job.achievements %}* {{ a }}
{% endfor %}{% endif %}
{% if job.metrics %}
**Metrics:**
{% for m in job.metrics %}* {{ m }}
{% endfor %}{% endif %}
{% endfor %}

---
{% if certifications %}
## Certifications

{% for cert in certifications %}* {{ cert }}
{% endfor %}

---
{% endif %}
{% if projects %}
## Projects

{% for project in projects %}* {{ project }}
{% endfor %}

---
{% endif %}
## Education

{% for edu in education %}* {{ edu }}
{% endfor %}""",
}
