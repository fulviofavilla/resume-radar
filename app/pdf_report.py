"""
PDF report generator for ResumeRadar.

Generates a polished PDF from analysis results using weasyprint.
Design language: editorial/utilitarian — white background, dark ink,
Space Mono for structure, DM Sans for body. Local fonts loaded via
base_url to work correctly inside Docker without network access.

Usage:
    from app.pdf_report import generate_pdf
    pdf_bytes = generate_pdf(results_response)
"""
from __future__ import annotations
import math
import os
from app.models import ResultsResponse

# Absolute path to the static/ directory so weasyprint can resolve fonts
# Works both locally and inside the Docker container (WORKDIR /app)
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
_STATIC_BASE_URL = f"file://{os.path.abspath(_STATIC_DIR)}/"


# ── HTML template ─────────────────────────────────────────────────────────────

def _build_html(data: ResultsResponse) -> str:
    report  = data.report
    profile = data.resume_profile
    gaps    = report.gap_analysis
    score   = round(gaps.match_score * 100)

    # Score arc — larger, more presence
    r       = 38
    circ    = 2 * math.pi * r
    offset  = circ - (score / 100) * circ

    # Color the arc based on score
    if score >= 75:
        arc_color   = "#16a34a"
        score_color = "#16a34a"
    elif score >= 50:
        arc_color   = "#d97706"
        score_color = "#d97706"
    else:
        arc_color   = "#dc2626"
        score_color = "#dc2626"

    arc_svg = f"""
    <svg width="90" height="90" viewBox="0 0 90 90">
      <circle cx="45" cy="45" r="{r}" fill="none" stroke="#ebebeb" stroke-width="5"/>
      <circle cx="45" cy="45" r="{r}" fill="none" stroke="{arc_color}" stroke-width="5"
        stroke-linecap="round"
        stroke-dasharray="{circ:.2f}"
        stroke-dashoffset="{offset:.2f}"
        transform="rotate(-90 45 45)"/>
      <text x="45" y="41" text-anchor="middle" dominant-baseline="middle"
        font-family="Space Mono, monospace" font-size="16" font-weight="700"
        fill="{arc_color}">{score}%</text>
      <text x="45" y="57" text-anchor="middle" dominant-baseline="middle"
        font-family="Space Mono, monospace" font-size="6"
        fill="#888" letter-spacing="1">MATCH</text>
    </svg>"""

    # Strength / missing tags
    strength_tags = "".join(
        f'<span class="tag strength">{s}</span>'
        for s in gaps.strengths[:10]
    )
    missing_tags = "".join(
        f'<span class="tag missing">- {s}</span>'
        for s in gaps.missing_skills[:6]
    ) if gaps.missing_skills else '<span class="tag muted">No critical gaps identified</span>'

    # Recommendations
    recs_html = "".join(
        f'<li>{rec}</li>' for rec in report.recommendations
    )

    # Rewrite suggestions
    rewrites_html = ""
    if report.resume_rewrites:
        items = ""
        for rw in report.resume_rewrites:
            estimated = (
                '<span class="badge">numbers estimated - replace with real data</span>'
                if rw.quantification_is_estimated else ""
            )
            alignment = (
                f'<p class="alignment">{rw.alignment_note}</p>'
                if rw.alignment_note else ""
            )
            items += f"""
            <div class="rewrite-item">
              <div class="rewrite-section-header">{rw.section} {estimated}</div>
              <div class="rewrite-cols">
                <div class="rewrite-col">
                  <div class="col-label">Original</div>
                  <p>{rw.original}</p>
                </div>
                <div class="rewrite-col highlight">
                  <div class="col-label">Suggested rewrite</div>
                  <p>{rw.rewrite}</p>
                </div>
              </div>
              <div class="rewrite-footer">
                <p class="rewrite-reason">{rw.reason}</p>
                {alignment}
              </div>
            </div>"""
        rewrites_html = f"""
        <div class="section">
          <div class="section-title">Resume Rewrites</div>
          {items}
        </div>"""

    # Jobs table rows — pré-computado para evitar f-string aninhada com join
    jobs_rows_html = "".join(f"""
      <tr>
        <td class="job-title">{j.title}</td>
        <td class="job-company">{j.company}</td>
        <td class="job-source">{j.source}</td>
      </tr>""" for j in report.top_jobs)

    # Skills profile
    skills_str   = " · ".join(profile.skills[:12])
    inferred_str = " · ".join(profile.inferred_skills[:8]) if profile.inferred_skills else "-"
    yoe_str      = f"{profile.years_of_experience} yrs experience · " if profile.years_of_experience else ""
    seniority    = profile.seniority.capitalize()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<style>
  @font-face {{
    font-family: 'Space Mono';
    font-weight: 400;
    src: url('fonts/space-mono-v17-latin/space-mono-v17-latin-regular.woff2') format('woff2');
  }}
  @font-face {{
    font-family: 'Space Mono';
    font-weight: 700;
    src: url('fonts/space-mono-v17-latin/space-mono-v17-latin-700.woff2') format('woff2');
  }}
  @font-face {{
    font-family: 'DM Sans';
    font-weight: 300;
    src: url('fonts/dm-sans-v17-latin/dm-sans-v17-latin-300.woff2') format('woff2');
  }}
  @font-face {{
    font-family: 'DM Sans';
    font-weight: 400;
    src: url('fonts/dm-sans-v17-latin/dm-sans-v17-latin-regular.woff2') format('woff2');
  }}
  @font-face {{
    font-family: 'DM Sans';
    font-weight: 500;
    src: url('fonts/dm-sans-v17-latin/dm-sans-v17-latin-500.woff2') format('woff2');
  }}

  :root {{
    --ink:      #0f0f0f;
    --ink2:     #3a3a3a;
    --ink3:     #777;
    --ink4:     #aaa;
    --rule:     #e0e0e0;
    --rule-dark:#c0c0c0;
    --hi:       #e8e8e4;
    --hi2:      #edf7ea;
    --badge-bg: #fde68a;
    --badge-fg: #78350f;
    --mono:     'Space Mono', monospace;
    --sans:     'DM Sans', sans-serif;
    --score-color: {score_color};
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  @page {{
    margin: 28pt 36pt 28pt 36pt;
    size: A4;
  }}

  body {{
    font-family: var(--sans);
    font-size: 9pt;
    color: var(--ink);
    background: #fff;
    line-height: 1.55;
  }}

  /* Header */
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    padding-bottom: 10pt;
    margin-bottom: 0;
    border-bottom: 2.5pt solid var(--ink);
  }}
  .logo-wrap {{
    display: block;
  }}
  .logo {{
    font-family: var(--mono);
    font-size: 14pt;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--ink);
    display: inline;
  }}
  .logo-tag {{
    font-family: var(--mono);
    font-size: 6.5pt;
    color: var(--ink3);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    display: inline;
    margin-left: 8pt;
  }}
  .header-meta {{
    font-family: var(--mono);
    font-size: 6.5pt;
    color: var(--ink3);
    text-align: right;
    line-height: 1.8;
  }}

  /* Score hero */
  .score-hero {{
    display: flex;
    gap: 16pt;
    align-items: center;
    padding: 16pt 0 14pt;
    border-bottom: 1pt solid var(--rule);
    margin-bottom: 18pt;
  }}
  .arc-wrap {{
    flex-shrink: 0;
    width: 90pt;
    height: 90pt;
  }}
  .arc-wrap svg {{ display: block; width: 90pt; height: 90pt; }}
  .score-body {{ flex: 1; }}
  .score-body .section-overline {{
    font-family: var(--mono);
    font-size: 7pt;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--ink3);
    margin-bottom: 4pt;
  }}
  .score-body .summary {{
    font-size: 9pt;
    color: var(--ink2);
    margin-bottom: 10pt;
    line-height: 1.6;
    font-weight: 300;
  }}
  .tags {{
    display: flex;
    flex-wrap: wrap;
    gap: 4pt;
    margin-bottom: 5pt;
  }}
  .tag {{
    font-family: var(--mono);
    font-size: 6pt;
    padding: 2pt 6pt;
    border-radius: 2pt;
  }}
  .tag.strength {{ background: #dcfce7; color: #166534; }}
  .tag.missing  {{ background: #fee2e2; color: #991b1b; }}
  .tag.muted    {{ background: var(--hi); color: var(--ink3); }}

  /* Sections */
  .section {{ margin-bottom: 18pt; }}
  .avoid-break {{ page-break-inside: avoid; }}
  .section-title {{
    font-family: var(--mono);
    font-size: 6.5pt;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--ink3);
    border-bottom: 1pt solid var(--rule);
    padding-bottom: 4pt;
    margin-bottom: 10pt;
  }}

  /* Skills profile */
  .profile-grid {{ display: flex; flex-direction: column; gap: 5pt; }}
  .profile-row {{ display: flex; gap: 10pt; align-items: baseline; }}
  .profile-lbl {{
    font-family: var(--mono);
    font-size: 6pt;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--ink3);
    flex-shrink: 0;
    width: 56pt;
  }}
  .profile-val {{
    font-size: 8.5pt;
    color: var(--ink2);
    font-weight: 300;
    line-height: 1.5;
  }}

  /* Recommendations */
  .rec-list {{ list-style: none; display: flex; flex-direction: column; gap: 7pt; }}
  .rec-list li {{
    display: flex;
    gap: 8pt;
    font-size: 8.5pt;
    color: var(--ink2);
    line-height: 1.55;
    font-weight: 300;
  }}
  .rec-list li::before {{
    content: '->';
    font-family: var(--mono);
    font-size: 8pt;
    flex-shrink: 0;
    color: var(--ink);
    margin-top: 1pt;
  }}

  /* Rewrites */
  .rewrite-item {{
    border: 1pt solid var(--rule);
    border-radius: 3pt;
    margin-bottom: 10pt;
    overflow: hidden;
    page-break-inside: avoid;
  }}
  .rewrite-section-header {{
    background: var(--hi);
    padding: 4pt 8pt;
    font-family: var(--mono);
    font-size: 6pt;
    color: var(--ink2);
    display: flex;
    align-items: center;
    gap: 8pt;
    border-bottom: 1pt solid var(--rule);
    text-transform: uppercase;
    letter-spacing: 0.07em;
  }}
  .badge {{
    background: var(--badge-bg);
    color: var(--badge-fg);
    font-family: var(--mono);
    font-size: 5.5pt;
    padding: 1.5pt 5pt;
    border-radius: 2pt;
  }}
  .rewrite-cols {{ display: flex; }}
  .rewrite-col {{
    flex: 1;
    padding: 8pt 10pt;
    font-size: 8pt;
    color: var(--ink2);
    line-height: 1.6;
    font-weight: 300;
    border-right: 1pt solid var(--rule);
  }}
  .rewrite-col:last-child {{ border-right: none; }}
  .rewrite-col.highlight {{
    background: var(--hi2);
    color: var(--ink);
    font-weight: 400;
  }}
  .col-label {{
    font-family: var(--mono);
    font-size: 5.5pt;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--ink3);
    margin-bottom: 5pt;
  }}
  .rewrite-footer {{
    border-top: 1pt solid var(--rule);
    padding: 5pt 10pt;
    background: #e4e4e0;
  }}
  .rewrite-reason {{
    font-size: 7.5pt;
    color: var(--ink2);
    font-style: italic;
    line-height: 1.5;
  }}
  .alignment {{
    font-family: var(--mono);
    font-size: 6pt;
    color: var(--ink3);
    margin-top: 3pt;
  }}

  /* Jobs table */
  .jobs-table {{ width: 100%; border-collapse: collapse; }}
  .jobs-table th {{
    font-family: var(--mono);
    font-size: 6pt;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--ink3);
    text-align: left;
    padding: 0 0 5pt;
    border-bottom: 1pt solid var(--rule-dark);
  }}
  .jobs-table td {{
    padding: 5pt 0;
    border-bottom: 1pt solid var(--rule);
    vertical-align: middle;
  }}
  .jobs-table tr:last-child td {{ border-bottom: none; }}
  .job-title   {{ font-size: 8.5pt; font-weight: 500; color: var(--ink); width: 42%; }}
  .job-company {{ font-size: 8pt; color: var(--ink2); font-weight: 300; width: 40%; }}
  .job-source  {{
    font-family: var(--mono);
    font-size: 6pt;
    color: var(--ink3);
    text-align: right;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    width: 18%;
  }}

  /* Footer */
  .footer {{
    margin-top: 18pt;
    padding-top: 7pt;
    border-top: 1pt solid var(--rule);
    font-family: var(--mono);
    font-size: 6pt;
    color: var(--ink4);
    display: flex;
    justify-content: space-between;
  }}
