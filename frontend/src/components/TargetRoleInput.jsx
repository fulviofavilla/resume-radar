export default function TargetRoleInput({ value, onChange }) {
  return (
    <div style={{ marginTop: 20 }}>
      <label style={{
        display: 'block',
        fontFamily: 'var(--mono)',
        fontSize: '0.72rem',
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        color: 'var(--muted)',
        marginBottom: 8,
      }}>
        Target role{' '}
        <span style={{ color: 'var(--muted-light)', fontSize: '0.68rem', letterSpacing: '0.06em' }}>(OPTIONAL)</span>
      </label>
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder="e.g. Data Engineer, ML Engineer, Backend Engineer"
        style={{
          width: '100%',
          background: 'var(--surface)',
          border: '1.5px solid var(--border)',
          borderRadius: 3,
          padding: '11px 14px',
          color: 'var(--text)',
          fontFamily: 'var(--sans)',
          fontSize: '0.9rem',
          outline: 'none',
          transition: 'border-color 0.2s',
        }}
        onFocus={e => e.target.style.borderColor = 'var(--accent)'}
        onBlur={e => e.target.style.borderColor = 'var(--border)'}
      />
    </div>
  )
}
