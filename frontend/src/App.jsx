import React, { useState } from 'react'
import FileUpload from './components/FileUpload'
import ResultsDashboard from './components/ResultsDashboard'
import { Shield } from 'lucide-react'

export default function App() {
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleUpload = async (file, mode, businessName, period) => {
    setLoading(true)
    setError(null)
    setResults(null)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('mode', mode)
    formData.append('business_name', businessName)
    formData.append('period', period)

    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || 'Server error')
      }
      const data = await res.json()
      setResults(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setResults(null)
    setError(null)
  }

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-950/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center">
              <span className="text-lg font-bold text-white">FDP</span>
            </div>
            <div>
              <h1 className="text-lg font-semibold text-white tracking-tight">
                Financial Document Processor
              </h1>
              <p className="text-xs text-gray-500">100% Local &middot; Zero Network &middot; Audit-Ready</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Shield size={14} className="text-green-500" />
            <span>All data stays on your machine</span>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        {!results ? (
          <FileUpload
            onUpload={handleUpload}
            loading={loading}
            error={error}
          />
        ) : (
          <ResultsDashboard
            data={results}
            onReset={handleReset}
          />
        )}
      </main>
    </div>
  )
}
