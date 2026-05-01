export default function Footer() {
  return (
    <footer style={{
      marginTop: 80,
      paddingTop: 24,
      borderTop: '1px solid var(--border)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      flexWrap: 'wrap',
      gap: 12,
    }}>
      <span style={{
        fontFamily: 'var(--mono)',
        fontSize: '0.7rem',
        color: 'var(--muted)',
        letterSpacing: '0.04em',
      }}>
        ResumeRadar - open source, MIT license
      </span>
    </footer>
  )
}

function FooterLink({ href, children, external }) {
  return (
    <a
      href={href}
      {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
      style={{
        fontFamily: 'var(--mono)',
        fontSize: '0.7rem',
        color: 'var(--muted)',
        textDecoration: 'none',
        letterSpacing: '0.04em',
        transition: 'color 0.2s',
      }}
      onMouseEnter={e => e.currentTarget.style.color = 'var(--accent)'}
      onMouseLeave={e => e.currentTarget.style.color = 'var(--muted)'}
    >
      {children}
    </a>
  )
}