import { useState, useEffect } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap } from 'react-leaflet'
import L from 'leaflet'
import { Brain, TrendingUp, Navigation, Clock, AlertTriangle } from 'lucide-react'

delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

const RISK_COLORS = {
  CRITICAL: '#dc2626',
  HIGH:     '#ea580c',
  MEDIUM:   '#ca8a04',
  LOW:      '#16a34a',
}

function PredictionLayer({ points }) {
  return points.map((p, i) => (
    <Circle
      key={i}
      center={[p.lat, p.lng]}
      radius={400}
      pathOptions={{
        color: RISK_COLORS[p.risk_level] || '#6b7280',
        fillColor: RISK_COLORS[p.risk_level] || '#6b7280',
        fillOpacity: Math.max(0.05, p.risk * 0.5),
        weight: p.risk > 0.6 ? 2 : 1,
        opacity: p.risk > 0.3 ? 0.6 : 0.2,
      }}
    >
      <Popup>
        <div style={{ background: '#1e293b', color: '#e2e8f0', padding: '8px', borderRadius: '8px', minWidth: '160px' }}>
          <div style={{ fontWeight: 'bold', color: RISK_COLORS[p.risk_level] }}>{p.risk_level} RISK</div>
          <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>
            Probability: {(p.risk * 100).toFixed(0)}%
          </div>
          <div style={{ fontSize: '12px', color: '#94a3b8' }}>
            Top crime: <span style={{ textTransform: 'capitalize' }}>{p.top_crime}</span>
          </div>
        </div>
      </Popup>
    </Circle>
  ))
}

