import { useState, useEffect, useCallback } from 'react'
import { Bell, Filter, CheckCircle, AlertTriangle, Search, Download, Trash2, RefreshCw } from 'lucide-react'
import { formatDistanceToNow, format } from 'date-fns'
import { useAlertStore } from '../store/alertStore'

const CRIME_EMOJI = { fight:'🥊', weapon:'🔫', accident:'🚗', suspicious:'👁️', riot:'🚨', criminal:'🦹', stolen_vehicle:'🚔', loitering:'⏱️' }
const SEV_CLS = { CRITICAL:'badge-critical', HIGH:'badge-high', MEDIUM:'badge-medium', LOW:'badge-low' }

function AlertCard({ alert, onResolve, onDelete }) {
  const [resolveForm, setResolveForm] = useState(false)
  const [notes, setNotes] = useState('')

  return (
    <div className={`card flex gap-4 transition-all hover:border-navy-500 ${alert.severity==='CRITICAL' && !alert.resolved ? 'border-red-600/50 alert-pulse' : ''}`}>
      {/* Icon */}
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-xl flex-shrink-0 ${
        alert.severity==='CRITICAL' ? 'bg-red-600/20' : alert.severity==='HIGH' ? 'bg-orange-600/20' : alert.severity==='MEDIUM' ? 'bg-yellow-600/20' : 'bg-green-600/20'
      }`}>
        {CRIME_EMOJI[alert.crime_type] || '⚠️'}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-white capitalize">{alert.crime_type?.replace('_',' ')}</span>
            <span className="text-slate-500 text-xs">#{alert.id}</span>
            {alert._live && <span className="text-xs bg-blue-600/20 text-blue-400 border border-blue-600/30 px-1.5 py-0.5 rounded">LIVE</span>}
          </div>
          <span className={SEV_CLS[alert.severity] || 'badge-low'}>{alert.severity}</span>
        </div>

        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5 text-xs text-slate-400">
          <span>📷 {alert.camera_id}</span>
          {alert.vehicle_id && <span>🚗 {alert.vehicle_id}</span>}
          <span>🎯 {((alert.confidence||0)*100).toFixed(0)}% confidence</span>
          {alert.person_count > 0 && <span>👥 {alert.person_count} persons</span>}
          {alert.criminal_name && <span className="text-red-400">🦹 {alert.criminal_name}</span>}
          {alert.plate_number  && <span className="text-orange-400">🚔 {alert.plate_number}</span>}
          {alert.crowd_risk > 0.5 && <span className="text-red-400">🚨 Riot {(alert.crowd_risk*100).toFixed(0)}%</span>}
          {alert.night_mode && <span className="text-cyan-400">🌙 Night</span>}
          {alert.latitude && (
            <a href={`https://maps.google.com/?q=${alert.latitude},${alert.longitude}`} target="_blank" rel="noreferrer" className="text-blue-400 hover:text-blue-300">
              📍 Map
            </a>
          )}
        </div>

        <div className="flex items-center justify-between mt-2 flex-wrap gap-2">
          <span className="text-xs text-slate-500">
            {alert.timestamp ? formatDistanceToNow(new Date(alert.timestamp), {addSuffix:true}) : '—'}
          </span>
          <div className="flex items-center gap-2">
            {!alert.resolved ? (
              <>
                {resolveForm ? (
                  <div className="flex items-center gap-2">
                    <input
                      type="text" placeholder="Notes (optional)" value={notes}
                      onChange={e => setNotes(e.target.value)}
                      className="bg-navy-800 border border-navy-600 rounded px-2 py-1 text-xs text-white w-40 focus:outline-none focus:border-green-500"
                    />
                    <button onClick={() => { onResolve(alert.id, notes); setResolveForm(false) }}
                      className="text-xs bg-green-600/20 text-green-400 border border-green-600/30 px-2 py-1 rounded hover:bg-green-600/30">
                      Confirm
                    </button>
                    <button onClick={() => setResolveForm(false)} className="text-xs text-slate-500 hover:text-white">Cancel</button>
                  </div>
                ) : (
                  <button onClick={() => setResolveForm(true)}
                    className="flex items-center gap-1.5 text-xs bg-green-600/20 text-green-400 border border-green-600/30 px-3 py-1 rounded-lg hover:bg-green-600/30 transition-colors">
                    <CheckCircle size={12}/> Resolve
                  </button>
                )}
              </>
            ) : (
              <span className="flex items-center gap-1 text-xs text-green-400">
                <CheckCircle size={12}/> Resolved {alert.resolved_by ? `by ${alert.resolved_by}` : ''}
              </span>
            )}
            <button onClick={() => onDelete(alert.id)}
              className="text-slate-600 hover:text-red-400 transition-colors p-1">
              <Trash2 size={13}/>
            </button>
          </div>
        </div>
      </div>

      {/* Snapshot */}
      {alert.snapshot_path && (
        <div className="w-20 h-16 rounded-lg overflow-hidden flex-shrink-0 bg-navy-900 border border-navy-600">
          <img src={`/api/evidence/${alert.snapshot_path.split('/').pop()}`} alt="Evidence"
            className="w-full h-full object-cover" onError={e => { e.target.style.display='none' }}/>
        </div>
      )}
    </div>
  )
}

