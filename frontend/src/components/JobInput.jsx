export default function JobInput({ value, onChange }) {
  return (
    <div style={{ marginTop: 16 }}>
      <label style={{
        display: 'block',
        fontFamily: 'var(--mono)',
        fontSize: '0.72rem',
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        color: 'var(--muted)',
        marginBottom: 8,
      }}>
        Job description
      </label>
      <textarea
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder="Paste the full job description here..."
        rows={8}
        style={{
          width: '100%',
          background: 'var(--surface)',
          border: '1.5px solid var(--border)',
          borderRadius: 3,
          padding: '11px 14px',
          color: 'var(--text)',
          fontFamily: 'var(--sans)',
          fontSize: '0.88rem',
          lineHeight: 1.6,
          outline: 'none',
          resize: 'vertical',
          transition: 'border-color 0.2s',
        }}
        onFocus={e => e.target.style.borderColor = 'var(--accent)'}
        onBlur={e => e.target.style.borderColor = 'var(--border)'}
      />
    </div>
  )
}