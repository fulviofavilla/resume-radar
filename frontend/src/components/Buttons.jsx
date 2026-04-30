export function SubmitButton({ disabled, onClick }) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      style={{
        marginTop: 24,
        width: '100%',
        background: 'var(--accent)',
        color: '#0a0a0a',
        border: 'none',
        borderRadius: 3,
        padding: 13,
        fontFamily: 'var(--mono)',
        fontSize: '0.85rem',
        fontWeight: 700,
        letterSpacing: '0.04em',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.35 : 1,
        transition: 'opacity 0.2s, transform 0.1s',
      }}
      onMouseEnter={e => { if (!disabled) e.currentTarget.style.opacity = '0.88' }}
      onMouseLeave={e => { if (!disabled) e.currentTarget.style.opacity = '1' }}
      onMouseDown={e => { if (!disabled) e.currentTarget.style.transform = 'scale(0.99)' }}
      onMouseUp={e => e.currentTarget.style.transform = 'scale(1)'}
    >
      Analyze resume
    </button>
  )
}

export function DownloadButton({ jobId }) {
  if (!jobId) return null
  return (
    <a
      href={`/results/${jobId}/pdf`}
      download
      style={{
        display: 'block',
        marginTop: 20,
        width: '100%',
        background: 'transparent',
        color: 'var(--accent)',
        border: '1.5px solid var(--accent)',
        borderRadius: 3,
        padding: 11,
        fontFamily: 'var(--mono)',
        fontSize: '0.8rem',
        fontWeight: 700,
        letterSpacing: '0.04em',
        cursor: 'pointer',
        textDecoration: 'none',
        textAlign: 'center',
        transition: 'background 0.2s',
      }}
      onMouseEnter={e => e.currentTarget.style.background = 'var(--accent-dim)'}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >
      ⬇ Download PDF report
    </a>
  )
}
