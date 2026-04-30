export default function JobList({ jobs, jobsAnalyzed }) {
  return (
    <div className="fade-in">
      <div style={{ height: 1, background: 'var(--border)', margin: '32px 0' }} />
      <div style={{
        fontFamily: 'var(--mono)',
        fontSize: '0.7rem',
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        color: 'var(--muted)',
        marginBottom: 16,
      }}>
        Jobs analyzed ({jobsAnalyzed})
      </div>
      <div style={{
        background: 'var(--surface)',
        border: '1.5px solid var(--border)',
        borderRadius: 4,
        padding: '0 28px',
      }}>
        {jobs.map((j, i) => (
          <div key={i} style={{
            padding: '14px 0',
            borderBottom: i < jobs.length - 1 ? '1px solid var(--border)' : 'none',
          }}>
            <div style={{ fontFamily: 'var(--mono)', fontSize: '0.85rem', color: 'var(--text)', marginBottom: 3 }}>
              {j.title}
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
              {j.company} · {j.source}
              <a
                href={j.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  color: 'var(--accent)',
                  textDecoration: 'none',
                  marginLeft: 8,
                  fontFamily: 'var(--mono)',
                  fontSize: '0.72rem',
                }}
                onMouseEnter={e => e.currentTarget.style.textDecoration = 'underline'}
                onMouseLeave={e => e.currentTarget.style.textDecoration = 'none'}
              >
                view ↗
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
