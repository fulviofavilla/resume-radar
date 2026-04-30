import { useState, useCallback } from 'react'

export const STATUS = {
  IDLE: 'idle',
  UPLOADING: 'uploading',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
  FAILED: 'failed',
}

export const ALL_STEPS = [
  { id: 'parse_resume',    label: 'parse_resume',    desc: 'Waiting...', done: 'Skills extracted from resume.' },
  { id: 'search_jobs',     label: 'search_jobs',     desc: 'Waiting...', done: 'Job postings retrieved.' },
  { id: 'embed_match',     label: 'embed_match',     desc: 'Waiting...', done: 'Semantic match computed.' },
  { id: 'generate_report', label: 'generate_report', desc: 'Waiting...', done: 'Recommendations generated.' },
  { id: 'rewrite_resume',  label: 'rewrite_resume',  desc: 'Waiting...', done: 'Rewrite suggestions ready.' },
]

function getSteps(jobDescription) {
  if (jobDescription) {
    return ALL_STEPS.filter(s => s.id !== 'search_jobs')
  }
  return ALL_STEPS
}

function initStepState(steps) {
  return steps.map(s => ({ ...s, status: 'waiting', message: s.desc }))
}

export function useAnalysis() {
  const [file, setFile] = useState(null)
  const [targetRole, setTargetRole] = useState('')
  const [jobDescription, setJobDescription] = useState('')
  const [status, setStatus] = useState(STATUS.IDLE)
  const [steps, setSteps] = useState(initStepState(ALL_STEPS))
  const [results, setResults] = useState(null)
  const [jobId, setJobId] = useState(null)
  const [error, setError] = useState('')

  const updateStep = useCallback((stepId, patch) => {
    setSteps(prev => prev.map(s => s.id === stepId ? { ...s, ...patch } : s))
  }, [])

  const activateStep = useCallback((stepId, message) => {
    setSteps(prev => prev.map(s => {
      if (s.status === 'active') return { ...s, status: 'done', message: s.done }
      if (s.id === stepId) return { ...s, status: 'active', message }
      return s
    }))
  }, [])

  const completeAllSteps = useCallback(() => {
    setSteps(prev => prev.map(s => ({
      ...s,
      status: 'done',
      message: s.done,
    })))
  }, [])

  const reset = useCallback((activeSteps) => {
    setSteps(initStepState(activeSteps))
    setResults(null)
    setError('')
    setJobId(null)
  }, [])

  const fetchResults = useCallback(async (id) => {
    const res = await fetch(`/results/${id}`)
    const data = await res.json()
    if (data.status === 'completed') {
      setResults(data)
      setStatus(STATUS.COMPLETED)
    } else {
      setError(data.error || 'Analysis failed.')
      setStatus(STATUS.FAILED)
    }
  }, [])

  const pollResults = useCallback(async (id) => {
    for (let i = 0; i < 60; i++) {
      await new Promise(r => setTimeout(r, 3000))
      const res = await fetch(`/results/${id}`)
      const data = await res.json()
      if (data.status === 'completed') {
        setResults(data)
        setStatus(STATUS.COMPLETED)
        return
      }
      if (data.status === 'failed') {
        setError(data.error || 'Analysis failed.')
        setStatus(STATUS.FAILED)
        return
      }
    }
    setError('Timed out waiting for results.')
    setStatus(STATUS.FAILED)
  }, [])

  const submit = useCallback(async () => {
    if (!file) return

    const activeSteps = getSteps(jobDescription)
    reset(activeSteps)
    setStatus(STATUS.UPLOADING)
    setError('')

    const form = new FormData()
    form.append('file', file)
    if (targetRole.trim()) form.append('target_role', targetRole.trim())
    if (jobDescription.trim()) form.append('job_description', jobDescription.trim())

    let id
    try {
      const res = await fetch('/analyze', { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Upload failed.')
      }
      const data = await res.json()
      id = data.job_id
      setJobId(id)
      setStatus(STATUS.PROCESSING)
    } catch (e) {
      setError(e.message)
      setStatus(STATUS.FAILED)
      return
    }

    // SSE stream
    const es = new EventSource(`/progress/${id}`)
    es.onmessage = (e) => {
      const event = JSON.parse(e.data)
      if (event.step === 'done') {
        es.close()
        completeAllSteps()
        fetchResults(id)
      } else if (event.step === 'error') {
        es.close()
        setError(event.message)
        setStatus(STATUS.FAILED)
      } else {
        activateStep(event.step, event.message)
      }
    }
    es.onerror = () => {
      es.close()
      pollResults(id)
    }
  }, [file, targetRole, jobDescription, reset, activateStep, completeAllSteps, fetchResults, pollResults])

  return {
    // state
    file, setFile,
    targetRole, setTargetRole,
    jobDescription, setJobDescription,
    status,
    steps,
    results,
    jobId,
    error,
    // actions
    submit,
  }
}
