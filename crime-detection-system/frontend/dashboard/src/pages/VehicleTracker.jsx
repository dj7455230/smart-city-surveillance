import { useState, useEffect, useRef } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet'
import L from 'leaflet'
import { Camera, MapPin, Clock, AlertTriangle, Radio, ChevronLeft, Activity, Wifi } from 'lucide-react'

// Fix leaflet icons
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl:       'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl:     'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

// ── Vehicle icons ─────────────────────────────────────────────────────────────
function makeVehicleIcon(color, isSelected) {
  const size = isSelected ? 44 : 34
  return L.divIcon({
    html: `
      <div style="
        width:${size}px; height:${size}px;
        background:${color};
        border: ${isSelected ? '3px solid #fff' : '2px solid rgba(255,255,255,0.5)'};
        border-radius:50%;
        display:flex; align-items:center; justify-content:center;
        font-size:${isSelected ? 20 : 16}px;
        box-shadow: 0 0 ${isSelected ? 16 : 8}px ${color}99;
        cursor:pointer;
        transition: all 0.3s;
      ">🚔</div>`,
    className: '',
    iconSize:   [size, size],
    iconAnchor: [size/2, size/2],
  })
}

function makeAlertIcon(type) {
  const colors = { weapon:'#dc2626', fight:'#ea580c', accident:'#ca8a04', suspicious:'#3b82f6', riot:'#dc2626' }
  const emojis = { weapon:'🔫', fight:'🥊', accident:'🚗', suspicious:'👁️', riot:'🚨' }
  const c = colors[type] || '#6b7280'
  return L.divIcon({
    html: `<div style="background:${c}22;border:2px solid ${c};border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:14px;">${emojis[type]||'⚠️'}</div>`,
    className: '',
    iconSize:   [28, 28],
    iconAnchor: [14, 14],
  })
}

// Vehicle colors
const V_COLORS = ['#3b82f6','#10b981','#f59e0b','#8b5cf6']

// ── Map auto-center on selected vehicle ───────────────────────────────────────
function MapController({ center }) {
  const map = useMap()
  useEffect(() => {
    if (center) map.flyTo(center, 14, { duration: 1.2 })
  }, [center])
  return null
}

// ── Fake camera frame generator ───────────────────────────────────────────────
function CameraFeed({ vehicle, wsRef }) {
  const [frame, setFrame]         = useState(null)
  const [detection, setDetection] = useState(null)
  const [connected, setConnected] = useState(false)
  const localWs = useRef(null)

  useEffect(() => {
    if (!vehicle) return
    localWs.current?.close()
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${location.host}/ws/camera/${vehicle.id}-CAM01`)
    localWs.current = ws
    ws.onopen  = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onmessage = e => {
      const d = JSON.parse(e.data)
      if (d.type === 'frame') {
        setFrame(`data:image/jpeg;base64,${d.frame}`)
        setDetection(d.detection)
      }
    }
    return () => ws.close()
  }, [vehicle?.id])

  if (!vehicle) return (
    <div className="flex-1 flex items-center justify-center bg-[#0a0f1e] rounded-lg border border-[#1e293b]">
      <div className="text-center text-slate-600">
        <Camera size={32} className="mx-auto mb-2"/>
        <div className="text-sm">Select a vehicle</div>
      </div>
    </div>
  )

  return (
    <div className="relative bg-black rounded-lg overflow-hidden border border-[#1e293b]" style={{aspectRatio:'16/10'}}>
      {/* Frame */}
      {frame
        ? <img src={frame} alt="feed" className="w-full h-full object-cover"/>
        : (
          <div className="w-full h-full flex items-center justify-center bg-[#050a14]">
            <div className="text-center">
              <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"/>
              <div className="text-xs text-slate-500">Connecting to {vehicle.id}...</div>
            </div>
          </div>
        )
      }

      {/* Top bar */}
      <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-2 py-1.5 bg-gradient-to-b from-black/80 to-transparent">
        <div className="flex items-center gap-1.5">
          <div className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-red-500 animate-pulse' : 'bg-slate-600'}`}/>
          <span className="text-white text-xs font-bold tracking-wider">● LIVE</span>
        </div>
        <div className="text-xs text-slate-300 font-mono">
          {new Date().toLocaleDateString('en-IN')} {new Date().toLocaleTimeString('en-IN', {hour12:false})}
        </div>
        <div className="text-xs text-slate-400">CAM1 · 15 FPS</div>
      </div>

      {/* Alert overlay */}
      {detection?.is_alert && (
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-red-900/90 to-transparent px-3 py-2">
          <div className="flex items-center gap-2">
            <AlertTriangle size={13} className="text-red-400"/>
            <span className="text-red-300 text-xs font-bold uppercase tracking-wide">
              {detection.crime_type?.replace('_',' ')} — {detection.severity}
            </span>
            <span className="ml-auto text-red-400 text-xs">{(detection.confidence*100).toFixed(0)}%</span>
          </div>
        </div>
      )}

      {/* Vehicle ID watermark */}
      <div className="absolute bottom-2 left-2 text-xs text-slate-500 font-mono">
        {vehicle.id}
      </div>
    </div>
  )
}

