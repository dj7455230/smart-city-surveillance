import { useState, useEffect } from 'react'
import { Shield, Download, Search, Lock, Hash, UserPlus, Car, Trash2, Plus, CheckCircle, XCircle } from 'lucide-react'

const TABS = [
  { id:'evidence',  label:'Evidence Vault',    icon:Shield },
  { id:'criminals', label:'Criminal Database', icon:UserPlus },
  { id:'vehicles',  label:'Stolen Vehicles',   icon:Car },
]

function EvidenceCard({ file, onDelete }) {
  return (
    <div className="card group hover:border-navy-500 transition-all">
      <div className="aspect-video bg-navy-900 rounded-lg overflow-hidden mb-3 relative">
        <img src={file.url} alt={file.filename} className="w-full h-full object-cover"
          onError={e => { e.target.style.display='none' }}/>
        <div className="absolute top-2 left-2">
          <span className={`text-xs px-2 py-0.5 rounded font-semibold ${
            ['weapon','criminal'].includes(file.crime_type) ? 'bg-red-600/80 text-white' :
            file.crime_type==='fight' ? 'bg-orange-600/80 text-white' : 'bg-yellow-600/80 text-white'
          }`}>{file.crime_type?.toUpperCase().replace('_',' ')}</span>
        </div>
        <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <a href={file.url} download={file.filename} className="bg-black/60 p-1.5 rounded hover:bg-black/80">
            <Download size={12} className="text-white"/>
          </a>
          <button onClick={() => onDelete(file.filename)} className="bg-black/60 p-1.5 rounded hover:bg-red-900/80">
            <Trash2 size={12} className="text-white"/>
          </button>
        </div>
      </div>
      <div className="space-y-1">
        <div className="text-xs text-slate-300 font-mono truncate">{file.filename}</div>
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>{file.size_kb} KB</span>
          <span>{new Date(file.created).toLocaleString()}</span>
        </div>
        {file.sha256 && (
          <div className="flex items-center gap-1 text-xs text-slate-600">
            <Hash size={10}/> <span className="font-mono truncate">{file.sha256.slice(0,16)}...</span>
          </div>
        )}
      </div>
    </div>
  )
}

