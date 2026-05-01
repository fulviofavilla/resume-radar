import { useState } from 'react'
import { useAnalysis, STATUS } from './hooks/useAnalysis'
import Header from './components/Header'
import UploadZone from './components/UploadZone'
import TargetRoleInput from './components/TargetRoleInput'
import ModeSwitch from './components/ModeSwitch'
import JobInput from './components/JobInput'
import { SubmitButton, DownloadButton } from './components/Buttons'
import Pipeline from './components/Pipeline'
import ScoreCard from './components/ScoreCard'
import Recommendations from './components/Recommendations'
import RewriteCards from './components/RewriteCards'
import JobList from './components/JobList'
import ErrorMessage from './components/ErrorMessage'
import Footer from './components/Footer'

const isProcessing = (status) =>
  status === STATUS.UPLOADING || status === STATUS.PROCESSING

export default function App() {
  const [mode, setMode] = useState('search') // 'search' | 'manual'

  const {
    file, setFile,
    targetRole, setTargetRole,
    jobDescription, setJobDescription,
    status,
    steps,
    results,
    jobId,
    error,
    submit,
  } = useAnalysis()

  const processing = isProcessing(status)
  const completed = status === STATUS.COMPLETED

  const handleModeChange = (newMode) => {
    setMode(newMode)
    // clear the other mode's input when switching
    if (newMode === 'search') setJobDescription('')
    if (newMode === 'manual') setTargetRole('')
  }

  const canSubmit = file && (
    mode === 'search' ||
    (mode === 'manual' && jobDescription.trim().length > 0)
  )

  return (
    <div style={{ maxWidth: 780, margin: '0 auto', padding: '60px 24px 40px' }}>
      <Header version="v1.0.0" />

      <UploadZone file={file} onFile={setFile} />

      <ModeSwitch mode={mode} onChange={handleModeChange} />

      {mode === 'search' && (
        <TargetRoleInput value={targetRole} onChange={setTargetRole} />
      )}

      {mode === 'manual' && (
        <JobInput value={jobDescription} onChange={setJobDescription} />
      )}

      <SubmitButton
        disabled={!canSubmit || processing}
        onClick={submit}
      />

      {completed && <DownloadButton jobId={jobId} />}

      <ErrorMessage message={error} />

      {processing && <Pipeline steps={steps} />}

      {completed && results && (
        <div style={{ marginTop: 56 }}>
          <ScoreCard report={results.report} profile={results.resume_profile} />
          <Recommendations recommendations={results.report.recommendations} />
          <RewriteCards rewrites={results.report.resume_rewrites} />
          {results.report.top_jobs?.length > 0 && (
            <JobList
              jobs={results.report.top_jobs}
              jobsAnalyzed={results.report.jobs_analyzed}
            />
          )}
        </div>
      )}

      <Footer />
    </div>
  )
}