export default function AlertsPage() {
  const [alerts, setAlerts]   = useState([])
  const [total, setTotal]     = useState(0)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter]   = useState({ severity:'', type:'', resolved:'' })
  const [search, setSearch]   = useState('')
  const [page, setPage]       = useState(0)
  const LIMIT = 20
  const { alerts: wsAlerts, markAllRead } = useAlertStore()

  useEffect(() => { markAllRead(); load() }, [filter, search, page])

  useEffect(() => {
    if (wsAlerts.length > 0) {
      setAlerts(prev => {
        const ids = new Set(prev.map(a => a.id))
        const fresh = wsAlerts.filter(a => !ids.has(a.id)).map(a => ({...a, _live:true}))
        return [...fresh, ...prev]
      })
    }
  }, [wsAlerts])

  async function load() {
    setLoading(true)
    try {
      const p = new URLSearchParams({ limit: LIMIT, offset: page * LIMIT })
      if (filter.severity) p.set('severity', filter.severity)
      if (filter.type)     p.set('crime_type', filter.type)
      if (filter.resolved === 'open')     p.set('resolved', 'false')
      if (filter.resolved === 'resolved') p.set('resolved', 'true')
      if (search) p.set('search', search)
      const res = await fetch(`/api/alerts?${p}`)
      if (res.ok) {
        const d = await res.json()
        setAlerts(d.data || [])
        setTotal(d.total || 0)
      }
    } catch (_) {}
    setLoading(false)
  }

  async function resolveAlert(id, notes) {
    await fetch(`/api/alerts/${id}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes, resolved_by: 'Officer' }),
    })
    setAlerts(prev => prev.map(a => a.id === id ? { ...a, resolved: true, resolved_by: 'Officer' } : a))
  }

  async function deleteAlert(id) {
    if (!confirm('Delete this alert?')) return
    await fetch(`/api/alerts/${id}`, { method: 'DELETE' })
    setAlerts(prev => prev.filter(a => a.id !== id))
    setTotal(t => t - 1)
  }

  function exportCSV() {
    const rows = ['ID,Time,Type,Severity,Camera,Confidence,Persons,Resolved',
      ...alerts.map(a => `${a.id},${a.timestamp},${a.crime_type},${a.severity},${a.camera_id},${a.confidence},${a.person_count},${a.resolved}`)
    ].join('\n')
    const url = URL.createObjectURL(new Blob([rows], { type: 'text/csv' }))
    Object.assign(document.createElement('a'), { href: url, download: 'crimewatch_alerts.csv' }).click()
  }

  const unresolved = alerts.filter(a => !a.resolved).length
  const critical   = alerts.filter(a => a.severity === 'CRITICAL').length

  return (
    <div className="p-6 space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Bell size={22} className="text-yellow-400"/> Alert Center
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            {total} total · {critical} critical · {unresolved} unresolved
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} className="p-2 bg-navy-700 border border-navy-600 rounded-lg text-slate-400 hover:text-white transition-colors">
            <RefreshCw size={15}/>
          </button>
          <button onClick={exportCSV} className="flex items-center gap-2 bg-navy-700 border border-navy-600 text-slate-300 px-3 py-2 rounded-lg hover:bg-navy-600 transition-colors text-sm">
            <Download size={14}/> Export CSV
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="card flex flex-wrap gap-3 items-center">
        <Filter size={14} className="text-slate-400"/>
        <div className="relative">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500"/>
          <input type="text" placeholder="Search..." value={search} onChange={e => { setSearch(e.target.value); setPage(0) }}
            className="bg-navy-800 border border-navy-600 rounded-lg pl-8 pr-3 py-1.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 w-40"/>
        </div>
        {[
          { key:'severity', opts:['CRITICAL','HIGH','MEDIUM','LOW'],                                    label:'Severity' },
          { key:'type',     opts:['fight','weapon','accident','suspicious','riot','criminal','stolen_vehicle'], label:'Type' },
          { key:'resolved', opts:['open','resolved'],                                                   label:'Status' },
        ].map(({ key, opts, label }) => (
          <select key={key} value={filter[key]}
            onChange={e => { setFilter(p => ({...p,[key]:e.target.value})); setPage(0) }}
            className="bg-navy-800 border border-navy-600 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500">
            <option value="">{label}: All</option>
            {opts.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        ))}
        <span className="ml-auto text-xs text-slate-500">{total} results</span>
      </div>

      {/* List */}
      <div className="space-y-3">
        {loading ? (
          <div className="text-center py-12 text-slate-500">Loading alerts...</div>
        ) : alerts.length === 0 ? (
          <div className="text-center py-12 text-slate-500">
            <AlertTriangle size={32} className="mx-auto mb-3 opacity-30"/>
            No alerts match your filters
          </div>
        ) : (
          alerts.map(a => (
            <AlertCard key={a.id} alert={a} onResolve={resolveAlert} onDelete={deleteAlert}/>
          ))
        )}
      </div>

      {/* Pagination */}
      {total > LIMIT && (
        <div className="flex items-center justify-center gap-3">
          <button onClick={() => setPage(p => Math.max(0, p-1))} disabled={page === 0}
            className="px-4 py-2 bg-navy-700 border border-navy-600 rounded-lg text-sm text-slate-300 disabled:opacity-40 hover:bg-navy-600 transition-colors">
            ← Prev
          </button>
          <span className="text-sm text-slate-400">Page {page+1} of {Math.ceil(total/LIMIT)}</span>
          <button onClick={() => setPage(p => p+1)} disabled={(page+1)*LIMIT >= total}
            className="px-4 py-2 bg-navy-700 border border-navy-600 rounded-lg text-sm text-slate-300 disabled:opacity-40 hover:bg-navy-600 transition-colors">
            Next →
          </button>
        </div>
      )}
    </div>
  )
}
