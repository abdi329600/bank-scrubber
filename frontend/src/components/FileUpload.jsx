import React, { useState, useRef, useCallback } from 'react'
import { Upload, FileSpreadsheet, Zap, BarChart3, Loader2, AlertCircle } from 'lucide-react'

export default function FileUpload({ onUpload, loading, error }) {
  const [file, setFile] = useState(null)
  const [mode, setMode] = useState('full')
  const [businessName, setBusinessName] = useState('')
  const [period, setPeriod] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef(null)

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) setFile(dropped)
  }, [])

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    setDragOver(true)
  }, [])

  const handleDragLeave = useCallback(() => setDragOver(false), [])

  const handleSubmit = () => {
    if (!file) return
    onUpload(file, mode, businessName || 'Client', period || 'Current Period')
  }

  return (
    <div className="max-w-2xl mx-auto animate-fade-in">
      {/* Title */}
      <div className="text-center mb-10">
        <h2 className="text-3xl font-bold text-white mb-2">
          Analyze Your Financial Documents
        </h2>
        <p className="text-gray-400">
          Drag and drop a bank statement, CSV, or PDF to get started
        </p>
      </div>

      {/* Drop Zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
        className={`
          relative cursor-pointer rounded-2xl border-2 border-dashed p-12
          flex flex-col items-center justify-center gap-4 transition-all duration-300
          ${dragOver
            ? 'border-indigo-500 bg-indigo-500/10 scale-[1.02]'
            : file
              ? 'border-green-500/50 bg-green-500/5'
              : 'border-gray-700 bg-gray-900/50 hover:border-gray-500 hover:bg-gray-900'
          }
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.txt,.pdf"
          className="hidden"
          onChange={(e) => setFile(e.target.files[0])}
        />
        {file ? (
          <>
            <div className="w-16 h-16 rounded-2xl bg-green-500/10 flex items-center justify-center">
              <FileSpreadsheet size={32} className="text-green-400" />
            </div>
            <div className="text-center">
              <p className="text-white font-medium text-lg">{file.name}</p>
              <p className="text-gray-500 text-sm mt-1">
                {(file.size / 1024).toFixed(1)} KB &middot; Click or drop to change
              </p>
            </div>
          </>
        ) : (
          <>
            <div className={`w-16 h-16 rounded-2xl flex items-center justify-center
              ${dragOver ? 'bg-indigo-500/20' : 'bg-gray-800'}`}>
              <Upload size={32} className={dragOver ? 'text-indigo-400' : 'text-gray-400'} />
            </div>
            <div className="text-center">
              <p className="text-white font-medium">Drop your file here</p>
              <p className="text-gray-500 text-sm mt-1">CSV, TXT, or PDF &middot; Bank statements, receipts, invoices</p>
            </div>
          </>
        )}
      </div>

      {/* Mode Selector */}
      <div className="mt-8">
        <label className="text-sm font-medium text-gray-400 mb-3 block">Analysis Mode</label>
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => setMode('full')}
            className={`relative p-4 rounded-xl border-2 transition-all text-left
              ${mode === 'full'
                ? 'border-indigo-500 bg-indigo-500/10'
                : 'border-gray-800 bg-gray-900 hover:border-gray-700'
              }`}
          >
            <div className="flex items-center gap-3 mb-2">
              <BarChart3 size={20} className={mode === 'full' ? 'text-indigo-400' : 'text-gray-500'} />
              <span className="font-semibold text-white">Full Analysis</span>
            </div>
            <p className="text-xs text-gray-400 leading-relaxed">
              Complete CPA package: P&L, trial balance, Schedule C mapping,
              journal entries, flags, and downloadable PDF report.
            </p>
          </button>

          <button
            onClick={() => setMode('categorize')}
            className={`relative p-4 rounded-xl border-2 transition-all text-left
              ${mode === 'categorize'
                ? 'border-emerald-500 bg-emerald-500/10'
                : 'border-gray-800 bg-gray-900 hover:border-gray-700'
              }`}
          >
            <div className="flex items-center gap-3 mb-2">
              <Zap size={20} className={mode === 'categorize' ? 'text-emerald-400' : 'text-gray-500'} />
              <span className="font-semibold text-white">Quick Categorize</span>
            </div>
            <p className="text-xs text-gray-400 leading-relaxed">
              Fast and focused. Just categorizes each transaction with the highest
              accuracy using the 3-layer engine. No extra reports.
            </p>
          </button>
        </div>
      </div>

      {/* Business Info (only for full mode) */}
      {mode === 'full' && (
        <div className="mt-6 grid grid-cols-2 gap-4 animate-fade-in">
          <div>
            <label className="text-sm font-medium text-gray-400 mb-1 block">Business Name</label>
            <input
              type="text"
              placeholder="e.g. Acme Auto Shop"
              value={businessName}
              onChange={(e) => setBusinessName(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white
                placeholder-gray-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500
                transition-all text-sm"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-400 mb-1 block">Period</label>
            <input
              type="text"
              placeholder="e.g. January 2024"
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white
                placeholder-gray-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500
                transition-all text-sm"
            />
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 flex items-start gap-3 animate-fade-in">
          <AlertCircle size={18} className="text-red-400 mt-0.5 shrink-0" />
          <p className="text-red-300 text-sm">{error}</p>
        </div>
      )}

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={!file || loading}
        className={`mt-8 w-full py-3.5 rounded-xl font-semibold text-sm transition-all
          flex items-center justify-center gap-2
          ${!file || loading
            ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
            : mode === 'full'
              ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20'
              : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-500/20'
          }`}
      >
        {loading ? (
          <>
            <Loader2 size={18} className="spin-slow" />
            Processing...
          </>
        ) : (
          <>
            {mode === 'full' ? <BarChart3 size={18} /> : <Zap size={18} />}
            {mode === 'full' ? 'Run Full Analysis' : 'Quick Categorize'}
          </>
        )}
      </button>
    </div>
  )
}
