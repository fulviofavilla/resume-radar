export default function Pipeline({ steps }) {
  if (!steps || steps.length === 0) return null

  return (
    <div style={{ marginTop: 48 }}>
      <div style={{
        fontFamily: 'var(--mono)',
        fontSize: '0.72rem',
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        color: 'var(--muted)',
        marginBottom: 20,
      }}>
        Pipeline
      </div>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {steps.map((step, i) => (
          <PipelineStep key={step.id} step={step} index={i} isLast={i === steps.length - 1} />
        ))}
      </div>
    </div>
  )
}

function PipelineStep({ step, index, isLast }) {
  const isActive = step.status === 'active'
  const isDone   = step.status === 'done'

  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-start',
      gap: 16,
      padding: '14px 0',
      borderBottom: isLast ? 'none' : '1px solid var(--border)',
      opacity: step.status === 'waiting' ? 0.3 : 1,
      transition: 'opacity 0.3s',
    }}>
      <div style={{
        width: 24,
        height: 24,
        borderRadius: '50%',
        border: `1.5px solid ${isActive || isDone ? 'var(--accent)' : 'var(--border)'}`,
        background: isDone ? 'var(--accent)' : isActive ? 'var(--accent-dim)' : 'transparent',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        marginTop: 1,
        transition: 'border-color 0.3s, background 0.3s',
        fontFamily: 'var(--mono)',
        fontSize: '0.65rem',
        color: isDone ? '#0a0a0a' : isActive ? 'var(--accent)' : 'var(--muted)',
      }}>
        {isDone ? '✓' : index + 1}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontFamily: 'var(--mono)', fontSize: '0.8rem', color: 'var(--text)', marginBottom: 2 }}>
          {step.label}
        </div>
        <div style={{
          fontSize: '0.78rem',
          color: isActive ? 'var(--accent)' : isDone ? 'var(--muted-light)' : 'var(--muted)',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}>
          {isActive && <span className="spinner" />}
          {step.message}
        </div>
      </div>
    </div>
  )
}
