"""
PDF report generator for ResumeRadar.

Generates a single-page PDF from analysis results using weasyprint.
The template reuses the same design language as the frontend (dark theme,
Space Mono, accent yellow) but adapted for print — white background with
dark ink, suitable for both screen viewing and printing.

Usage:
    from app.pdf_report import generate_pdf
    pdf_bytes = generate_pdf(results_response)
"""
from __future__ import annotations
import math
from app.models import ResultsResponse


# ── HTML template ─────────────────────────────────────────────────────────────

def _build_html(data: ResultsResponse) -> str:
    report  = data.report
    profile = data.resume_profile
    gaps    = report.gap_analysis
    score   = round(gaps.match_score * 100)

    # SVG score arc
    r        = 28
    circ     = 2 * math.pi * r
    offset   = circ - (score / 100) * circ
    arc_svg  = f"""
    <svg width="68" height="68" viewBox="0 0 68 68">
      <circle cx="34" cy="34" r="{r}" fill="none" stroke="#e8e8e8" stroke-width="4"/>
      <circle cx="34" cy="34" r="{r}" fill="none" stroke="#1a1a1a" stroke-width="4"
        stroke-linecap="round"
        stroke-dasharray="{circ:.2f}"
        stroke-dashoffset="{offset:.2f}"
        transform="rotate(-90 34 34)"/>
    </svg>
    <div class="arc-label">{score}%</div>"""

    # Strength tags
    strength_tags = "".join(
        f'<span class="tag strength">{s}</span>'
        for s in gaps.strengths[:10]
    )
    missing_tags = "".join(
        f'<span class="tag missing">− {s}</span>'
        for s in gaps.missing_skills[:6]
    ) if gaps.missing_skills else '<span class="tag muted">No critical gaps identified</span>'

    # Recommendations
    recs_html = "".join(
        f'<li>{r}</li>' for r in report.recommendations
    )

    # Rewrite suggestions
    rewrites_html = ""
    if report.resume_rewrites:
        items = ""
        for rw in report.resume_rewrites:
            estimated = (
                '<span class="badge">numbers estimated — replace with real data</span>'
                if rw.quantification_is_estimated else ""
            )
            alignment = (
                f'<p class="alignment">{rw.alignment_note}</p>'
                if rw.alignment_note else ""
            )
            items += f"""
            <div class="rewrite-item">
              <div class="rewrite-section">{rw.section} {estimated}</div>
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
              <p class="rewrite-reason">{rw.reason}</p>
              {alignment}
            </div>"""
        rewrites_html = f"""
        <div class="section">
          <div class="section-title">Resume Rewrites</div>
          {items}
        </div>"""

    # Top jobs
    jobs_html = "".join(f"""
        <div class="job-row">
          <span class="job-title">{j.title}</span>
          <span class="job-company">{j.company}</span>
          <span class="job-source">{j.source}</span>
        </div>""" for j in report.top_jobs)

    # Skills profile
    skills_str   = " · ".join(profile.skills[:12])
    inferred_str = " · ".join(profile.inferred_skills[:8])
    yoe = f"{profile.years_of_experience} yrs · " if profile.years_of_experience else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500&display=swap');

  :root {{
    --ink:     #0f0f0f;
    --ink2:    #444;
    --ink3:    #888;
    --rule:    #ddd;
    --accent:  #1a1a1a;
    --hi:      #f5f5f0;
    --badge-bg:#fff3cd;
    --badge-fg:#7a5c00;
    --mono:    'Space Mono', monospace;
    --sans:    'DM Sans', sans-serif;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: var(--sans);
    font-size: 9.5pt;
    color: var(--ink);
    background: #fff;
    padding: 32pt 36pt;
    line-height: 1.5;
  }}

  /* Header */
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    border-bottom: 2px solid var(--ink);
    padding-bottom: 10pt;
    margin-bottom: 20pt;
  }}
  .logo {{ font-family: var(--mono); font-size: 13pt; font-weight: 700; }}
  .meta {{ font-family: var(--mono); font-size: 7pt; color: var(--ink3); text-align: right; line-height: 1.8; }}

  /* Score row */
  .score-row {{
    display: flex;
    gap: 20pt;
    align-items: flex-start;
    margin-bottom: 18pt;
  }}
  .arc-wrap {{
    position: relative;
    flex-shrink: 0;
    width: 68pt;
    height: 68pt;
  }}
  .arc-wrap svg {{ display: block; }}
  .arc-label {{
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--mono);
    font-size: 11pt;
    font-weight: 700;
  }}
  .score-body {{ flex: 1; }}
  .score-body h2 {{
    font-family: var(--mono);
    font-size: 7.5pt;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: var(--ink3);
    margin-bottom: 5pt;
  }}
  .score-body p {{ font-size: 9pt; color: var(--ink2); margin-bottom: 8pt; }}

  /* Tags */
  .tags {{ display: flex; flex-wrap: wrap; gap: 4pt; }}
  .tag {{
    font-family: var(--mono);
    font-size: 6.5pt;
    padding: 2pt 6pt;
    border-radius: 2pt;
    background: var(--hi);
    color: var(--ink2);
  }}
  .tag.strength {{ background: #e8f5e9; color: #2e7d32; }}
  .tag.missing  {{ background: #fce4ec; color: #c62828; }}
  .tag.muted    {{ background: var(--hi); color: var(--ink3); }}

  /* Sections */
  .section {{ margin-bottom: 18pt; }}
  .section-title {{
    font-family: var(--mono);
    font-size: 7pt;
    letter-spacing: .1em;
    text-transform: uppercase;
    color: var(--ink3);
    border-bottom: 1px solid var(--rule);
    padding-bottom: 4pt;
    margin-bottom: 10pt;
  }}

  /* Profile */
  .profile-row {{ margin-bottom: 5pt; }}
  .profile-row .lbl {{
    font-family: var(--mono);
    font-size: 6.5pt;
    text-transform: uppercase;
    letter-spacing: .06em;
    color: var(--ink3);
    display: inline-block;
    width: 70pt;
  }}
  .profile-row span {{ font-size: 8.5pt; color: var(--ink2); }}

  /* Recommendations */
  .rec-list {{ list-style: none; display: flex; flex-direction: column; gap: 6pt; }}
  .rec-list li {{
    display: flex;
    gap: 8pt;
    font-size: 8.5pt;
    color: var(--ink2);
    line-height: 1.5;
  }}
  .rec-list li::before {{
    content: '→';
    font-family: var(--mono);
    flex-shrink: 0;
    color: var(--ink);
  }}

  /* Rewrites */
  .rewrite-item {{
    border: 1pt solid var(--rule);
    border-radius: 3pt;
    margin-bottom: 10pt;
    overflow: hidden;
  }}
  .rewrite-section {{
    background: var(--hi);
    padding: 4pt 8pt;
    font-family: var(--mono);
    font-size: 6.5pt;
    color: var(--ink3);
    display: flex;
    align-items: center;
    gap: 8pt;
  }}
  .badge {{
    background: var(--badge-bg);
    color: var(--badge-fg);
    font-family: var(--mono);
    font-size: 6pt;
    padding: 1pt 5pt;
    border-radius: 2pt;
  }}
  .rewrite-cols {{
    display: flex;
    gap: 0;
  }}
  .rewrite-col {{
    flex: 1;
    padding: 8pt;
    font-size: 8pt;
    color: var(--ink2);
    line-height: 1.55;
    border-right: 1pt solid var(--rule);
  }}
  .rewrite-col:last-child {{ border-right: none; }}
  .rewrite-col.highlight {{ background: #fafff5; color: var(--ink); }}
  .col-label {{
    font-family: var(--mono);
    font-size: 6pt;
    text-transform: uppercase;
    letter-spacing: .07em;
    color: var(--ink3);
    margin-bottom: 4pt;
  }}
  .rewrite-reason {{
    padding: 5pt 8pt;
    font-size: 7.5pt;
    color: var(--ink3);
    border-top: 1pt solid var(--rule);
    font-style: italic;
  }}
  .alignment {{
    padding: 3pt 8pt 5pt;
    font-family: var(--mono);
    font-size: 6.5pt;
    color: var(--ink3);
  }}

  /* Jobs */
  .job-row {{
    display: flex;
    gap: 10pt;
    padding: 5pt 0;
    border-bottom: 1pt solid var(--rule);
    font-size: 8.5pt;
    align-items: baseline;
  }}
  .job-row:last-child {{ border-bottom: none; }}
  .job-title   {{ flex: 2; font-weight: 500; color: var(--ink); }}
  .job-company {{ flex: 1.5; color: var(--ink2); }}
  .job-source  {{ font-family: var(--mono); font-size: 6.5pt; color: var(--ink3); }}

  /* Footer */
  .footer {{
    margin-top: 20pt;
    border-top: 1pt solid var(--rule);
    padding-top: 8pt;
    font-family: var(--mono);
    font-size: 6.5pt;
    color: var(--ink3);
    display: flex;
    justify-content: space-between;
  }}
</style>
</head>
<body>

<div class="header">
  <div class="logo">📡 ResumeRadar</div>
  <div class="meta">
    {yoe}{profile.seniority.capitalize()}<br/>
    {report.jobs_analyzed} jobs analyzed
  </div>
</div>

<!-- Score + profile summary -->
<div class="score-row">
  <div class="arc-wrap">{arc_svg}</div>
  <div class="score-body">
    <h2>Semantic match score</h2>
    <p>{profile.summary}</p>
    <div class="tags">{strength_tags}</div>
    <div class="tags" style="margin-top:5pt">{missing_tags}</div>
  </div>
</div>

<!-- Skills profile -->
<div class="section">
  <div class="section-title">Skills Profile</div>
  <div class="profile-row"><span class="lbl">Explicit</span><span>{skills_str}</span></div>
  <div class="profile-row"><span class="lbl">Inferred</span><span>{inferred_str}</span></div>
</div>

<!-- Recommendations -->
<div class="section">
  <div class="section-title">Recommendations</div>
  <ul class="rec-list">{recs_html}</ul>
</div>

{rewrites_html}

<!-- Top jobs -->
<div class="section">
  <div class="section-title">Jobs Analyzed</div>
  {jobs_html}
</div>

<div class="footer">
  <span>Generated by ResumeRadar</span>
  <span>resume-radar · github.com/fulviofavilla/resume-radar</span>
</div>

</body>
</html>"""


# ── Public API ────────────────────────────────────────────────────────────────

def generate_pdf(data: ResultsResponse) -> bytes:
    """
    Render the analysis results as a PDF and return raw bytes.
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
    return HTML(string=html).write_pdf()