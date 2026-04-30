import { useRef, useState } from 'react'

export default function UploadZone({ file, onFile }) {
  const inputRef = useRef(null)
  const [dragover, setDragover] = useState(false)
  const [hovered, setHovered] = useState(false)

  const handleDrop = (e) => {
    e.preventDefault()
    setDragover(false)
    const f = e.dataTransfer.files[0]
    if (f && f.type === 'application/pdf') onFile(f)
  }

  const active = dragover || hovered

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={e => { e.preventDefault(); setDragover(true) }}
      onDragLeave={() => setDragover(false)}
      onDrop={handleDrop}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        border: `1.5px dashed ${active ? 'var(--accent)' : 'var(--border)'}`,
        borderRadius: 4,
        padding: '48px 32px',
        textAlign: 'center',
        cursor: 'pointer',
        background: active ? 'var(--accent-dim)' : 'transparent',
        transition: 'border-color 0.2s, background 0.2s',
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        style={{ display: 'none' }}
        onChange={e => e.target.files[0] && onFile(e.target.files[0])}
      />
      <span style={{ fontSize: '2rem', display: 'block', marginBottom: 12 }}>⬆</span>
      <div style={{ fontFamily: 'var(--mono)', fontSize: '0.85rem', color: 'var(--muted)' }}>
        Drop your resume PDF here, or <span style={{ color: 'var(--accent)' }}>click to browse</span>
      </div>
      {file && (
        <div style={{ marginTop: 10, fontSize: '0.8rem', color: 'var(--accent)', fontFamily: 'var(--mono)' }}>
          {file.name}
        </div>
      )}
    </div>
  )
}