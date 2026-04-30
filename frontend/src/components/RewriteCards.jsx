export default function RewriteCards({ rewrites }) {
  if (!rewrites || rewrites.length === 0) return null

  return (
    <div className="fade-in">
      <div style={{
        fontFamily: 'var(--mono)',
        fontSize: '0.7rem',
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        color: 'var(--muted)',
        marginBottom: 16,
        marginTop: 32,
      }}>
        Resume rewrites
      </div>
      {rewrites.map((rw, i) => (
        <RewriteItem key={i} rw={rw} />
      ))}
    </div>
  )
}

function RewriteItem({ rw }) {
  return (
    <div style={{
      border: '1.5px solid var(--border)',
      borderRadius: 4,
      overflow: 'hidden',
      marginBottom: 16,
    }}>
      <div style={{
        background: 'var(--surface)',
        padding: '10px 16px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: '0.7rem', color: 'var(--muted)', letterSpacing: '0.04em' }}>
          {rw.section}
        </span>
        {rw.quantification_is_estimated && (
          <span style={{
            fontFamily: 'var(--mono)',
            fontSize: '0.62rem',
            padding: '2px 7px',
            borderRadius: 2,
            background: 'rgba(107, 143, 168, 0.15)',
            color: 'var(--estimated)',
            letterSpacing: '0.04em',
          }}>
            numbers estimated
          </span>
        )}
      </div>
      <div style={{
        padding: 16,
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
        gap: '0 20px',
      }}>
        <div style={{ paddingBottom: 12 }}>
          <label style={{
            display: 'block',
            fontFamily: 'var(--mono)',
            fontSize: '0.65rem',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--muted)',
            marginBottom: 5,
          }}>
            Original
          </label>
          <p style={{ fontSize: '0.85rem', lineHeight: 1.6, color: 'var(--text)' }}>{rw.original}</p>
        </div>
        <div style={{ paddingBottom: 12 }}>
          <label style={{
            display: 'block',
            fontFamily: 'var(--mono)',
            fontSize: '0.65rem',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--muted)',
            marginBottom: 5,
          }}>
            Suggested rewrite
          </label>
          <p style={{ fontSize: '0.85rem', lineHeight: 1.6, color: 'var(--accent)' }}>{rw.rewrite}</p>
        </div>
        <div style={{
          gridColumn: '1 / -1',
          fontSize: '0.78rem',
          color: 'var(--muted)',
          paddingTop: 12,
          borderTop: '1px solid var(--border)',
          lineHeight: 1.5,
        }}>
          {rw.reason}
          {rw.alignment_note && (
            <div style={{ fontSize: '0.75rem', color: 'var(--muted)', fontFamily: 'var(--mono)', marginTop: 4 }}>
              {rw.alignment_note}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
