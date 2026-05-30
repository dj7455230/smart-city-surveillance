import { useState, useEffect, useRef } from 'react'
import { Camera, AlertTriangle, Users, Zap, Volume2, VolumeX, Moon, Car, Shield, Eye } from 'lucide-react'

const CAMERAS = [
  { id: 'CAM-01', label: 'Front Camera',  vehicle: 'VH-001' },
  { id: 'CAM-02', label: 'Rear Camera',   vehicle: 'VH-001' },
  { id: 'CAM-03', label: 'Left Camera',   vehicle: 'VH-002' },
  { id: 'CAM-04', label: 'Right Camera',  vehicle: 'VH-002' },
]

const SEVERITY_BORDER = {
  CRITICAL: 'border-red-600',
  HIGH:     'border-orange-500',
  MEDIUM:   'border-yellow-500',
  LOW:      'border-green-500',
}

function DetectionBadges({ detection }) {
  if (!detection?.is_alert) return null
  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {detection.face?.has_criminal_match && (
        <span className="text-xs bg-red-900/80 text-red-300 border border-red-700 px-1.5 py-0.5 rounded">
          🦹 Criminal Match
        </span>
      )}
      {detection.anpr?.has_alert && (
        <span className="text-xs bg-red-900/80 text-red-300 border border-red-700 px-1.5 py-0.5 rounded">
          🚔 Stolen Vehicle
        </span>
      )}
      {detection.crowd?.riot_risk > 0.5 && (
        <span className="text-xs bg-orange-900/80 text-orange-300 border border-orange-700 px-1.5 py-0.5 rounded">
          🚨 Riot Risk {(detection.crowd.riot_risk * 100).toFixed(0)}%
        </span>
      )}
      {detection.night_mode && (
        <span className="text-xs bg-blue-900/80 text-blue-300 border border-blue-700 px-1.5 py-0.5 rounded">
          🌙 Night Mode
        </span>
      )}
    </div>
  )
}

function CameraFeed({ camera, isMain = false }) {
  const [frame, setFrame] = useState(null)
  const [detection, setDetection] = useState(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)

  useEffect(() => {
    connectWS()
    return () => wsRef.current?.close()
  }, [camera.id])

  function connectWS() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host || 'localhost:8000'
    const ws = new WebSocket(`${protocol}//${host}/ws/camera/${camera.id}`)
    wsRef.current = ws
    ws.onopen = () => setConnected(true)
    ws.onclose = () => { setConnected(false); setTimeout(connectWS, 3000) }
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'frame') {
        setFrame(`data:image/jpeg;base64,${data.frame}`)
        setDetection(data.detection)
      }
    }
  }

  const isAlert = detection?.is_alert
  const borderClass = isAlert ? (SEVERITY_BORDER[detection?.severity] || 'border-red-600') : 'border-navy-600'

  return (
    <div className={`relative bg-navy-900 rounded-xl overflow-hidden border-2 transition-all aspect-video ${borderClass} ${isAlert ? 'alert-pulse' : ''}`}>
      {frame
        ? <img src={frame} alt={camera.label} className="w-full h-full object-cover" />
        : (
          <div className="w-full h-full flex flex-col items-center justify-center gap-2 bg-navy-900">
            <Camera size={isMain ? 40 : 20} className="text-navy-600" />
            <span className="text-slate-500 text-xs">{connected ? 'Initializing...' : 'Connecting...'}</span>
          </div>
        )
      }

      {/* Camera label */}
      <div className="absolute top-2 left-2 flex items-center gap-1.5 bg-black/70 rounded px-2 py-1">
        <div className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-green-400' : 'bg-red-400'}`} />
        <span className="text-white text-xs font-medium">{camera.label}</span>
      </div>

      {/* Alert overlay */}
      {isAlert && (
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 to-transparent p-2">
          <div className="flex items-center gap-1.5">
            <AlertTriangle size={12} className="text-red-400 flex-shrink-0" />
            <span className="text-red-300 text-xs font-bold uppercase">
              {detection.crime_type?.replace(/_/g, ' ')} — {detection.severity}
            </span>
            <span className="ml-auto text-red-400 text-xs">{(detection.confidence * 100).toFixed(0)}%</span>
          </div>
          {isMain && <DetectionBadges detection={detection} />}
        </div>
      )}

      {/* Person count */}
      {detection?.person_count > 0 && (
        <div className="absolute top-2 right-2 flex items-center gap-1 bg-black/70 rounded px-1.5 py-1">
          <Users size={11} className="text-blue-400" />
          <span className="text-white text-xs">{detection.person_count}</span>
        </div>
      )}
    </div>
  )
}

export default function LiveFeed() {
  const [mainCamera, setMainCamera] = useState(CAMERAS[0])
  const [voiceEnabled, setVoiceEnabled] = useState(true)

  return (
    <div className="p-6 space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Live Camera Feed</h1>
          <p className="text-slate-400 text-sm mt-1">360° surveillance · Face ID · ANPR · Crowd Analysis</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setVoiceEnabled(!voiceEnabled)}
            className={`p-2 rounded-lg border transition-all ${voiceEnabled ? 'bg-blue-600/20 border-blue-600/30 text-blue-400' : 'bg-navy-700 border-navy-600 text-slate-400'}`}
            title="Toggle voice alerts"
          >
            {voiceEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
          </button>
          <div className="flex items-center gap-2 bg-red-600/10 border border-red-600/20 rounded-lg px-3 py-2">
            <div className="live-dot" />
            <span className="text-red-400 text-sm font-medium">LIVE</span>
          </div>
        </div>
      </div>

      {/* Main + grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-3">
          <CameraFeed camera={mainCamera} isMain />
        </div>
        <div className="space-y-3">
          <div className="text-xs text-slate-500 uppercase tracking-wider font-medium px-1">Camera Grid</div>
          {CAMERAS.map(cam => (
            <button
              key={cam.id}
              onClick={() => setMainCamera(cam)}
              className={`w-full text-left rounded-lg overflow-hidden border-2 transition-all ${mainCamera.id === cam.id ? 'border-blue-500' : 'border-navy-600 hover:border-navy-500'}`}
            >
              <CameraFeed camera={cam} />
            </button>
          ))}
        </div>
      </div>

      {/* Feature legend */}
      <div className="card">
        <div className="flex items-center gap-6 flex-wrap">
          <span className="text-xs text-slate-500 uppercase tracking-wider">Active Features</span>
          {[
            { icon: Zap,    label: 'YOLOv8 Detection',   color: 'text-blue-400' },
            { icon: Shield, label: 'Face Recognition',   color: 'text-purple-400' },
            { icon: Car,    label: 'ANPR / Plate Scan',  color: 'text-orange-400' },
            { icon: Users,  label: 'Crowd Analysis',     color: 'text-yellow-400' },
            { icon: Moon,   label: 'Night Vision',       color: 'text-cyan-400' },
            { icon: Eye,    label: 'Crime Prediction',   color: 'text-green-400' },
          ].map(({ icon: Icon, label, color }) => (
            <div key={label} className="flex items-center gap-1.5 text-xs">
              <Icon size={13} className={color} />
              <span className="text-slate-400">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
