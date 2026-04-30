export default function ErrorMessage({ message }) {
  if (!message) return null
  return (
    <div style={{
      marginTop: 24,
      padding: '14px 18px',
      background: 'rgba(255,79,79,0.08)',
      border: '1.5px solid rgba(255,79,79,0.3)',
      borderRadius: 3,
      fontFamily: 'var(--mono)',
      fontSize: '0.8rem',
      color: 'var(--danger)',
    }}>
      ⚠ {message}
    </div>
  )
}
