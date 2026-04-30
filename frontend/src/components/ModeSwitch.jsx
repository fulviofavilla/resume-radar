export default function ModeSwitch({ mode, onChange }) {
  return (
    <div style={{ display: 'flex', gap: 0, marginTop: 20 }}>
      <ModeBtn
        active={mode === 'search'}
        onClick={() => onChange('search')}
        label="Search jobs automatically"
      />
      <ModeBtn
        active={mode === 'manual'}
        onClick={() => onChange('manual')}
        label="Paste a job description"
      />
    </div>
  )
}

function ModeBtn({ active, onClick, label }) {
  return (
    <button
      onClick={onClick}
      style={{
        flex: 1,
        padding: '9px 14px',
        fontFamily: 'var(--mono)',
        fontSize: '0.72rem',
        letterSpacing: '0.04em',
        cursor: 'pointer',
        border: '1.5px solid var(--border)',
        background: active ? 'var(--accent-dim)' : 'transparent',
        color: active ? 'var(--accent)' : 'var(--muted)',
        transition: 'background 0.2s, color 0.2s',
        borderRadius: 0,
      }}
      onMouseEnter={e => { if (!active) e.currentTarget.style.color = 'var(--text)' }}
      onMouseLeave={e => { if (!active) e.currentTarget.style.color = 'var(--muted)' }}
    >
      {label}
    </button>
  )
}