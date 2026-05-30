import { useState, useEffect } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap } from 'react-leaflet'
import L from 'leaflet'
import { Map, Car, AlertTriangle, Layers } from 'lucide-react'

// Fix Leaflet default icon issue with Vite
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

// Custom icons
const vehicleIcon = L.divIcon({
  html: `<div style="background:#3b82f6;border:2px solid #1d4ed8;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:14px;box-shadow:0 0 8px rgba(59,130,246,0.6)">🚔</div>`,
  className: '',
  iconSize: [28, 28],
  iconAnchor: [14, 14],
})

const crimeIconMap = {
  fight:      { emoji: '🥊', color: '#ea580c' },
  weapon:     { emoji: '🔫', color: '#dc2626' },
  accident:   { emoji: '🚗', color: '#ca8a04' },
  suspicious: { emoji: '👁️', color: '#3b82f6' },
}

function CrimeMarker({ point }) {
  const info = crimeIconMap[point.type] || { emoji: '⚠️', color: '#6b7280' }
  const icon = L.divIcon({
    html: `<div style="background:${info.color}22;border:2px solid ${info.color};border-radius:50%;width:32px;height:32px;display:flex;align-items:center;justify-content:center;font-size:16px;animation:pulse 2s infinite">
      ${info.emoji}
    </div>`,
    className: '',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  })

  return (
    <Marker position={[point.lat, point.lng]} icon={icon}>
      <Popup className="dark-popup">
        <div style={{ background: '#1e293b', color: '#e2e8f0', padding: '8px', borderRadius: '8px', minWidth: '160px' }}>
          <div style={{ fontWeight: 'bold', textTransform: 'capitalize', marginBottom: '4px' }}>
            {info.emoji} {point.type}
          </div>
          <div style={{ fontSize: '12px', color: '#94a3b8' }}>
            Severity: <span style={{ color: info.color }}>{point.severity}</span>
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
            {point.lat.toFixed(4)}, {point.lng.toFixed(4)}
          </div>
        </div>
      </Popup>
    </Marker>
  )
}

function HeatmapLayer({ points }) {
  // Render circles as a simple heatmap approximation
  return points.map((point, i) => {
    const info = crimeIconMap[point.type] || { color: '#6b7280' }
    return (
      <Circle
        key={i}
        center={[point.lat, point.lng]}
        radius={300}
        pathOptions={{
          color: info.color,
          fillColor: info.color,
          fillOpacity: 0.15,
          weight: 1,
          opacity: 0.4,
        }}
      />
    )
  })
}

export default function MapView() {
  const [vehicles, setVehicles] = useState([])
  const [heatmapPoints, setHeatmapPoints] = useState([])
  const [showHeatmap, setShowHeatmap] = useState(true)
  const [showVehicles, setShowVehicles] = useState(true)
  const [showCrimes, setShowCrimes] = useState(true)
  const CENTER = [28.6139, 77.2090]   // New Delhi

  useEffect(() => {
    fetchHeatmap()
    const interval = setInterval(fetchVehicles, 3000)
    fetchVehicles()
    return () => clearInterval(interval)
  }, [])

  async function fetchVehicles() {
    try {
      const res = await fetch('/api/vehicles')
      setVehicles(await res.json())
    } catch (e) {}
  }

  async function fetchHeatmap() {
    try {
      const res = await fetch('/api/heatmap-data')
      setHeatmapPoints(await res.json())
    } catch (e) {}
  }

  return (
    <div className="p-6 space-y-4 animate-fade-in h-full">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Map size={22} className="text-blue-400" />
            Crime Map
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Live vehicle tracking · Crime heatmap · {heatmapPoints.length} incidents plotted
          </p>
        </div>

        {/* Layer toggles */}
        <div className="flex items-center gap-2">
          {[
            { label: 'Heatmap', state: showHeatmap, set: setShowHeatmap, color: 'text-orange-400' },
            { label: 'Vehicles', state: showVehicles, set: setShowVehicles, color: 'text-blue-400' },
            { label: 'Crimes', state: showCrimes, set: setShowCrimes, color: 'text-red-400' },
          ].map(({ label, state, set, color }) => (
            <button
              key={label}
              onClick={() => set(!state)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${
                state
                  ? `bg-navy-700 border-navy-500 ${color}`
                  : 'bg-navy-800 border-navy-700 text-slate-500'
              }`}
            >
              <Layers size={12} />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Map */}
      <div className="rounded-xl overflow-hidden border border-navy-600" style={{ height: 'calc(100vh - 220px)' }}>
        <MapContainer
          center={CENTER}
          zoom={13}
          style={{ height: '100%', width: '100%' }}
          zoomControl={true}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; OpenStreetMap contributors'
          />

          {/* Heatmap circles */}
          {showHeatmap && <HeatmapLayer points={heatmapPoints} />}

          {/* Crime markers */}
          {showCrimes && heatmapPoints.map((point, i) => (
            <CrimeMarker key={i} point={point} />
          ))}

          {/* Vehicle markers */}
          {showVehicles && vehicles.map(vehicle => (
            <Marker
              key={vehicle.id}
              position={[vehicle.lat, vehicle.lng]}
              icon={vehicleIcon}
            >
              <Popup>
                <div style={{ background: '#1e293b', color: '#e2e8f0', padding: '8px', borderRadius: '8px' }}>
                  <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>🚔 {vehicle.name}</div>
                  <div style={{ fontSize: '12px', color: '#94a3b8' }}>ID: {vehicle.id}</div>
                  <div style={{ fontSize: '12px', color: '#4ade80' }}>● {vehicle.status}</div>
                  <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
                    {vehicle.lat.toFixed(4)}, {vehicle.lng.toFixed(4)}
                  </div>
                  <div style={{ fontSize: '11px', color: '#64748b' }}>
                    {vehicle.camera_count} cameras mounted
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>

      {/* Legend */}
      <div className="card flex flex-wrap gap-4 items-center">
        <span className="text-xs text-slate-500 uppercase tracking-wider">Legend</span>
        {Object.entries(crimeIconMap).map(([type, { emoji, color }]) => (
          <div key={type} className="flex items-center gap-1.5 text-xs text-slate-400">
            <span>{emoji}</span>
            <span className="capitalize">{type}</span>
          </div>
        ))}
        <div className="flex items-center gap-1.5 text-xs text-slate-400">
          <span>🚔</span>
          <span>Patrol Vehicle</span>
        </div>
        <div className="ml-auto text-xs text-slate-500">
          Vehicles update every 3s
        </div>
      </div>
    </div>
  )
}