</style>
</head>
<body>

<div class="header">
  <div class="logo-wrap">
    <span class="logo">ResumeRadar</span>
    <span class="logo-tag">Analysis Report</span>
  </div>
  <div class="header-meta">
    {yoe_str}{seniority}<br/>
    {report.jobs_analyzed} jobs analyzed
  </div>
</div>

<div class="score-hero">
  <div class="arc-wrap">
    {arc_svg}
  </div>
  <div class="score-body">
    <div class="section-overline">Semantic Match Score</div>
    <p class="summary">{profile.summary}</p>
    <div class="tags">{strength_tags}</div>
    <div class="tags">{missing_tags}</div>
  </div>
</div>

<div class="section avoid-break">
  <div class="section-title">Skills Profile</div>
  <div class="profile-grid">
    <div class="profile-row">
      <span class="profile-lbl">Explicit</span>
      <span class="profile-val">{skills_str}</span>
    </div>
    <div class="profile-row">
      <span class="profile-lbl">Inferred</span>
      <span class="profile-val">{inferred_str}</span>
    </div>
  </div>
</div>

<div class="section avoid-break">
  <div class="section-title">Recommendations</div>
  <ul class="rec-list">{recs_html}</ul>
</div>

{rewrites_html}

<div class="section">
  <div class="section-title">Jobs Analyzed</div>
  <table class="jobs-table">
    <thead>
      <tr>
        <th>Role</th>
        <th>Company</th>
        <th style="text-align:right">Source</th>
      </tr>
    </thead>
    <tbody>
      {jobs_rows_html}
    </tbody>
  </table>
</div>

<div class="footer">
  <span>Generated by ResumeRadar</span>
  <span>github.com/fulviofavilla/resume-radar</span>
</div>

</body>
</html>"""


# ── Public API ────────────────────────────────────────────────────────────────

def generate_pdf(data: ResultsResponse) -> bytes:
    """
    Render the analysis results as a PDF and return raw bytes.

    base_url is set to the static/ directory so weasyprint can resolve
    local font files via @font-face without network access.

    Raises ImportError if weasyprint is not installed.
    Raises ValueError if the results are not completed.
    """
    if data.status != "completed" or not data.report or not data.resume_profile:
        raise ValueError("Cannot generate PDF: results not completed")

    try:
        from weasyprint import HTML
    except ImportError as e:
        raise ImportError(
            "weasyprint is required for PDF generation. "
            "Add it to requirements.txt and rebuild the container."
        ) from e

    html = _build_html(data)
    return HTML(string=html, base_url=_STATIC_BASE_URL).write_pdf()