export default function PredictionMap() {
  const [predPoints, setPredPoints] = useState([])
  const [patrolRoutes, setPatrolRoutes] = useState([])
  const [prediction, setPrediction] = useState(null)
  const [loading, setLoading] = useState(true)
  const [clickedPos, setClickedPos] = useState(null)
  const CENTER = [28.6139, 77.2090]

  useEffect(() => {
    fetchHeatmap()
    fetchPatrolRoutes()
  }, [])

  async function fetchHeatmap() {
    setLoading(true)
    try {
      const res = await fetch('/api/predict/heatmap?grid_size=8')
      setPredPoints(await res.json())
    } catch (e) {}
    setLoading(false)
  }

  async function fetchPatrolRoutes() {
    try {
      const res = await fetch('/api/predict/patrol-routes')
      setPatrolRoutes(await res.json())
    } catch (e) {}
  }

  async function predictPoint(lat, lng) {
    try {
      const res = await fetch(`/api/predict?lat=${lat}&lng=${lng}`)
      setPrediction(await res.json())
      setClickedPos({ lat, lng })
    } catch (e) {}
  }

  const highRiskCount = predPoints.filter(p => p.risk > 0.5).length
  const criticalCount = predPoints.filter(p => p.risk_level === 'CRITICAL').length

  return (
    <div className="p-6 space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Brain size={22} className="text-purple-400" />
            Crime Prediction AI
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            ML-powered crime probability map · {predPoints.length} zones analyzed
          </p>
        </div>
        <button
          onClick={fetchHeatmap}
          className="flex items-center gap-2 bg-purple-600/20 border border-purple-600/30 text-purple-400 px-3 py-2 rounded-lg hover:bg-purple-600/30 transition-colors text-sm"
        >
          <Brain size={14} />
          Refresh Prediction
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Zones Analyzed', value: predPoints.length, color: 'text-blue-400' },
          { label: 'High Risk Zones', value: highRiskCount, color: 'text-orange-400' },
          { label: 'Critical Zones', value: criticalCount, color: 'text-red-400' },
          { label: 'Patrol Routes', value: patrolRoutes.length, color: 'text-green-400' },
        ].map(({ label, value, color }) => (
          <div key={label} className="card text-center">
            <div className={`text-2xl font-bold ${color}`}>{value}</div>
            <div className="text-xs text-slate-400 mt-1">{label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Map */}
        <div className="lg:col-span-2 rounded-xl overflow-hidden border border-navy-600" style={{ height: '500px' }}>
          {loading ? (
            <div className="h-full flex items-center justify-center bg-navy-900 text-slate-500">
              <Brain size={32} className="animate-pulse mr-3" />
              Running prediction model...
            </div>
          ) : (
            <MapContainer center={CENTER} zoom={13} style={{ height: '100%', width: '100%' }}>
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              <PredictionLayer points={predPoints} />
              {clickedPos && (
                <Marker position={[clickedPos.lat, clickedPos.lng]}>
                  <Popup>
                    <div style={{ background: '#1e293b', color: '#e2e8f0', padding: '8px', borderRadius: '8px' }}>
                      <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>📍 Prediction Point</div>
                      {prediction && (
                        <>
                          <div style={{ fontSize: '12px', color: RISK_COLORS[prediction.risk_level] }}>
                            Risk: {(prediction.overall_risk * 100).toFixed(0)}% — {prediction.risk_level}
                          </div>
                          <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>
                            {prediction.recommendation}
                          </div>
                        </>
                      )}
                    </div>
                  </Popup>
                </Marker>
              )}
            </MapContainer>
          )}
        </div>

        {/* Patrol recommendations */}
        <div className="space-y-3">
          <div className="card">
            <h3 className="font-semibold text-white mb-3 flex items-center gap-2 text-sm">
              <Navigation size={14} className="text-green-400" />
              AI Patrol Routes
            </h3>
            <div className="space-y-3">
              {patrolRoutes.map((route, i) => (
                <div key={i} className="bg-navy-800 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-white text-sm font-medium">🚔 {route.vehicle_name}</span>
                    <span className={`text-xs font-semibold ${
                      route.priority === 'CRITICAL' ? 'text-red-400' :
                      route.priority === 'HIGH' ? 'text-orange-400' : 'text-yellow-400'
                    }`}>{route.priority}</span>
                  </div>
                  <p className="text-xs text-slate-400">{route.instruction}</p>
                </div>
              ))}
              {patrolRoutes.length === 0 && (
                <div className="text-slate-500 text-xs text-center py-4">Loading routes...</div>
              )}
            </div>
          </div>

          {/* Quick predict */}
          <div className="card">
            <h3 className="font-semibold text-white mb-3 flex items-center gap-2 text-sm">
              <Clock size={14} className="text-blue-400" />
              Quick Predict
            </h3>
            <div className="space-y-2">
              {[
                { label: 'Current Location', lat: 28.6139, lng: 77.2090 },
                { label: 'North Zone', lat: 28.6300, lng: 77.2090 },
                { label: 'South Zone', lat: 28.5900, lng: 77.2090 },
                { label: 'East Zone', lat: 28.6139, lng: 77.2400 },
              ].map(({ label, lat, lng }) => (
                <button
                  key={label}
                  onClick={() => predictPoint(lat, lng)}
                  className="w-full text-left bg-navy-800 hover:bg-navy-700 rounded-lg px-3 py-2 text-xs text-slate-300 transition-colors"
                >
                  📍 {label}
                </button>
              ))}
            </div>
            {prediction && (
              <div className="mt-3 p-3 bg-navy-800 rounded-lg">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-slate-400">Risk Score</span>
                  <span className={`text-sm font-bold ${
                    prediction.risk_level === 'CRITICAL' ? 'text-red-400' :
                    prediction.risk_level === 'HIGH' ? 'text-orange-400' :
                    prediction.risk_level === 'MEDIUM' ? 'text-yellow-400' : 'text-green-400'
                  }`}>{(prediction.overall_risk * 100).toFixed(0)}%</span>
                </div>
                <div className="w-full bg-navy-600 rounded-full h-1.5 mb-2">
                  <div
                    className="h-1.5 rounded-full bg-gradient-to-r from-green-500 via-yellow-500 to-red-500"
                    style={{ width: `${prediction.overall_risk * 100}%` }}
                  />
                </div>
                <p className="text-xs text-slate-400">{prediction.recommendation}</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Risk legend */}
      <div className="card flex flex-wrap gap-4 items-center">
        <span className="text-xs text-slate-500 uppercase tracking-wider">Risk Legend</span>
        {Object.entries(RISK_COLORS).map(([level, color]) => (
          <div key={level} className="flex items-center gap-2 text-xs">
            <div className="w-3 h-3 rounded-full" style={{ background: color }} />
            <span className="text-slate-400">{level}</span>
          </div>
        ))}
        <div className="ml-auto text-xs text-slate-500 flex items-center gap-1">
          <Brain size={11} className="text-purple-400" />
          Random Forest · Trained on 5000 samples
        </div>
      </div>
    </div>
  )
}