// ── Recent log item ───────────────────────────────────────────────────────────
function LogItem({ log, onClick }) {
  const sev = { CRITICAL:'text-red-400 bg-red-900/30', HIGH:'text-orange-400 bg-orange-900/30',
                MEDIUM:'text-yellow-400 bg-yellow-900/30', LOW:'text-green-400 bg-green-900/30' }
  return (
    <div onClick={onClick}
      className="flex items-center justify-between px-3 py-2 rounded-lg bg-[#0d1424] border border-[#1e293b] hover:border-cyan-800 cursor-pointer transition-all group">
      <div className="flex-1 min-w-0">
        <div className="text-xs text-slate-300 font-medium truncate capitalize">
          {log.crime_type?.replace('_',' ')}
        </div>
        <div className="text-xs text-slate-600 mt-0.5">
          {log.timestamp ? new Date(log.timestamp).toLocaleTimeString('en-IN', {hour:'2-digit',minute:'2-digit',hour12:true}) : '—'}
          {log.camera_id ? ` — ${log.camera_id}` : ''}
        </div>
      </div>
      <button className="text-xs bg-cyan-900/40 text-cyan-400 border border-cyan-800/50 px-2 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity ml-2 flex-shrink-0">
        ▶ Play
      </button>
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function VehicleTracker() {
  const [vehicles, setVehicles]       = useState([])
  const [selected, setSelected]       = useState(null)
  const [alerts, setAlerts]           = useState([])
  const [heatmap, setHeatmap]         = useState([])
  const [trails, setTrails]           = useState({})   // vehicle_id → [positions]
  const [mapCenter, setMapCenter]     = useState(null)
  const [showPanel, setShowPanel]     = useState(true)
  const intervalRef = useRef(null)

  // Load initial data
  useEffect(() => {
    loadAlerts()
    loadHeatmap()
    loadVehicles()
    intervalRef.current = setInterval(loadVehicles, 3000)
    return () => clearInterval(intervalRef.current)
  }, [])

  // Auto-select first vehicle
  useEffect(() => {
    if (vehicles.length > 0 && !selected) {
      setSelected(vehicles[0])
      setMapCenter([vehicles[0].lat, vehicles[0].lng])
    }
  }, [vehicles])

  async function loadVehicles() {
    try {
      const r = await fetch('/api/vehicles')
      if (!r.ok) return
      const data = await r.json()
      setVehicles(data)
      // Update trails
      setTrails(prev => {
        const next = { ...prev }
        data.forEach(v => {
          const hist = next[v.id] || []
          const last = hist[hist.length - 1]
          if (!last || last[0] !== v.lat || last[1] !== v.lng) {
            next[v.id] = [...hist, [v.lat, v.lng]].slice(-40)
          }
        })
        return next
      })
    } catch (_) {}
  }

  async function loadAlerts() {
    try {
      const r = await fetch('/api/alerts?limit=30')
      if (r.ok) {
        const d = await r.json()
        setAlerts(d.data || [])
      }
    } catch (_) {}
  }

  async function loadHeatmap() {
    try {
      const r = await fetch('/api/heatmap-data')
      if (r.ok) setHeatmap(await r.json())
    } catch (_) {}
  }

  function selectVehicle(v) {
    setSelected(v)
    setMapCenter([v.lat, v.lng])
  }

  const selectedAlerts = alerts.filter(a => !selected || a.vehicle_id === selected?.id).slice(0, 8)

  return (
    <div className="flex h-full bg-[#060b18] text-white overflow-hidden">

      {/* ── LEFT PANEL ─────────────────────────────────────────────────────── */}
      {showPanel && (
        <div className="w-72 flex-shrink-0 flex flex-col border-r border-[#1a2540] bg-[#080d1a]">

          {/* Header */}
          <div className="px-4 py-3 border-b border-[#1a2540] flex items-center justify-between">
            <div>
              <div className="text-sm font-bold text-cyan-400 tracking-widest">CSD</div>
              <div className="text-xs text-slate-500">Surveillance</div>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-green-400">
              <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse"/>
              LIVE
            </div>
          </div>

          {/* Camera feed */}
          <div className="p-3">
            <CameraFeed vehicle={selected}/>
          </div>

          {/* Back / vehicle selector */}
          <div className="px-3 pb-2">
            <button
              onClick={() => setSelected(null)}
              className="flex items-center gap-1 text-xs text-slate-500 hover:text-cyan-400 transition-colors mb-2">
              <ChevronLeft size={13}/> Back to list
            </button>

            {/* Selected vehicle info */}
            {selected ? (
              <div className="bg-[#0d1a2e] border border-cyan-900/50 rounded-lg p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-bold text-cyan-400 text-sm tracking-wider">{selected.id}</span>
                  <span className={`text-xs px-2 py-0.5 rounded font-semibold ${
                    selected.status === 'active' ? 'bg-green-900/40 text-green-400' : 'bg-red-900/40 text-red-400'
                  }`}>{selected.status?.toUpperCase()}</span>
                </div>
                <div className="text-xs text-slate-400 mb-1">{selected.name}</div>
                {selected.officer && <div className="text-xs text-slate-500">👮 {selected.officer}</div>}
                <div className="flex items-center gap-1 text-xs text-slate-500 mt-1">
                  <MapPin size={10} className="text-cyan-500"/>
                  {selected.lat?.toFixed(4)}, {selected.lng?.toFixed(4)}
                </div>
                <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
                  <span>📷 {selected.camera_count} cams</span>
                  <span>🚀 {selected.speed_kmh} km/h</span>
                </div>
              </div>
            ) : (
              /* Vehicle list */
              <div className="space-y-2">
                <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Active Vehicles</div>
                {vehicles.map((v, i) => (
                  <button key={v.id} onClick={() => selectVehicle(v)}
                    className="w-full text-left bg-[#0d1a2e] hover:bg-[#112035] border border-[#1e3050] hover:border-cyan-800 rounded-lg p-2.5 transition-all">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full flex items-center justify-center text-sm flex-shrink-0"
                        style={{background: V_COLORS[i % V_COLORS.length] + '33', border: `1.5px solid ${V_COLORS[i % V_COLORS.length]}`}}>
                        🚔
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-bold" style={{color: V_COLORS[i % V_COLORS.length]}}>{v.id}</div>
                        <div className="text-xs text-slate-500 truncate">{v.name}</div>
                      </div>
                      <div className="w-1.5 h-1.5 rounded-full bg-green-400 flex-shrink-0"/>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Recent logs */}
          <div className="flex-1 overflow-hidden flex flex-col px-3 pb-3">
            <div className="text-xs text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-2">
              <Activity size={11}/> Recent Logs
            </div>
            <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
              {selectedAlerts.length === 0 ? (
                <div className="text-xs text-slate-600 text-center py-4">No recent activity</div>
              ) : (
                selectedAlerts.map(a => (
                  <LogItem key={a.id} log={a} onClick={() => {
                    if (a.latitude) setMapCenter([a.latitude, a.longitude])
                  }}/>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── MAP ────────────────────────────────────────────────────────────── */}
      <div className="flex-1 relative">

        {/* Toggle panel button */}
        <button onClick={() => setShowPanel(!showPanel)}
          className="absolute top-3 left-3 z-[1000] bg-[#080d1a]/90 border border-[#1a2540] text-cyan-400 p-2 rounded-lg hover:bg-[#0d1424] transition-colors">
          <ChevronLeft size={16} className={`transition-transform ${showPanel ? '' : 'rotate-180'}`}/>
        </button>

        {/* Stats overlay */}
        <div className="absolute top-3 right-3 z-[1000] flex flex-col gap-2">
          <div className="bg-[#080d1a]/90 border border-[#1a2540] rounded-lg px-3 py-2 text-xs">
            <div className="text-slate-500 mb-1">Active Units</div>
            <div className="text-cyan-400 font-bold text-lg">{vehicles.length}</div>
          </div>
          <div className="bg-[#080d1a]/90 border border-[#1a2540] rounded-lg px-3 py-2 text-xs">
            <div className="text-slate-500 mb-1">Incidents</div>
            <div className="text-red-400 font-bold text-lg">{heatmap.length}</div>
          </div>
          <div className="bg-[#080d1a]/90 border border-[#1a2540] rounded-lg px-3 py-2 text-xs">
            <div className="text-slate-500 mb-1">GPS Update</div>
            <div className="text-green-400 font-bold flex items-center gap-1">
              <Wifi size={11}/> 3s
            </div>
          </div>
        </div>

        {/* Vehicle list overlay (bottom) */}
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-[1000] flex gap-2">
          {vehicles.map((v, i) => (
            <button key={v.id} onClick={() => selectVehicle(v)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-medium transition-all ${
                selected?.id === v.id
                  ? 'border-cyan-500 bg-cyan-900/40 text-cyan-300'
                  : 'border-[#1a2540] bg-[#080d1a]/90 text-slate-400 hover:border-cyan-800'
              }`}>
              <div className="w-2 h-2 rounded-full" style={{background: V_COLORS[i % V_COLORS.length]}}/>
              {v.id}
              <span className="text-slate-600">{v.speed_kmh} km/h</span>
            </button>
          ))}
        </div>

        <MapContainer
          center={[28.6139, 77.2090]}
          zoom={13}
          style={{ height: '100%', width: '100%' }}
          zoomControl={false}
        >
          {/* Dark satellite-style tile */}
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          />

          <MapController center={mapCenter}/>

          {/* Vehicle trails */}
          {vehicles.map((v, i) => {
            const trail = trails[v.id] || []
            if (trail.length < 2) return null
            return (
              <Polyline
                key={`trail-${v.id}`}
                positions={trail}
                pathOptions={{
                  color: V_COLORS[i % V_COLORS.length],
                  weight: 2.5,
                  opacity: 0.6,
                  dashArray: '6 4',
                }}
              />
            )
          })}

          {/* Vehicle markers */}
          {vehicles.map((v, i) => (
            <Marker
              key={v.id}
              position={[v.lat, v.lng]}
              icon={makeVehicleIcon(V_COLORS[i % V_COLORS.length], selected?.id === v.id)}
              eventHandlers={{ click: () => selectVehicle(v) }}
            >
              <Popup>
                <div style={{background:'#0d1424',color:'#e2e8f0',padding:'10px',borderRadius:'8px',minWidth:'160px',border:'1px solid #1e3050'}}>
                  <div style={{fontWeight:'bold',color: V_COLORS[i % V_COLORS.length],marginBottom:'6px',fontSize:'14px'}}>
                    🚔 {v.id}
                  </div>
                  <div style={{fontSize:'12px',color:'#94a3b8'}}>{v.name}</div>
                  {v.officer && <div style={{fontSize:'12px',color:'#94a3b8'}}>👮 {v.officer}</div>}
                  <div style={{fontSize:'11px',color:'#64748b',marginTop:'4px'}}>
                    📍 {v.lat?.toFixed(5)}, {v.lng?.toFixed(5)}
                  </div>
                  <div style={{fontSize:'11px',color:'#64748b'}}>
                    🚀 {v.speed_kmh} km/h · 📷 {v.camera_count} cameras
                  </div>
                  <div style={{marginTop:'6px',padding:'4px 8px',background:'#16a34a22',border:'1px solid #16a34a44',borderRadius:'4px',fontSize:'11px',color:'#4ade80',textAlign:'center'}}>
                    ● ACTIVE
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}

          {/* Crime incident markers */}
          {heatmap.map((p, i) => (
            <Marker
              key={`inc-${i}`}
              position={[p.lat, p.lng]}
              icon={makeAlertIcon(p.type)}
            >
              <Popup>
                <div style={{background:'#0d1424',color:'#e2e8f0',padding:'8px',borderRadius:'8px',border:'1px solid #1e3050'}}>
                  <div style={{fontWeight:'bold',textTransform:'capitalize',marginBottom:'4px'}}>
                    {p.type?.replace('_',' ')}
                  </div>
                  <div style={{fontSize:'11px',color:'#94a3b8'}}>Severity: {p.severity}</div>
                  <div style={{fontSize:'11px',color:'#64748b'}}>{p.lat?.toFixed(4)}, {p.lng?.toFixed(4)}</div>
                  {p.timestamp && (
                    <div style={{fontSize:'11px',color:'#64748b'}}>
                      {new Date(p.timestamp).toLocaleString('en-IN')}
                    </div>
                  )}
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  )
}
