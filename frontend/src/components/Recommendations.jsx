export default function Recommendations({ recommendations }) {
  return (
    <div className="fade-in" style={{
      background: 'var(--surface)',
      border: '1.5px solid var(--border)',
      borderRadius: 4,
      padding: '24px 28px',
      marginBottom: 24,
    }}>
      <div style={{
        fontFamily: 'var(--mono)',
        fontSize: '0.72rem',
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        color: 'var(--muted)',
        marginBottom: 16,
      }}>
        Recommendations
      </div>
      <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {recommendations.map((r, i) => (
          <li key={i} style={{ display: 'flex', gap: 12, fontSize: '0.88rem', lineHeight: 1.55, color: 'var(--text)' }}>
            <span style={{ color: 'var(--accent)', fontFamily: 'var(--mono)', flexShrink: 0, marginTop: 1 }}>→</span>
            {r}
          </li>
        ))}
      </ul>
    </div>
  )
}
