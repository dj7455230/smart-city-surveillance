import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Camera, Bell, Map, BarChart3,
  Shield, Wifi, WifiOff, Menu, X, Brain, Lock, Car
} from 'lucide-react'
import Dashboard from './pages/Dashboard'
import LiveFeed from './pages/LiveFeed'
import AlertsPage from './pages/AlertsPage'
import MapView from './pages/MapView'
import Analytics from './pages/Analytics'
import PredictionMap from './pages/PredictionMap'
import EvidenceVault from './pages/EvidenceVault'
import VehicleTracker from './pages/VehicleTracker'
import { useAlertStore } from './store/alertStore'

const NAV_ITEMS = [
  { to: '/',           icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/live',       icon: Camera,          label: 'Live Feed' },
  { to: '/alerts',     icon: Bell,            label: 'Alerts',    badge: true },
  { to: '/vehicles',   icon: Car,             label: 'Vehicles' },
  { to: '/map',        icon: Map,             label: 'Crime Map' },
  { to: '/prediction', icon: Brain,           label: 'AI Predict' },
  { to: '/analytics',  icon: BarChart3,       label: 'Analytics' },
  { to: '/evidence',   icon: Lock,            label: 'Evidence' },
]

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const { unreadCount, wsConnected, connectAlertWS } = useAlertStore()

  useEffect(() => {
    connectAlertWS()
    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }, [])

  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden">
        {/* ── Sidebar ── */}
        <aside className={`flex flex-col bg-navy-800 border-r border-navy-600 transition-all duration-300 ${sidebarOpen ? 'w-60' : 'w-16'}`}>
          {/* Logo */}
          <div className="flex items-center gap-3 px-4 py-5 border-b border-navy-600">
            <div className="w-8 h-8 bg-red-600 rounded-lg flex items-center justify-center flex-shrink-0 shadow-lg shadow-red-900/50">
              <Shield size={18} className="text-white" />
            </div>
            {sidebarOpen && (
              <div>
                <div className="font-bold text-white text-sm leading-tight">CrimeWatch AI</div>
                <div className="text-xs text-slate-400">v2 · All Features</div>
              </div>
            )}
            <button onClick={() => setSidebarOpen(!sidebarOpen)} className="ml-auto text-slate-400 hover:text-white">
              {sidebarOpen ? <X size={16} /> : <Menu size={16} />}
            </button>
          </div>

          {/* Nav */}
          <nav className="flex-1 py-4 space-y-0.5 px-2 overflow-y-auto">
            {NAV_ITEMS.map(({ to, icon: Icon, label, badge }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) => `
                  flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all
                  ${isActive
                    ? 'bg-red-600/20 text-red-400 border border-red-600/30'
                    : 'text-slate-400 hover:text-white hover:bg-navy-700'
                  }
                `}
              >
                <Icon size={17} className="flex-shrink-0" />
                {sidebarOpen && (
                  <span className="text-sm font-medium flex-1">{label}</span>
                )}
                {sidebarOpen && badge && unreadCount > 0 && (
                  <span className="bg-red-600 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-bold">
                    {unreadCount > 9 ? '9+' : unreadCount}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>

          {/* Feature badges */}
          {sidebarOpen && (
            <div className="px-3 py-3 border-t border-navy-600 space-y-1">
              {[
                { label: 'Face Recognition', color: 'text-purple-400' },
                { label: 'ANPR / Plate Scan', color: 'text-orange-400' },
                { label: 'Audio Detection', color: 'text-cyan-400' },
                { label: 'Crime Prediction', color: 'text-green-400' },
              ].map(({ label, color }) => (
                <div key={label} className={`text-xs ${color} flex items-center gap-1.5`}>
                  <div className="w-1 h-1 rounded-full bg-current" />
                  {label}
                </div>
              ))}
            </div>
          )}

          {/* Connection status */}
          <div className="px-4 py-3 border-t border-navy-600">
            <div className="flex items-center gap-2">
              {wsConnected
                ? <Wifi size={14} className="text-green-400" />
                : <WifiOff size={14} className="text-red-400" />
              }
              {sidebarOpen && (
                <span className={`text-xs ${wsConnected ? 'text-green-400' : 'text-red-400'}`}>
                  {wsConnected ? 'System Online' : 'Reconnecting...'}
                </span>
              )}
            </div>
          </div>
        </aside>

        {/* ── Main content ── */}
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/"           element={<Dashboard />} />
            <Route path="/live"       element={<LiveFeed />} />
            <Route path="/alerts"     element={<AlertsPage />} />
            <Route path="/vehicles"   element={<VehicleTracker />} />
            <Route path="/map"        element={<MapView />} />
            <Route path="/prediction" element={<PredictionMap />} />
            <Route path="/analytics"  element={<Analytics />} />
            <Route path="/evidence"   element={<EvidenceVault />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
