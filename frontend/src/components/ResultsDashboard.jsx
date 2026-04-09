import React, { useState } from 'react'
import {
  ArrowLeft, Download, FileText, BarChart3, Scale, FileCheck,
  AlertTriangle, List, TrendingUp, TrendingDown, DollarSign,
  CheckCircle2, XCircle, ChevronDown, ChevronUp, Tag, Shield,
  Landmark, Eye, Info, Banknote, Lock
} from 'lucide-react'

function money(v) {
  const n = Number(v) || 0
  const prefix = n < 0 ? '-$' : '$'
  return prefix + Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function pct(v) {
  return (Number(v) * 100).toFixed(1) + '%'
}

function Badge({ children, color = 'gray' }) {
  const colors = {
    green: 'bg-green-500/10 text-green-400 border-green-500/20',
    red: 'bg-red-500/10 text-red-400 border-red-500/20',
    yellow: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    blue: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    indigo: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
    gray: 'bg-gray-500/10 text-gray-400 border-gray-500/20',
    emerald: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  }
  return (
    <span className={`px-2 py-0.5 rounded-md text-xs font-medium border ${colors[color]}`}>
      {children}
    </span>
  )
}

function StatCard({ label, value, icon: Icon, color = 'indigo', sub }) {
  const bg = {
    indigo: 'from-indigo-500/10 to-indigo-500/5 border-indigo-500/20',
    green: 'from-green-500/10 to-green-500/5 border-green-500/20',
    red: 'from-red-500/10 to-red-500/5 border-red-500/20',
    yellow: 'from-yellow-500/10 to-yellow-500/5 border-yellow-500/20',
    emerald: 'from-emerald-500/10 to-emerald-500/5 border-emerald-500/20',
  }
  const ic = {
    indigo: 'text-indigo-400', green: 'text-green-400', red: 'text-red-400',
    yellow: 'text-yellow-400', emerald: 'text-emerald-400',
  }
  return (
    <div className={`rounded-xl border bg-gradient-to-br p-5 ${bg[color]}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">{label}</span>
        <Icon size={18} className={ic[color]} />
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  )
}

function TabButton({ active, onClick, children, icon: Icon }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg transition-all
        ${active
          ? 'bg-gray-800 text-white'
          : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800/50'
        }`}
    >
      <Icon size={16} />
      {children}
    </button>
  )
}

/* ─── TRANSACTIONS TABLE ─────────────────────────────────────── */
function TransactionsTab({ transactions }) {
  const [sortField, setSortField] = useState('date')
  const [sortAsc, setSortAsc] = useState(true)
  const [filter, setFilter] = useState('')

  const filtered = transactions.filter(t =>
    t.description.toLowerCase().includes(filter.toLowerCase()) ||
    t.account_name?.toLowerCase().includes(filter.toLowerCase()) ||
    t.account_code?.includes(filter)
  )

  const sorted = [...filtered].sort((a, b) => {
    let cmp = 0
    if (sortField === 'amount') cmp = a.amount - b.amount
    else if (sortField === 'confidence') cmp = a.confidence - b.confidence
    else cmp = (a[sortField] || '').localeCompare(b[sortField] || '')
    return sortAsc ? cmp : -cmp
  })

  const toggleSort = (field) => {
    if (sortField === field) setSortAsc(!sortAsc)
    else { setSortField(field); setSortAsc(true) }
  }

  const SortIcon = ({ field }) => {
    if (sortField !== field) return null
    return sortAsc ? <ChevronUp size={12} /> : <ChevronDown size={12} />
  }

  return (
    <div className="animate-fade-in">
      <input
        type="text"
        placeholder="Search transactions..."
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="w-full mb-4 px-4 py-2.5 rounded-xl bg-gray-900 border border-gray-800 text-white
          placeholder-gray-600 focus:outline-none focus:border-indigo-500 text-sm"
      />
      <div className="overflow-x-auto rounded-xl border border-gray-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-900 text-gray-400 text-xs uppercase tracking-wider">
              <th className="px-4 py-3 text-left cursor-pointer select-none" onClick={() => toggleSort('date')}>
                <span className="flex items-center gap-1">Date <SortIcon field="date" /></span>
              </th>
              <th className="px-4 py-3 text-left">Description</th>
              <th className="px-4 py-3 text-right cursor-pointer select-none" onClick={() => toggleSort('amount')}>
                <span className="flex items-center gap-1 justify-end">Amount <SortIcon field="amount" /></span>
              </th>
              <th className="px-4 py-3 text-left">Category</th>
              <th className="px-4 py-3 text-center cursor-pointer select-none" onClick={() => toggleSort('confidence')}>
                <span className="flex items-center gap-1 justify-center">Conf. <SortIcon field="confidence" /></span>
              </th>
              <th className="px-4 py-3 text-left">Layer</th>
              <th className="px-4 py-3 text-center">Flags</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {sorted.map((t, i) => (
              <tr key={i} className={`hover:bg-gray-800/30 transition-colors
                ${t.required_review ? 'bg-yellow-500/[0.04]' : ''}
                ${t.flags?.length > 0 ? 'bg-yellow-500/[0.03]' : ''}`}>
                <td className="px-4 py-3 text-gray-300 whitespace-nowrap text-xs">{t.date}</td>
                <td className="px-4 py-3 max-w-[280px]">
                  <div className="text-white font-medium truncate">{t.description}</div>
                  <div className="flex items-center gap-1 mt-0.5">
                    {t.inflow_type && t.inflow_type !== 'OUTFLOW' && (
                      <Badge color={t.inflow_type === 'REVENUE' ? 'green' : t.inflow_type === 'TRANSFER' ? 'blue' : t.inflow_type === 'UNKNOWN' ? 'yellow' : 'gray'}>
                        {t.inflow_type}
                      </Badge>
                    )}
                    {t.is_capex && <Badge color="indigo">CAPEX</Badge>}
                    {t.loan_principal && <Badge color="gray">LOAN</Badge>}
                    {t.required_review && <Badge color="yellow">REVIEW</Badge>}
                  </div>
                </td>
                <td className={`px-4 py-3 text-right font-mono font-medium whitespace-nowrap
                  ${t.direction === 'CREDIT' ? 'text-green-400' : 'text-red-400'}`}>
                  {t.direction === 'CREDIT' ? '+' : '-'}{money(Math.abs(t.amount))}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500 font-mono">{t.account_code}</span>
                    <span className="text-gray-300 text-xs">{t.account_name}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-center">
                  <ConfidenceBar value={t.confidence} />
                </td>
                <td className="px-4 py-3">
                  <Badge color={t.layer === 'exact_match' ? 'green' : t.layer === 'pattern_match' ? 'blue' : 'yellow'}>
                    {t.layer === 'exact_match' ? 'Exact' : t.layer === 'pattern_match' ? 'Pattern' : 'Review'}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-center">
                  {t.flags?.length > 0 && (
                    <span className="text-yellow-400" title={t.flag_notes?.join('\n')}>
                      <AlertTriangle size={14} />
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-gray-600 mt-3">Showing {sorted.length} of {transactions.length} transactions</p>
    </div>
  )
}

function ConfidenceBar({ value }) {
  const pctVal = Math.round(value * 100)
  const color = pctVal >= 90 ? 'bg-green-500' : pctVal >= 70 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-12 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pctVal}%` }} />
      </div>
      <span className="text-xs text-gray-500 font-mono">{pctVal}%</span>
    </div>
  )
}

/* ─── P&L TAB ───────────────────────────────────────────── */
function PLTab({ pnl }) {
  if (!pnl) return <p className="text-gray-500">Run a full analysis to see P&L.</p>

  const Section = ({ title, lines, total, color }) => (
    <div className="mb-6">
      <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">{title}</h4>
      {lines?.map((l, i) => (
        <div key={i} className="flex justify-between py-1.5 px-3 text-sm border-b border-gray-800/40">
          <span className="text-gray-300"><span className="text-gray-600 font-mono text-xs mr-2">{l.code}</span>{l.name}</span>
          <span className={`font-mono ${color}`}>{money(l.amount)}</span>
        </div>
      ))}
      <div className="flex justify-between py-2 px-3 font-semibold text-sm bg-gray-800/30 rounded-lg mt-1">
        <span className="text-white">Total {title}</span>
        <span className={`font-mono ${color}`}>{money(total)}</span>
      </div>
    </div>
  )

  const basisLabels = {
    cash_basis_from_bank_activity: 'Cash Basis (Bank Activity)',
    accrual_basis: 'Accrual Basis',
  }

  return (
    <div className="animate-fade-in max-w-2xl">
      {/* Basis label + disclosure */}
      {pnl.basis && (
        <div className="flex items-center gap-2 mb-4 px-3 py-2 rounded-lg bg-gray-900/50 border border-gray-800">
          <Lock size={14} className="text-gray-500" />
          <span className="text-xs text-gray-400">
            {basisLabels[pnl.basis] || pnl.basis}
          </span>
        </div>
      )}

      <Section title="Revenue" lines={pnl.revenue?.lines} total={pnl.revenue?.total} color="text-green-400" />
      <Section title="Cost of Goods Sold" lines={pnl.cogs?.lines} total={pnl.cogs?.total} color="text-red-400" />

      <div className="flex justify-between py-3 px-4 rounded-xl bg-indigo-500/10 border border-indigo-500/20 mb-6">
        <span className="font-bold text-white">Gross Profit</span>
        <div className="text-right">
          <span className="font-mono font-bold text-indigo-400 text-lg">{money(pnl.gross_profit)}</span>
          <span className="text-xs text-gray-500 ml-2">({pnl.gross_margin_pct}%)</span>
        </div>
      </div>

      <Section title="Operating Expenses" lines={pnl.operating_expenses?.lines} total={pnl.operating_expenses?.total} color="text-red-400" />

      {/* Interest expense row */}
      {Number(pnl.interest_expense) > 0 && (
        <div className="flex justify-between py-2 px-3 text-sm border-b border-gray-800/40 mb-2">
          <span className="text-gray-300"><span className="text-gray-600 font-mono text-xs mr-2">6700</span>Interest Expense</span>
          <span className="font-mono text-red-400">{money(pnl.interest_expense)}</span>
        </div>
      )}

      <div className={`flex justify-between py-4 px-4 rounded-xl border text-lg font-bold
        ${pnl.net_income >= 0
          ? 'bg-green-500/10 border-green-500/20'
          : 'bg-red-500/10 border-red-500/20'
        }`}>
        <span className="text-white">Net Income</span>
        <span className={`font-mono ${pnl.net_income >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {money(pnl.net_income)}
        </span>
      </div>

      {/* P&L Warnings */}
      {pnl.warnings?.length > 0 && (
        <div className="mt-6 space-y-2">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Validation Warnings</h4>
          {pnl.warnings.map((w, i) => (
            <div key={i} className={`rounded-lg border px-3 py-2 text-xs flex items-start gap-2
              ${w.startsWith('MATH_ERROR') ? 'border-red-500/20 bg-red-500/5 text-red-400'
              : w.startsWith('SEMANTIC') ? 'border-yellow-500/20 bg-yellow-500/5 text-yellow-400'
              : w.startsWith('DISCLOSURE') ? 'border-blue-500/20 bg-blue-500/5 text-blue-400'
              : 'border-gray-700 bg-gray-900/50 text-gray-400'}`}>
              <AlertTriangle size={12} className="mt-0.5 shrink-0" />
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}

      {/* Assumptions disclosure */}
      {pnl.assumptions?.length > 0 && (
        <div className="mt-6 space-y-1">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Assumptions & Limitations</h4>
          {pnl.assumptions.map((a, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-gray-500 px-3 py-1">
              <Info size={12} className="mt-0.5 shrink-0 text-gray-600" />
              <span>{a}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ─── TRIAL BALANCE TAB ─────────────────────────────────────── */
function TrialBalanceTab({ tb }) {
  if (!tb) return <p className="text-gray-500">Run a full analysis to see the trial balance.</p>
  return (
    <div className="animate-fade-in">
      <div className="flex items-center gap-3 mb-4">
        {tb.is_balanced
          ? <Badge color="green"><CheckCircle2 size={12} className="inline mr-1" />BALANCED</Badge>
          : <Badge color="red"><XCircle size={12} className="inline mr-1" />OUT OF BALANCE</Badge>
        }
      </div>
      <div className="overflow-x-auto rounded-xl border border-gray-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-900 text-gray-400 text-xs uppercase tracking-wider">
              <th className="px-4 py-3 text-left">Account</th>
              <th className="px-4 py-3 text-left">Name</th>
              <th className="px-4 py-3 text-left">Type</th>
              <th className="px-4 py-3 text-right">Debit</th>
              <th className="px-4 py-3 text-right">Credit</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {tb.accounts?.map((a, i) => (
              <tr key={i} className="hover:bg-gray-800/30 transition-colors">
                <td className="px-4 py-2.5 font-mono text-gray-400 text-xs">{a.code}</td>
                <td className="px-4 py-2.5 text-white">{a.name}</td>
                <td className="px-4 py-2.5"><Badge color={
                  a.type === 'REVENUE' ? 'green' : a.type === 'EXPENSE' ? 'red'
                    : a.type === 'ASSET' ? 'blue' : a.type === 'COGS' ? 'yellow' : 'gray'
                }>{a.type}</Badge></td>
                <td className="px-4 py-2.5 text-right font-mono text-gray-300">{a.debit ? money(a.debit) : ''}</td>
                <td className="px-4 py-2.5 text-right font-mono text-gray-300">{a.credit ? money(a.credit) : ''}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="bg-gray-800/50 font-bold">
              <td colSpan={3} className="px-4 py-3 text-white">TOTALS</td>
              <td className="px-4 py-3 text-right font-mono text-white">{money(tb.total_debits)}</td>
              <td className="px-4 py-3 text-right font-mono text-white">{money(tb.total_credits)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  )
}

/* ─── FLAGS TAB ─────────────────────────────────────────────── */
function FlagsTab({ flags, transactions }) {
  if (!flags) return <p className="text-gray-500">Run a full analysis to see flags.</p>

  const sevColor = { CRITICAL: 'red', HIGH: 'yellow', MEDIUM: 'blue', LOW: 'gray' }
  const flaggedTxns = transactions.filter(t => t.flags?.length > 0)

  return (
    <div className="animate-fade-in">
      <div className="grid grid-cols-4 gap-3 mb-6">
        {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(sev => (
          <div key={sev} className={`rounded-xl border p-3 text-center
            ${sev === 'CRITICAL' ? 'border-red-500/30 bg-red-500/5'
              : sev === 'HIGH' ? 'border-yellow-500/30 bg-yellow-500/5'
                : sev === 'MEDIUM' ? 'border-blue-500/30 bg-blue-500/5'
                  : 'border-gray-700 bg-gray-900'}`}>
            <p className="text-2xl font-bold text-white">{flags.by_severity?.[sev] || 0}</p>
            <p className="text-xs text-gray-500 mt-1">{sev}</p>
          </div>
        ))}
      </div>

      {flaggedTxns.length > 0 && (
        <div className="space-y-3">
          {flaggedTxns.map((t, i) => (
            <div key={i} className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-500">{t.date}</span>
                  <span className="text-white font-medium">{t.description}</span>
                </div>
                <span className={`font-mono font-medium ${t.direction === 'CREDIT' ? 'text-green-400' : 'text-red-400'}`}>
                  {money(t.amount)}
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                {t.flags.map((f, j) => (
                  <Badge key={j} color={sevColor[getFlagSeverity(f)] || 'gray'}>{f}</Badge>
                ))}
              </div>
              {t.flag_notes?.length > 0 && (
                <div className="mt-2 space-y-1">
                  {t.flag_notes.map((n, j) => (
                    <p key={j} className="text-xs text-yellow-400/70 leading-relaxed">{n}</p>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function getFlagSeverity(flag) {
  const map = {
    BALANCE_MISMATCH: 'CRITICAL', DUPLICATE_TRANSACTION: 'HIGH', MEALS_OVER_75: 'MEDIUM',
    LARGE_CASH_WITHDRAWAL: 'MEDIUM', ROUND_NUMBER_SUSPICIOUS: 'LOW', CASH_NEAR_10K: 'HIGH',
    PERSONAL_EXPENSE_MIXED: 'MEDIUM', LOW_CONFIDENCE_CATEGORY: 'MEDIUM', AMBIGUOUS_VENDOR: 'MEDIUM',
    POSSIBLE_CAPITAL_EXPENSE: 'HIGH', LOAN_PAYMENT_DETECTED: 'MEDIUM',
    INFLOW_UNCLASSIFIED: 'MEDIUM', BELOW_THRESHOLD: 'MEDIUM', LOAN_NEEDS_SPLIT: 'HIGH',
    CAPEX_DETECTED: 'HIGH', LARGE_EXPENSE_REVIEW: 'MEDIUM',
  }
  return map[flag] || 'LOW'
}

/* ─── SCHEDULE C TAB ────────────────────────────────────────── */
function ScheduleCTab({ sc }) {
  if (!sc) return <p className="text-gray-500">Run a full analysis to see Schedule C mapping.</p>
  const summary = sc.summary || {}

  return (
    <div className="animate-fade-in">
      {/* Summary */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <div className="rounded-xl border border-green-500/20 bg-green-500/5 p-4">
          <p className="text-xs text-gray-400">Gross Receipts</p>
          <p className="text-xl font-bold text-green-400 font-mono mt-1">{money(summary.gross_receipts)}</p>
        </div>
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4">
          <p className="text-xs text-gray-400">Total Expenses</p>
          <p className="text-xl font-bold text-red-400 font-mono mt-1">{money(summary.total_expenses)}</p>
        </div>
        <div className={`rounded-xl border p-4 ${summary.net_profit >= 0
          ? 'border-emerald-500/20 bg-emerald-500/5' : 'border-red-500/20 bg-red-500/5'}`}>
          <p className="text-xs text-gray-400">Net Profit (Line 31)</p>
          <p className={`text-xl font-bold font-mono mt-1 ${summary.net_profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {money(summary.net_profit)}
          </p>
        </div>
      </div>

      {/* Lines */}
      <div className="rounded-xl border border-gray-800 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-900 text-gray-400 text-xs uppercase tracking-wider">
              <th className="px-4 py-3 text-left">Schedule C Line</th>
              <th className="px-4 py-3 text-right">Amount</th>
              <th className="px-4 py-3 text-right">Transactions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {Object.entries(sc.lines || {}).map(([line, data], i) => (
              <tr key={i} className="hover:bg-gray-800/30 transition-colors">
                <td className="px-4 py-2.5 text-gray-300">{line}</td>
                <td className="px-4 py-2.5 text-right font-mono text-white">{money(data.total)}</td>
                <td className="px-4 py-2.5 text-right text-gray-500">{data.transaction_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ─── ACCEPTANCE GATES BANNER ────────────────────────────────── */
function AcceptanceBanner({ acceptance, reconciliation, method_label }) {
  if (!acceptance) return null
  const statusColor = {
    PASS: 'border-green-500/30 bg-green-500/5',
    PASS_WITH_WARNINGS: 'border-yellow-500/30 bg-yellow-500/5',
    BLOCKED: 'border-red-500/30 bg-red-500/5',
  }
  const statusIcon = {
    PASS: <CheckCircle2 size={18} className="text-green-400" />,
    PASS_WITH_WARNINGS: <AlertTriangle size={18} className="text-yellow-400" />,
    BLOCKED: <XCircle size={18} className="text-red-400" />,
  }
  const reconColor = { GREEN: 'text-green-400', YELLOW: 'text-yellow-400', RED: 'text-red-400' }

  return (
    <div className={`rounded-xl border p-4 mb-6 ${statusColor[acceptance.overall_status] || statusColor.BLOCKED}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          {statusIcon[acceptance.overall_status]}
          <div>
            <p className="text-white font-semibold text-sm">
              {acceptance.overall_status === 'PASS' ? 'All Acceptance Gates Pass' :
               acceptance.overall_status === 'PASS_WITH_WARNINGS' ? 'Pass With Warnings' :
               'Acceptance Gates Blocked'}
            </p>
            <p className="text-xs text-gray-400 mt-0.5">{acceptance.summary}</p>
          </div>
        </div>
        {reconciliation && (
          <div className="flex items-center gap-2 text-xs">
            <Landmark size={14} className={reconColor[reconciliation.status] || 'text-gray-500'} />
            <span className={reconColor[reconciliation.status]}>Recon: {reconciliation.status}</span>
          </div>
        )}
      </div>
      <div className="grid grid-cols-4 gap-2 mt-3">
        {acceptance.gates?.map((g, i) => (
          <div key={i} className={`rounded-lg border px-3 py-2 text-xs
            ${g.passed ? 'border-green-500/20 bg-green-500/5' : g.blocker ? 'border-red-500/20 bg-red-500/5' : 'border-yellow-500/20 bg-yellow-500/5'}`}>
            <div className="flex items-center gap-1.5 mb-1">
              {g.passed ? <CheckCircle2 size={12} className="text-green-400" /> : <XCircle size={12} className={g.blocker ? 'text-red-400' : 'text-yellow-400'} />}
              <span className="font-semibold text-white">{g.name}</span>
            </div>
            <p className="text-gray-500 leading-relaxed">{g.details}</p>
          </div>
        ))}
      </div>
      {method_label && (
        <div className="mt-3 flex items-center gap-2 text-xs text-gray-500">
          <Lock size={12} />
          <span>{method_label}</span>
        </div>
      )}
    </div>
  )
}

/* ─── VALIDATION TAB ────────────────────────────────────────── */
function ValidationTab({ validation, reconciliation, acceptance }) {
  if (!validation) return <p className="text-gray-500">Run a full analysis to see validation.</p>
  const sevColor = { CRITICAL: 'red', HIGH: 'yellow', MEDIUM: 'blue', LOW: 'gray' }

  return (
    <div className="animate-fade-in space-y-6">
      {/* Structural vs Semantic */}
      <div className="grid grid-cols-2 gap-4">
        <div className={`rounded-xl border p-4 ${validation.structural_pass ? 'border-green-500/20 bg-green-500/5' : 'border-red-500/20 bg-red-500/5'}`}>
          <div className="flex items-center gap-2 mb-2">
            {validation.structural_pass ? <CheckCircle2 size={16} className="text-green-400" /> : <XCircle size={16} className="text-red-400" />}
            <span className="text-white font-semibold text-sm">Structural Integrity</span>
          </div>
          <p className="text-xs text-gray-400">{validation.structural_issues} issue(s) — JE balance, TB balance, reconciliation</p>
        </div>
        <div className={`rounded-xl border p-4 ${validation.semantic_pass ? 'border-green-500/20 bg-green-500/5' : 'border-yellow-500/20 bg-yellow-500/5'}`}>
          <div className="flex items-center gap-2 mb-2">
            {validation.semantic_pass ? <CheckCircle2 size={16} className="text-green-400" /> : <AlertTriangle size={16} className="text-yellow-400" />}
            <span className="text-white font-semibold text-sm">Semantic Validity</span>
          </div>
          <p className="text-xs text-gray-400">{validation.semantic_issues} issue(s) — classification meaning, deductibility, routing</p>
        </div>
      </div>

      {/* Reconciliation detail */}
      {reconciliation && (
        <div className={`rounded-xl border p-4 ${reconciliation.status === 'GREEN' ? 'border-green-500/20 bg-green-500/5' : reconciliation.status === 'YELLOW' ? 'border-yellow-500/20 bg-yellow-500/5' : 'border-red-500/20 bg-red-500/5'}`}>
          <div className="flex items-center gap-2 mb-2">
            <Landmark size={16} className={reconciliation.status === 'GREEN' ? 'text-green-400' : reconciliation.status === 'YELLOW' ? 'text-yellow-400' : 'text-red-400'} />
            <span className="text-white font-semibold text-sm">Bank Reconciliation: {reconciliation.status}</span>
          </div>
          {reconciliation.issues?.map((issue, i) => (
            <p key={i} className="text-xs text-gray-400 mt-1">- {issue}</p>
          ))}
          {reconciliation.recommendations?.map((rec, i) => (
            <p key={i} className="text-xs text-blue-400/70 mt-1">Rec: {rec}</p>
          ))}
        </div>
      )}

      {/* Issue list */}
      {validation.issues?.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">All Validation Issues</h4>
          {validation.issues.map((issue, i) => (
            <div key={i} className="rounded-lg border border-gray-800 bg-gray-900/50 p-3 flex items-start gap-3">
              <Badge color={sevColor[issue.severity] || 'gray'}>{issue.severity}</Badge>
              <div>
                <div className="flex items-center gap-2">
                  <Badge color={issue.category === 'structural' ? 'indigo' : 'blue'}>{issue.category}</Badge>
                  <span className="text-xs text-gray-500 font-mono">{issue.code}</span>
                </div>
                <p className="text-xs text-gray-300 mt-1">{issue.message}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ─── MAIN DASHBOARD ────────────────────────────────────────── */
export default function ResultsDashboard({ data, onReset }) {
  const [tab, setTab] = useState('transactions')
  const [showReviewOnly, setShowReviewOnly] = useState(false)
  const isFullMode = data.mode === 'full'
  const cat = data.categorization || {}
  const pnl = data.profit_and_loss
  const tb = data.trial_balance
  const flags = data.flags
  const sc = data.schedule_c
  const recon = data.reconciliation
  const validation = data.validation
  const acceptance = data.acceptance

  const downloadPDF = () => window.open('/api/download-pdf', '_blank')
  const downloadJSON = () => window.open('/api/download-json', '_blank')

  const displayTxns = showReviewOnly
    ? (data.transactions || []).filter(t => t.required_review || t.flags?.length > 0)
    : (data.transactions || [])

  return (
    <div className="animate-fade-in">
      {/* Top bar */}
      <div className="flex items-center justify-between mb-6">
        <button onClick={onReset} className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors">
          <ArrowLeft size={16} /> Upload new file
        </button>
        <div className="flex gap-2">
          {isFullMode && (
            <>
              <button onClick={downloadPDF}
                className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-all">
                <Download size={14} /> PDF Report
              </button>
              <button onClick={downloadJSON}
                className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-all border border-gray-700">
                <FileText size={14} /> JSON
              </button>
            </>
          )}
        </div>
      </div>

      {/* Acceptance Gates Banner (Full mode only) */}
      {isFullMode && <AcceptanceBanner acceptance={acceptance} reconciliation={recon} method_label={data.method_label} />}

      {/* Stats Row */}
      <div className={`grid gap-4 mb-8 ${isFullMode ? 'grid-cols-5' : 'grid-cols-4'}`}>
        <StatCard label="Transactions" value={data.transaction_count}
          icon={List} color="indigo" sub={data.file_name} />
        <StatCard label="Auto-Categorized"
          value={`${cat.exact_match + cat.pattern_match}/${data.transaction_count}`}
          icon={Tag} color="emerald"
          sub={`${cat.exact_match} exact, ${cat.pattern_match} pattern`} />
        <StatCard label="Avg Confidence" value={pct(cat.avg_confidence)}
          icon={CheckCircle2}
          color={cat.avg_confidence >= 0.85 ? 'green' : cat.avg_confidence >= 0.7 ? 'yellow' : 'red'}
          sub={`Threshold: ${pct(cat.threshold)} (${cat.mode})`} />
        <StatCard label="Review Queue" value={cat.review_queue || 0}
          icon={Eye}
          color={(cat.review_queue || 0) > 0 ? 'yellow' : 'green'}
          sub={(cat.review_queue || 0) > 0 ? 'Items need human review' : 'All clear'} />
        {isFullMode && pnl && (
          <StatCard label="Net Income" value={money(pnl.net_income)}
            icon={pnl.net_income >= 0 ? TrendingUp : TrendingDown}
            color={pnl.net_income >= 0 ? 'green' : 'red'}
            sub={`Gross margin ${pnl.gross_margin_pct}%`} />
        )}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-6 bg-gray-900/50 p-1 rounded-xl border border-gray-800 overflow-x-auto">
        <TabButton active={tab === 'transactions'} onClick={() => setTab('transactions')} icon={List}>
          Transactions
        </TabButton>
        {isFullMode && (
          <>
            <TabButton active={tab === 'pnl'} onClick={() => setTab('pnl')} icon={BarChart3}>
              P&L
            </TabButton>
            <TabButton active={tab === 'trial_balance'} onClick={() => setTab('trial_balance')} icon={Scale}>
              Trial Balance
            </TabButton>
            <TabButton active={tab === 'schedule_c'} onClick={() => setTab('schedule_c')} icon={FileCheck}>
              Schedule C
            </TabButton>
            <TabButton active={tab === 'flags'} onClick={() => setTab('flags')} icon={AlertTriangle}>
              Flags {flags?.total > 0 && <Badge color="yellow">{flags.total}</Badge>}
            </TabButton>
            <TabButton active={tab === 'validation'} onClick={() => setTab('validation')} icon={Shield}>
              Integrity
            </TabButton>
          </>
        )}
      </div>

      {/* Review Queue Toggle */}
      {tab === 'transactions' && (cat.review_queue || 0) > 0 && (
        <div className="mb-4 flex items-center gap-3">
          <button
            onClick={() => setShowReviewOnly(!showReviewOnly)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border
              ${showReviewOnly
                ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
                : 'bg-gray-900 border-gray-800 text-gray-500 hover:text-gray-300'}`}
          >
            <Eye size={14} />
            {showReviewOnly ? `Showing ${displayTxns.length} review items` : `Show review queue (${cat.review_queue})`}
          </button>
        </div>
      )}

      {/* Tab Content */}
      <div>
        {tab === 'transactions' && <TransactionsTab transactions={displayTxns} />}
        {tab === 'pnl' && <PLTab pnl={pnl} />}
        {tab === 'trial_balance' && <TrialBalanceTab tb={tb} />}
        {tab === 'schedule_c' && <ScheduleCTab sc={sc} />}
        {tab === 'flags' && <FlagsTab flags={flags} transactions={data.transactions || []} />}
        {tab === 'validation' && <ValidationTab validation={validation} reconciliation={recon} acceptance={acceptance} />}
      </div>
    </div>
  )
}
