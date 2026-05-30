import { useState, useEffect } from 'react'
import { AlertTriangle, Camera, Car, Shield, TrendingUp, Activity, Clock, CheckCircle, XCircle, Wifi } from 'lucide-react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { formatDistanceToNow } from 'date-fns'
import { useAlertStore } from '../store/alertStore'

const CRIME_COLORS = { fight:'#ea580c', weapon:'#dc2626', accident:'#ca8a04', suspicious:'#3b82f6', riot:'#dc2626', criminal:'#9333ea', stolen_vehicle:'#f97316', loitering:'#64748b' }
const TT = { contentStyle:{background:'#1e293b',border:'1px solid #334155',borderRadius:8}, labelStyle:{color:'#94a3b8'}, itemStyle:{color:'#e2e8f0'} }

function StatCard({ icon: Icon, label, value, sub, color='blue', pulse=false }) {
  const map = { red:'text-red-400 bg-red-600/10 border-red-600/20', orange:'text-orange-400 bg-orange-600/10 border-orange-600/20', green:'text-green-400 bg-green-600/10 border-green-600/20', blue:'text-blue-400 bg-blue-600/10 border-blue-600/20', purple:'text-purple-400 bg-purple-600/10 border-purple-600/20' }
  return (
    <div className={`card flex items-center gap-4 ${pulse ? 'alert-pulse' : ''}`}>
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center border ${map[color]}`}>
        <Icon size={22} />
      </div>
      <div>
        <div className="text-2xl font-bold text-white">{value ?? '—'}</div>
        <div className="text-sm text-slate-400">{label}</div>
        {sub && <div className="text-xs text-slate-500 mt-0.5">{sub}</div>}
      </div>
    </div>
  )
}

function SeverityBadge({ s }) {
  const m = { CRITICAL:'badge-critical', HIGH:'badge-high', MEDIUM:'badge-medium', LOW:'badge-low' }
  return <span className={m[s] || 'badge-low'}>{s}</span>
}

export default function Dashboard() {
  const [stats, setStats]   = useState(null)
  const [alerts, setAlerts] = useState([])
  const { alerts: wsAlerts, wsConnected } = useAlertStore()

  useEffect(() => {
    load()
    const t = setInterval(load, 10000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (wsAlerts.length > 0) {
      setAlerts(prev => {
        const ids = new Set(prev.map(a => a.id))
        const fresh = wsAlerts.filter(a => !ids.has(a.id)).map(a => ({ ...a, _live: true }))
        return [...fresh, ...prev].slice(0, 15)
      })
    }
  }, [wsAlerts])

  async function load() {
    try {
      const [sRes, aRes] = await Promise.all([
        fetch('/api/stats'),
        fetch('/api/alerts?limit=12'),
      ])
      if (sRes.ok) setStats(await sRes.json())
      if (aRes.ok) {
        const d = await aRes.json()
        setAlerts(d.data || [])
      }
    } catch (_) {}
  }

  const pieData = stats?.breakdown
    ? Object.entries(stats.breakdown).map(([name, value]) => ({ name, value }))
    : [{ name:'fight',value:8 },{ name:'weapon',value:4 },{ name:'accident',value:6 },{ name:'suspicious',value:7 }]

  const hourly = stats?.hourly_24h || Array.from({length:12},(_,i)=>({ hour:`${i*2}:00`, alerts:0 }))

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Command Center</h1>
          <p className="text-slate-400 text-sm mt-1">Real-time crime detection overview</p>
        </div>
        <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium ${wsConnected ? 'bg-green-600/10 border-green-600/20 text-green-400' : 'bg-red-600/10 border-red-600/20 text-red-400'}`}>
          <div className={wsConnected ? 'live-dot' : 'w-2 h-2 rounded-full bg-red-400'} />
          {wsConnected ? 'SYSTEM LIVE' : 'CONNECTING...'}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={AlertTriangle} label="Total Alerts"    color="red"    pulse={stats?.unresolved > 0} value={stats?.total_alerts}    sub={`${stats?.unresolved ?? 0} unresolved`} />
        <StatCard icon={Shield}        label="Critical Today"  color="orange" value={stats?.critical_alerts} sub="Immediate action needed" />
        <StatCard icon={Camera}        label="Active Cameras"  color="blue"   value={stats?.active_cameras}  sub="360° coverage" />
        <StatCard icon={Car}           label="Patrol Vehicles" color="green"  value={stats?.active_vehicles} sub="GPS tracked" />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card lg:col-span-2">
          <h2 className="font-semibold text-white mb-4 flex items-center gap-2 text-sm">
            <Activity size={15} className="text-blue-400" /> Alert Timeline (24h)
          </h2>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={hourly}>
              <defs>
                <linearGradient id="ag" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <XAxis dataKey="hour" tick={{fill:'#64748b',fontSize:10}} axisLine={false} tickLine={false} interval={3}/>
              <YAxis tick={{fill:'#64748b',fontSize:10}} axisLine={false} tickLine={false}/>
              <Tooltip {...TT}/>
              <Area type="monotone" dataKey="alerts" stroke="#3b82f6" fill="url(#ag)" strokeWidth={2} name="Alerts"/>
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h2 className="font-semibold text-white mb-4 flex items-center gap-2 text-sm">
            <TrendingUp size={15} className="text-purple-400" /> Crime Breakdown
          </h2>
          <ResponsiveContainer width="100%" height={160}>
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" innerRadius={40} outerRadius={65} paddingAngle={3} dataKey="value">
                {pieData.map((e,i) => <Cell key={i} fill={CRIME_COLORS[e.name] || '#6b7280'}/>)}
              </Pie>
              <Tooltip {...TT}/>
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1.5 mt-2">
            {pieData.map(e => (
              <div key={e.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full" style={{background: CRIME_COLORS[e.name] || '#6b7280'}}/>
                  <span className="text-slate-400 capitalize">{e.name.replace('_',' ')}</span>
                </div>
                <span className="text-white font-medium">{e.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent alerts */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-white flex items-center gap-2 text-sm">
            <Clock size={15} className="text-yellow-400" /> Recent Alerts
          </h2>
          <a href="/alerts" className="text-xs text-blue-400 hover:text-blue-300">View all →</a>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-500 text-xs border-b border-navy-600">
                {['Time','Type','Severity','Camera','Confidence','Status'].map(h => (
                  <th key={h} className="text-left pb-2 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-navy-600">
              {alerts.slice(0,10).map((a,i) => (
                <tr key={a.id || i} className={`hover:bg-navy-600/30 transition-colors ${a._live ? 'bg-blue-900/10' : ''}`}>
                  <td className="py-2.5 text-slate-400 text-xs">
                    {a.timestamp ? formatDistanceToNow(new Date(a.timestamp), {addSuffix:true}) : '—'}
                  </td>
                  <td className="py-2.5 font-medium text-white capitalize">{a.crime_type?.replace('_',' ')}</td>
                  <td className="py-2.5"><SeverityBadge s={a.severity}/></td>
                  <td className="py-2.5 text-slate-400 text-xs">{a.camera_id}</td>
                  <td className="py-2.5">
                    <div className="flex items-center gap-2">
                      <div className="w-14 bg-navy-600 rounded-full h-1.5">
                        <div className="h-1.5 rounded-full bg-blue-500" style={{width:`${(a.confidence||0)*100}%`}}/>
                      </div>
                      <span className="text-xs text-slate-400">{((a.confidence||0)*100).toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className="py-2.5">
                    {a.resolved
                      ? <CheckCircle size={14} className="text-green-400"/>
                      : <XCircle    size={14} className="text-red-400"/>}
                  </td>
                </tr>
              ))}
              {alerts.length === 0 && (
                <tr><td colSpan={6} className="py-8 text-center text-slate-500">No alerts yet. System is monitoring...</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
