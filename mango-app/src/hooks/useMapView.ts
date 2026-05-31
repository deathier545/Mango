import { useEffect, type RefObject } from 'react'
import L from 'leaflet'
import type { MapTarget } from '../types/ui'

type UseMapViewArgs = {
  active: boolean
  globeVisible: boolean
  mapTarget: MapTarget
  mapHostRef: RefObject<HTMLDivElement | null>
  mapRef: RefObject<L.Map | null>
  mapTileLayerRef: RefObject<L.TileLayer | null>
  mapTileErrorCountRef: RefObject<number>
  mapMarkerRef: RefObject<L.CircleMarker | null>
  onMapNotice: (message: string) => void
}

export function useMapView({
  active,
  globeVisible,
  mapTarget,
  mapHostRef,
  mapRef,
  mapTileLayerRef,
  mapTileErrorCountRef,
  mapMarkerRef,
  onMapNotice,
}: UseMapViewArgs) {
  useEffect(() => {
    if (!(active && globeVisible)) return
    const host = mapHostRef.current
    if (!host) return
    let retryTimer: number | null = null
    let resizeObserver: ResizeObserver | null = null

    if (mapRef.current && (mapRef.current as unknown as { _container?: Element })._container !== host) {
      mapRef.current.remove()
      mapRef.current = null
      mapMarkerRef.current = null
    }

    if (!mapRef.current) {
      const map = L.map(host, {
        zoomControl: true,
        minZoom: 2,
        maxZoom: 19,
        worldCopyJump: true,
      })
      const osmLayer = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors',
      })
      mapTileErrorCountRef.current = 0
      osmLayer.on('tileerror', () => {
        mapTileErrorCountRef.current += 1
        if (mapTileErrorCountRef.current === 1) {
          onMapNotice('Map tiles are slow — switching to backup map style.')
        }
        if (mapTileErrorCountRef.current >= 4 && mapTileLayerRef.current === osmLayer) {
          map.removeLayer(osmLayer)
          const backupLayer = L.tileLayer('https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap &copy; CARTO',
          })
          backupLayer.addTo(map)
          mapTileLayerRef.current = backupLayer
          onMapNotice('Using backup map tiles.')
        }
      })
      osmLayer.addTo(map)
      mapTileLayerRef.current = osmLayer
      mapRef.current = map
      mapMarkerRef.current = L.circleMarker([mapTarget.lat, mapTarget.lng], {
        radius: 8,
        color: '#53d8ff',
        weight: 2,
        fillColor: '#53d8ff',
        fillOpacity: 0.28,
      }).addTo(map)
    }

    const map = mapRef.current
    if (!map) return

    const applyMapView = (animate: boolean): boolean => {
      const currentHost = mapHostRef.current
      if (!currentHost) return false
      const w = currentHost.clientWidth
      const h = currentHost.clientHeight
      if (w < 120 || h < 120) return false
      map.invalidateSize()
      map.setView([mapTarget.lat, mapTarget.lng], mapTarget.zoom, { animate })
      mapMarkerRef.current?.setLatLng([mapTarget.lat, mapTarget.lng])
      return true
    }

    const syncMapView = (attempt: number) => {
      const synced = applyMapView(attempt === 0)
      if (synced || attempt >= 12) return
      retryTimer = window.setTimeout(() => syncMapView(attempt + 1), 80)
    }

    window.requestAnimationFrame(() => syncMapView(0))

    const onWindowResize = () => {
      window.requestAnimationFrame(() => applyMapView(false))
    }
    window.addEventListener('resize', onWindowResize)
    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => {
        window.requestAnimationFrame(() => applyMapView(false))
      })
      resizeObserver.observe(host)
    }

    return () => {
      if (retryTimer != null) window.clearTimeout(retryTimer)
      window.removeEventListener('resize', onWindowResize)
      resizeObserver?.disconnect()
    }
  }, [
    active,
    globeVisible,
    mapTarget.lat,
    mapTarget.lng,
    mapTarget.zoom,
    mapHostRef,
    mapRef,
    mapMarkerRef,
    mapTileLayerRef,
    mapTileErrorCountRef,
    onMapNotice,
  ])

  useEffect(() => {
    if (globeVisible) return
    if (mapRef.current) {
      mapRef.current.remove()
      mapRef.current = null
      mapTileLayerRef.current = null
      mapTileErrorCountRef.current = 0
      mapMarkerRef.current = null
    }
  }, [globeVisible, mapRef, mapTileLayerRef, mapTileErrorCountRef, mapMarkerRef])

  useEffect(() => {
    return () => {
      if (mapRef.current) {
        mapRef.current.remove()
        mapRef.current = null
      }
    }
  }, [mapRef])
}
