import { useEffect, useRef } from 'react'

function getScoreColor(score) {
  if (score >= 85) return 'var(--score-great)'
  if (score >= 70) return 'var(--score-good)'
  if (score >= 50) return 'var(--score-fair)'
  return 'var(--score-weak)'
}

export default function ScoreCard({ report, profile }) {
  const arcRef = useRef(null)
  const gaps = report.gap_analysis
  const scoreInt = Math.round(gaps.match_score * 100)
  const scoreColor = getScoreColor(scoreInt)
  const circ = 2 * Math.PI * 30
  const offset = circ - (scoreInt / 100) * circ

  useEffect(() => {
    if (arcRef.current) {
      // Start at full offset (empty), animate to final offset
      arcRef.current.style.strokeDashoffset = circ
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (arcRef.current) arcRef.current.style.strokeDashoffset = offset
        })
      })
    }
  }, [circ, offset])

  return (
    <div className="fade-in">
      <div style={{
        fontFamily: 'var(--mono)',
        fontSize: '0.7rem',
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        color: 'var(--muted)',
        marginBottom: 16,
      }}>
        Match analysis
      </div>
      <div style={{
        background: 'var(--surface)',
        border: '1.5px solid var(--border)',
        borderRadius: 4,
        padding: '28px 28px 24px',
        marginBottom: 32,
        display: 'flex',
        alignItems: 'center',
        gap: 28,
      }}>
        {/* Arc */}
        <div style={{ position: 'relative', flexShrink: 0 }}>
          <svg width="72" height="72" viewBox="0 0 72 72" style={{ transform: 'rotate(-90deg)' }}>
            <circle cx="36" cy="36" r="30" fill="none" stroke="var(--border)" strokeWidth="4" />
            <circle
              ref={arcRef}
              cx="36" cy="36" r="30"
              fill="none"
              stroke={scoreColor}
              strokeWidth="4"
              strokeLinecap="round"
              strokeDasharray={circ}
              strokeDashoffset={circ}
              style={{ transition: 'stroke-dashoffset 1s ease' }}
            />
          </svg>
          <div style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: 'var(--mono)',
            fontSize: '1.1rem',
            fontWeight: 700,
            color: scoreColor,
          }}>
            {scoreInt}%
          </div>
        </div>

        {/* Meta */}
        <div style={{ flex: 1 }}>
          <div style={{
            fontFamily: 'var(--mono)',
            fontSize: '0.75rem',
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            color: 'var(--muted)',
            marginBottom: 6,
          }}>
            Semantic match score
          </div>
          <div style={{ fontSize: '0.88rem', color: 'var(--text)', lineHeight: 1.55 }}>
            {profile.summary}
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 12 }}>
            {gaps.strengths.slice(0, 8).map(s => (
              <span key={s} style={{
                fontFamily: 'var(--mono)', fontSize: '0.7rem', padding: '3px 9px',
                borderRadius: 2, background: 'var(--accent-dim)', color: 'var(--accent)',
              }}>{s}</span>
            ))}
            {gaps.missing_skills.slice(0, 5).map(s => (
              <span key={s} style={{
                fontFamily: 'var(--mono)', fontSize: '0.7rem', padding: '3px 9px',
                borderRadius: 2, background: 'rgba(255,79,79,0.1)', color: 'var(--danger)',
              }}>− {s}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
