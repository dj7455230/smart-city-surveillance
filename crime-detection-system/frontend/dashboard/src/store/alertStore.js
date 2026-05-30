/**
 * Global alert store — WebSocket + voice alerts + notification API
 */

let _alerts = []
let _unreadCount = 0
let _wsConnected = false
let _listeners = new Set()

function notify() {
  _listeners.forEach(fn => fn({ alerts: _alerts, unreadCount: _unreadCount, wsConnected: _wsConnected }))
}

function addAlert(alert) {
  _alerts = [alert, ..._alerts].slice(0, 200)
  _unreadCount += 1
  notify()
  _triggerVoiceAlert(alert)
  _triggerBrowserNotification(alert)
}

function _triggerVoiceAlert(alert) {
  try {
    const severityVoice = { CRITICAL: 1.3, HIGH: 1.1, MEDIUM: 1.0, LOW: 0.9 }
    const crimeLabel = alert.crime_type?.replace(/_/g, ' ') || 'unknown'
    const msg = new SpeechSynthesisUtterance(
      `Alert! ${crimeLabel} detected. Severity: ${alert.severity}.`
    )
    msg.rate = severityVoice[alert.severity] || 1.0
    msg.pitch = alert.severity === 'CRITICAL' ? 1.3 : 1.0
    msg.volume = 1.0
    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(msg)
  } catch (_) {}
}

function _triggerBrowserNotification(alert) {
  if (!('Notification' in window)) return
  if (Notification.permission !== 'granted') {
    Notification.requestPermission()
    return
  }
  const icons = { fight: '🥊', weapon: '🔫', accident: '🚗', suspicious: '👁️',
                  riot: '🚨', criminal: '🦹', stolen_vehicle: '🚔' }
  new Notification(`CrimeWatch AI — ${alert.severity}`, {
    body: `${icons[alert.crime_type] || '⚠️'} ${alert.crime_type?.toUpperCase()} detected\n${alert.camera_id}`,
    icon: '/favicon.ico',
    tag: alert.id,
  })
}

let wsInstance = null
let _reconnectTimer = null
let _reconnectDelay = 3000

function connectAlertWS() {
  if (wsInstance && wsInstance.readyState === WebSocket.OPEN) return
  // Clear any pending reconnect
  if (_reconnectTimer) { clearTimeout(_reconnectTimer); _reconnectTimer = null }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host || 'localhost:8000'
  const ws = new WebSocket(`${protocol}//${host}/ws/alerts`)
  wsInstance = ws

  ws.onopen = () => {
    _wsConnected = true
    _reconnectDelay = 3000   // reset backoff on success
    notify()
  }
  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      if (data.type === 'CRIME_ALERT') addAlert(data)
    } catch (_) {}
  }
  ws.onclose = () => {
    _wsConnected = false
    notify()
    // Exponential backoff: 3s → 6s → 12s → max 30s
    _reconnectDelay = Math.min(_reconnectDelay * 1.5, 30000)
    _reconnectTimer = setTimeout(connectAlertWS, _reconnectDelay)
  }
  ws.onerror = () => {
    // Let onclose handle reconnect — don't double-reconnect
    _wsConnected = false
    notify()
  }
}

import { useState, useEffect, useCallback } from 'react'

export function useAlertStore() {
  const [state, setState] = useState({ alerts: _alerts, unreadCount: _unreadCount, wsConnected: _wsConnected })
  useEffect(() => {
    const listener = (s) => setState({ ...s })
    _listeners.add(listener)
    return () => _listeners.delete(listener)
  }, [])
  const markAllRead = useCallback(() => { _unreadCount = 0; notify() }, [])
  return { ...state, connectAlertWS, markAllRead }
}