export default function EvidenceVault() {
  const [tab, setTab]           = useState('evidence')
  const [evidence, setEvidence] = useState([])
  const [criminals, setCriminals] = useState([])
  const [vehicles, setVehicles] = useState([])
  const [search, setSearch]     = useState('')
  const [loading, setLoading]   = useState(false)

  // Criminal form
  const [cForm, setCForm] = useState({ name:'', alias:'', crime_history:'', risk_level:'MEDIUM', notes:'', file:null })
  const [cMsg, setCMsg]   = useState('')

  // Vehicle form
  const [vForm, setVForm] = useState({ plate_number:'', vehicle_make:'', vehicle_model:'', color:'', status:'stolen', reason:'', priority:'HIGH', reported_by:'' })
  const [vMsg, setVMsg]   = useState('')

  // Plate check
  const [checkPlate, setCheckPlate] = useState('')
  const [plateResult, setPlateResult] = useState(null)

  useEffect(() => {
    if (tab === 'evidence')  loadEvidence()
    if (tab === 'criminals') loadCriminals()
    if (tab === 'vehicles')  loadVehicles()
  }, [tab])

  async function loadEvidence() {
    setLoading(true)
    try { const r = await fetch('/api/evidence'); if(r.ok) setEvidence(await r.json()) } catch(_){}
    setLoading(false)
  }
  async function loadCriminals() {
    try { const r = await fetch('/api/criminals'); if(r.ok) setCriminals(await r.json()) } catch(_){}
  }
  async function loadVehicles() {
    try { const r = await fetch('/api/stolen-vehicles'); if(r.ok) setVehicles(await r.json()) } catch(_){}
  }

  async function deleteEvidence(filename) {
    if (!confirm('Delete this evidence file?')) return
    await fetch(`/api/evidence/${filename}`, { method:'DELETE' })
    setEvidence(prev => prev.filter(f => f.filename !== filename))
  }

  async function addCriminal(e) {
    e.preventDefault()
    setCMsg('')
    const fd = new FormData()
    Object.entries(cForm).forEach(([k,v]) => { if(k !== 'file' && v) fd.append(k,v) })
    if (cForm.file) fd.append('image', cForm.file)
    try {
      const r = await fetch('/api/criminals', { method:'POST', body:fd })
      const d = await r.json()
      if (d.success) {
        setCMsg('✓ Criminal profile added successfully')
        setCForm({ name:'', alias:'', crime_history:'', risk_level:'MEDIUM', notes:'', file:null })
        loadCriminals()
      } else {
        setCMsg('Error: ' + (d.detail || 'Failed'))
      }
    } catch(_) { setCMsg('Network error') }
  }

  async function deleteCriminal(id) {
    if (!confirm('Remove this criminal profile?')) return
    await fetch(`/api/criminals/${id}`, { method:'DELETE' })
    setCriminals(prev => prev.filter(c => c.id !== id))
  }

  async function addVehicle(e) {
    e.preventDefault()
    setVMsg('')
    const fd = new FormData()
    Object.entries(vForm).forEach(([k,v]) => { if(v) fd.append(k,v) })
    try {
      const r = await fetch('/api/stolen-vehicles', { method:'POST', body:fd })
      const d = await r.json()
      if (d.success) {
        setVMsg('✓ Vehicle registered successfully')
        setVForm({ plate_number:'', vehicle_make:'', vehicle_model:'', color:'', status:'stolen', reason:'', priority:'HIGH', reported_by:'' })
        loadVehicles()
      } else {
        setVMsg('Error: ' + (d.detail || 'Failed'))
      }
    } catch(_) { setVMsg('Network error') }
  }

  async function removeVehicle(id) {
    if (!confirm('Remove this vehicle from database?')) return
    await fetch(`/api/stolen-vehicles/${id}`, { method:'DELETE' })
    setVehicles(prev => prev.filter(v => v.id !== id))
  }

  async function doCheckPlate() {
    if (!checkPlate.trim()) return
    setPlateResult(null)
    const fd = new FormData()
    fd.append('plate', checkPlate)
    try {
      const r = await fetch('/api/stolen-vehicles/check', { method:'POST', body:fd })
      setPlateResult(await r.json())
    } catch(_) {}
  }

  const filteredEvidence = evidence.filter(f =>
    !search || f.filename.toLowerCase().includes(search.toLowerCase()) || f.crime_type?.includes(search.toLowerCase())
  )

  return (
    <div className="p-6 space-y-4 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Lock size={22} className="text-green-400"/> Evidence & Database Vault
        </h1>
        <p className="text-slate-400 text-sm mt-1">Tamper-proof evidence · Criminal profiles · Stolen vehicle registry</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-navy-800 p-1 rounded-xl w-fit">
        {TABS.map(({ id, label, icon:Icon }) => (
          <button key={id} onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${tab===id ? 'bg-navy-600 text-white' : 'text-slate-400 hover:text-white'}`}>
            <Icon size={14}/> {label}
          </button>
        ))}
      </div>

      {/* Evidence */}
      {tab === 'evidence' && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"/>
              <input type="text" placeholder="Search evidence..." value={search} onChange={e => setSearch(e.target.value)}
                className="bg-navy-800 border border-navy-600 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 w-56"/>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Hash size={12} className="text-green-400"/> SHA-256 verified · {filteredEvidence.length} files
            </div>
          </div>
          {loading ? (
            <div className="text-center py-12 text-slate-500">Loading...</div>
          ) : filteredEvidence.length === 0 ? (
            <div className="text-center py-16 text-slate-500">
              <Shield size={40} className="mx-auto mb-3 opacity-20"/>
              No evidence files yet. Alerts will save snapshots automatically.
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
              {filteredEvidence.map(f => <EvidenceCard key={f.filename} file={f} onDelete={deleteEvidence}/>)}
            </div>
          )}
        </div>
      )}

      {/* Criminals */}
      {tab === 'criminals' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Add form */}
          <div className="card">
            <h3 className="font-semibold text-white mb-4 flex items-center gap-2 text-sm">
              <Plus size={15} className="text-purple-400"/> Add Criminal Profile
            </h3>
            <form onSubmit={addCriminal} className="space-y-3">
              {[
                { key:'name',          label:'Full Name *',      type:'text',     required:true },
                { key:'alias',         label:'Alias / Nickname', type:'text' },
                { key:'crime_history', label:'Crime History',    type:'text' },
                { key:'notes',         label:'Notes',            type:'text' },
              ].map(({ key, label, type, required }) => (
                <div key={key}>
                  <label className="text-xs text-slate-400 mb-1 block">{label}</label>
                  <input type={type} required={required} value={cForm[key]}
                    onChange={e => setCForm(p => ({...p,[key]:e.target.value}))}
                    className="w-full bg-navy-800 border border-navy-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"/>
                </div>
              ))}
              <div>
                <label className="text-xs text-slate-400 mb-1 block">Risk Level</label>
                <select value={cForm.risk_level} onChange={e => setCForm(p => ({...p,risk_level:e.target.value}))}
                  className="w-full bg-navy-800 border border-navy-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500">
                  {['LOW','MEDIUM','HIGH','CRITICAL'].map(l => <option key={l} value={l}>{l}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-400 mb-1 block">Reference Photo</label>
                <input type="file" accept="image/*" onChange={e => setCForm(p => ({...p,file:e.target.files[0]}))}
                  className="w-full bg-navy-800 border border-navy-600 rounded-lg px-3 py-2 text-sm text-slate-300 file:mr-3 file:bg-purple-600 file:text-white file:border-0 file:rounded file:px-2 file:py-0.5 file:text-xs"/>
              </div>
              {cMsg && <div className={`text-xs px-3 py-2 rounded ${cMsg.startsWith('✓') ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>{cMsg}</div>}
              <button type="submit" className="w-full bg-purple-600 hover:bg-purple-700 text-white py-2 rounded-lg text-sm font-medium transition-colors">
                Add to Database
              </button>
            </form>
          </div>

          {/* List */}
          <div className="card">
            <h3 className="font-semibold text-white mb-4 text-sm">Registered Profiles ({criminals.length})</h3>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {criminals.map(c => (
                <div key={c.id} className="flex items-center gap-3 bg-navy-800 rounded-lg p-3 group">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center text-lg flex-shrink-0 ${
                    c.risk_level==='CRITICAL' ? 'bg-red-600/20' : c.risk_level==='HIGH' ? 'bg-orange-600/20' : 'bg-yellow-600/20'
                  }`}>🦹</div>
                  <div className="flex-1 min-w-0">
                    <div className="text-white text-sm font-medium">{c.name}</div>
                    {c.alias && <div className="text-xs text-slate-500">aka {c.alias}</div>}
                    <div className="text-xs text-slate-500">{c.crime_history?.slice(0,50)}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-semibold ${c.risk_level==='CRITICAL'?'text-red-400':c.risk_level==='HIGH'?'text-orange-400':'text-yellow-400'}`}>{c.risk_level}</span>
                    <button onClick={() => deleteCriminal(c.id)} className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-red-400 transition-all">
                      <Trash2 size={13}/>
                    </button>
                  </div>
                </div>
              ))}
              {criminals.length === 0 && <div className="text-slate-500 text-xs text-center py-6">No profiles yet</div>}
            </div>
          </div>
        </div>
      )}

      {/* Stolen Vehicles */}
      {tab === 'vehicles' && (
        <div className="space-y-4">
          {/* Plate checker */}
          <div className="card">
            <h3 className="font-semibold text-white mb-3 flex items-center gap-2 text-sm">
              <Car size={15} className="text-orange-400"/> Check Plate Number
            </h3>
            <div className="flex gap-3">
              <input type="text" placeholder="e.g. DL01AB1234" value={checkPlate}
                onChange={e => setCheckPlate(e.target.value.toUpperCase())}
                onKeyDown={e => e.key === 'Enter' && doCheckPlate()}
                className="flex-1 bg-navy-800 border border-navy-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-orange-500 font-mono max-w-xs"/>
              <button onClick={doCheckPlate} className="bg-orange-600 hover:bg-orange-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                Check
              </button>
            </div>
            {plateResult && (
              <div className={`mt-3 p-3 rounded-lg border flex items-start gap-3 ${plateResult.found ? 'bg-red-900/20 border-red-600/30' : 'bg-green-900/20 border-green-600/30'}`}>
                {plateResult.found ? <XCircle size={18} className="text-red-400 flex-shrink-0 mt-0.5"/> : <CheckCircle size={18} className="text-green-400 flex-shrink-0 mt-0.5"/>}
                <div>
                  <div className={`font-semibold text-sm ${plateResult.found ? 'text-red-400' : 'text-green-400'}`}>
                    {plateResult.found ? `${plateResult.status} — ${plateResult.plate_number}` : `CLEAR — ${plateResult.plate_number}`}
                  </div>
                  {plateResult.reason   && <div className="text-xs text-slate-400 mt-1">{plateResult.reason}</div>}
                  {plateResult.vehicle  && <div className="text-xs text-slate-400">Vehicle: {plateResult.vehicle} ({plateResult.color})</div>}
                  {plateResult.priority && <div className="text-xs text-slate-400">Priority: {plateResult.priority}</div>}
                </div>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Add vehicle form */}
            <div className="card">
              <h3 className="font-semibold text-white mb-4 flex items-center gap-2 text-sm">
                <Plus size={15} className="text-orange-400"/> Register Vehicle
              </h3>
              <form onSubmit={addVehicle} className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { key:'plate_number',  label:'Plate Number *', required:true },
                    { key:'vehicle_make',  label:'Make' },
                    { key:'vehicle_model', label:'Model' },
                    { key:'color',         label:'Color' },
                    { key:'reported_by',   label:'Reported By' },
                    { key:'reason',        label:'Reason' },
                  ].map(({ key, label, required }) => (
                    <div key={key}>
                      <label className="text-xs text-slate-400 mb-1 block">{label}</label>
                      <input type="text" required={required} value={vForm[key]}
                        onChange={e => setVForm(p => ({...p,[key]:e.target.value}))}
                        className="w-full bg-navy-800 border border-navy-600 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-orange-500"/>
                    </div>
                  ))}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-400 mb-1 block">Status</label>
                    <select value={vForm.status} onChange={e => setVForm(p => ({...p,status:e.target.value}))}
                      className="w-full bg-navy-800 border border-navy-600 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-orange-500">
                      <option value="stolen">Stolen</option>
                      <option value="wanted">Wanted</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 mb-1 block">Priority</label>
                    <select value={vForm.priority} onChange={e => setVForm(p => ({...p,priority:e.target.value}))}
                      className="w-full bg-navy-800 border border-navy-600 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-orange-500">
                      {['LOW','MEDIUM','HIGH','CRITICAL'].map(l => <option key={l} value={l}>{l}</option>)}
                    </select>
                  </div>
                </div>
                {vMsg && <div className={`text-xs px-3 py-2 rounded ${vMsg.startsWith('✓') ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>{vMsg}</div>}
                <button type="submit" className="w-full bg-orange-600 hover:bg-orange-700 text-white py-2 rounded-lg text-sm font-medium transition-colors">
                  Register Vehicle
                </button>
              </form>
            </div>

            {/* Vehicle list */}
            <div className="card">
              <h3 className="font-semibold text-white mb-3 text-sm">Registered Vehicles ({vehicles.length})</h3>
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {vehicles.map(v => (
                  <div key={v.id} className="flex items-center justify-between bg-navy-800 rounded-lg px-3 py-2 group">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-white font-mono font-semibold text-sm">{v.plate_number}</span>
                        <span className={`text-xs font-semibold ${v.status==='wanted'?'text-red-400':'text-orange-400'}`}>{v.status.toUpperCase()}</span>
                      </div>
                      <div className="text-xs text-slate-400">{[v.vehicle_make,v.vehicle_model,v.color].filter(Boolean).join(' · ')}</div>
                      {v.reason && <div className="text-xs text-slate-500">{v.reason}</div>}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-semibold ${v.priority==='CRITICAL'?'text-red-400':v.priority==='HIGH'?'text-orange-400':'text-yellow-400'}`}>{v.priority}</span>
                      <button onClick={() => removeVehicle(v.id)} className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-red-400 transition-all">
                        <Trash2 size={13}/>
                      </button>
                    </div>
                  </div>
                ))}
                {vehicles.length === 0 && <div className="text-slate-500 text-xs text-center py-6">No vehicles registered</div>}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
