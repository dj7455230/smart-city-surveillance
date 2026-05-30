import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, RadarChart, Radar,
  PolarGrid, PolarAngleAxis, Legend
} from 'recharts'
import { BarChart3, TrendingUp, Clock, Target } from 'lucide-react'

const COLORS = ['#dc2626', '#ea580c', '#ca8a04', '#3b82f6', '#8b5cf6']

const TOOLTIP_STYLE = {
  contentStyle: { background: '#1e293b', border: '1px solid #334155', borderRadius: 8 },
  labelStyle: { color: '#94a3b8' },
  itemStyle: { color: '#e2e8f0' },
}

function ChartCard({ title, icon: Icon, children, className = '' }) {
  return (
    <div className={`card ${className}`}>
      <h3 className="font-semibold text-white mb-4 flex items-center gap-2 text-sm">
        <Icon size={15} className="text-blue-400" />
        {title}
      </h3>
      {children}
    </div>
  )
}

export default function Analytics() {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    fetch('/api/stats').then(r => r.json()).then(setStats).catch(() => {})
  }, [])

  // Generate demo chart data
  const hourlyData = Array.from({ length: 24 }, (_, h) => ({
    hour: `${h}:00`,
    alerts: Math.floor(Math.random() * 12 + (h >= 20 || h <= 4 ? 8 : 2)),
    resolved: Math.floor(Math.random() * 8),
  }))

  const weeklyData = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(day => ({
    day,
    fight: Math.floor(Math.random() * 10),
    weapon: Math.floor(Math.random() * 5),
    accident: Math.floor(Math.random() * 8),
    suspicious: Math.floor(Math.random() * 12),
  }))

  const responseTimeData = [
    { name: 'CRITICAL', avg: 2.3, target: 2 },
    { name: 'HIGH',     avg: 4.1, target: 5 },
    { name: 'MEDIUM',   avg: 8.7, target: 10 },
    { name: 'LOW',      avg: 15.2, target: 20 },
  ]

  const radarData = [
    { subject: 'Detection Rate', A: 94 },
    { subject: 'Response Time', A: 87 },
    { subject: 'False Positive', A: 91 },
    { subject: 'Coverage', A: 78 },
    { subject: 'Uptime', A: 99 },
    { subject: 'Accuracy', A: 89 },
  ]

  const pieData = stats?.breakdown
    ? Object.entries(stats.breakdown).map(([name, value]) => ({ name, value }))
    : [
        { name: 'Fight', value: 35 },
        { name: 'Weapon', value: 18 },
        { name: 'Accident', value: 27 },
        { name: 'Suspicious', value: 20 },
      ]

  const kpis = [
    { label: 'Detection Accuracy', value: '94.2%', trend: '+2.1%', up: true },
    { label: 'Avg Response Time', value: '3.8 min', trend: '-0.5 min', up: true },
    { label: 'False Positive Rate', value: '5.8%', trend: '-1.2%', up: true },
    { label: 'System Uptime', value: '99.7%', trend: '+0.1%', up: true },
  ]

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <BarChart3 size={22} className="text-purple-400" />
          Analytics
        </h1>
        <p className="text-slate-400 text-sm mt-1">Performance metrics and crime pattern analysis</p>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map(({ label, value, trend, up }) => (
          <div key={label} className="card text-center">
            <div className="text-2xl font-bold text-white">{value}</div>
            <div className="text-xs text-slate-400 mt-1">{label}</div>
            <div className={`text-xs mt-1 font-medium ${up ? 'text-green-400' : 'text-red-400'}`}>
              {trend}
            </div>
          </div>
        ))}
      </div>

      {/* Charts grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 24h alert volume */}
        <ChartCard title="24-Hour Alert Volume" icon={Clock} className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={hourlyData}>
              <XAxis dataKey="hour" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false}
                interval={3} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Bar dataKey="alerts" fill="#3b82f6" radius={[3, 3, 0, 0]} name="Alerts" />
              <Bar dataKey="resolved" fill="#16a34a" radius={[3, 3, 0, 0]} name="Resolved" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Weekly crime type breakdown */}
        <ChartCard title="Weekly Crime Type Breakdown" icon={TrendingUp}>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={weeklyData}>
              <XAxis dataKey="day" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
              <Bar dataKey="fight"      fill="#ea580c" radius={[2, 2, 0, 0]} stackId="a" />
              <Bar dataKey="weapon"     fill="#dc2626" radius={[2, 2, 0, 0]} stackId="a" />
              <Bar dataKey="accident"   fill="#ca8a04" radius={[2, 2, 0, 0]} stackId="a" />
              <Bar dataKey="suspicious" fill="#3b82f6" radius={[2, 2, 0, 0]} stackId="a" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Crime distribution pie */}
        <ChartCard title="Crime Distribution" icon={Target}>
          <div className="flex items-center gap-4">
            <ResponsiveContainer width="60%" height={200}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" outerRadius={80} dataKey="value" paddingAngle={3}>
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip {...TOOLTIP_STYLE} />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-2">
              {pieData.map((entry, i) => (
                <div key={entry.name} className="flex items-center gap-2 text-xs">
                  <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: COLORS[i % COLORS.length] }} />
                  <span className="text-slate-400 capitalize">{entry.name}</span>
                  <span className="text-white font-medium ml-auto">{entry.value}</span>
                </div>
              ))}
            </div>
          </div>
        </ChartCard>
      </div>

      {/* System performance radar + response time */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="System Performance Radar" icon={BarChart3}>
          <ResponsiveContainer width="100%" height={240}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#334155" />
              <PolarAngleAxis dataKey="subject" tick={{ fill: '#64748b', fontSize: 10 }} />
              <Radar name="Score" dataKey="A" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} />
              <Tooltip {...TOOLTIP_STYLE} />
            </RadarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Response Time by Severity (min)" icon={Clock}>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={responseTimeData} layout="vertical">
              <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis dataKey="name" type="category" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} width={60} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Bar dataKey="avg" fill="#3b82f6" radius={[0, 4, 4, 0]} name="Actual" />
              <Bar dataKey="target" fill="#334155" radius={[0, 4, 4, 0]} name="Target" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  )
}
