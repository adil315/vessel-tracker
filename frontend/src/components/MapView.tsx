import { GoogleMap, Marker, Polyline, useJsApiLoader } from '@react-google-maps/api';
import { useCallback, useEffect, useMemo, useRef } from 'react';
import type { TrackResponse } from '../types';
import { DARK_MAP_STYLE } from '../constants/mapStyles';

type MapViewProps = {
  data?: TrackResponse;
  hoveredPointIndex?: number | null;
  mapType?: 'Roadmap' | 'Satellite' | 'Hybrid';
};

const containerStyle = {
  width: '100%',
  height: '520px',
  borderRadius: '1rem',
};

export default function MapView({ data, hoveredPointIndex, mapType = 'Roadmap' }: MapViewProps) {
  const mapRef = useRef<google.maps.Map | null>(null);
  const { isLoaded } = useJsApiLoader({
    id: 'google-map-script',
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_KEY || 'YOUR_KEY',
  });

  const points = useMemo(() => {
    const track = data?.tracks?.[0]?.points ?? [];
    const all: { lat: number; lng: number }[] = [];
    for (const pkt of track) {
      if (Number.isFinite(pkt.boat_lat) && Number.isFinite(pkt.boat_lon)) {
        all.push({ lat: pkt.boat_lat, lng: pkt.boat_lon });
      }
    }
    if (data?.fiber_latlon?.length) {
      for (const p of data.fiber_latlon) {
        all.push({ lat: p.lat, lng: p.lon });
      }
    }
    if (data?.ais_latlon?.length) {
      for (const p of data.ais_latlon) {
        all.push({ lat: p.lat, lng: p.lon });
      }
    }
    return all;
  }, [data]);

  const center = useMemo(() => {
    if (points.length) {
      const avgLat = points.reduce((sum, p) => sum + p.lat, 0) / points.length;
      const avgLng = points.reduce((sum, p) => sum + p.lng, 0) / points.length;
      return { lat: avgLat, lng: avgLng };
    }
    return { lat: 51.5, lng: -9.0 };
  }, [points]);

  const fitMapToPoints = useCallback(() => {
    if (!mapRef.current || !isLoaded) return;
    if (!points.length) {
      mapRef.current.setCenter(center);
      mapRef.current.setZoom(5);
      return;
    }
    const bounds = new google.maps.LatLngBounds();
    points.forEach((point) => bounds.extend({ lat: point.lat, lng: point.lng }));
    mapRef.current.fitBounds(bounds, 40);
  }, [center, isLoaded, points]);

  useEffect(() => {
    if (isLoaded) fitMapToPoints();
  }, [fitMapToPoints, isLoaded]);

  const mapOptions = useMemo(() => ({
    mapTypeId: mapType,
    streetViewControl: false,
    fullscreenControl: true,
    styles: DARK_MAP_STYLE,
  }), [mapType]);

  if (!isLoaded) {
    return <div className="glass flex h-[520px] items-center justify-center rounded-2xl p-4 text-slate-400">Loading map…</div>;
  }

  const primaryTrack = data?.tracks?.[0]?.points ?? [];
  const path = primaryTrack.map((p) => ({ lat: p.boat_lat, lng: p.boat_lon }));
  const onCable = primaryTrack.map((p) => ({ lat: p.on_lat, lng: p.on_lon }));
  const fiber = data?.fiber_latlon ?? [];
  const ais = data?.ais_latlon ?? [];

  return (
    <div className="rounded-2xl border border-white/10 bg-slate-900/30 p-2">
      <GoogleMap
        mapContainerStyle={containerStyle}
        center={center}
        zoom={5}
        options={mapOptions}
        onLoad={(map) => {
          mapRef.current = map;
          fitMapToPoints();
        }}
      >
        {fiber.length > 0 && (
          <Polyline path={fiber.map((p) => ({ lat: p.lat, lng: p.lon }))} options={{ strokeColor: '#60a5fa', strokeOpacity: 0.9, strokeWeight: 3, geodesic: true, icons: [{ icon: { path: 'M 0,-1 0,1', strokeOpacity: 1, scale: 3 }, offset: '0', repeat: '10px' }] }} />
        )}
        {onCable.length > 0 && (
          <Polyline path={onCable} options={{ strokeColor: '#9ca3af', strokeOpacity: 0.9, strokeWeight: 2, geodesic: true, icons: [{ icon: { path: 'M 0,-1 0,1', strokeOpacity: 1, scale: 2 }, offset: '0', repeat: '8px' }] }} />
        )}
        {path.length > 0 && (
          <Polyline path={path} options={{ strokeColor: '#ef4444', strokeOpacity: 1, strokeWeight: 4, geodesic: true }} />
        )}
        {ais.length > 0 && (
          <Polyline path={ais.map((p) => ({ lat: p.lat, lng: p.lon }))} options={{ strokeColor: '#06b6d4', strokeOpacity: 1, strokeWeight: 5, geodesic: true }} />
        )}
        {primaryTrack[0] && (
          <Marker position={{ lat: primaryTrack[0].boat_lat, lng: primaryTrack[0].boat_lon }} label={{ text: `START ${primaryTrack[0].time}`, color: '#fff' }} />
        )}
        {primaryTrack[primaryTrack.length - 1] && (
          <Marker position={{ lat: primaryTrack[primaryTrack.length - 1].boat_lat, lng: primaryTrack[primaryTrack.length - 1].boat_lon }} label={{ text: `END ${primaryTrack[primaryTrack.length - 1].time}`, color: '#fff' }} />
        )}
        {path.map((point, idx) => {
          if (hoveredPointIndex !== null && idx !== hoveredPointIndex) return null;
          return (
            <Marker key={`${point.lat}-${point.lng}-${idx}`} position={point} icon={{ path: 'M 0,0 m -6,0 a 6,6 0 1,0 12,0 a 6,6 0 1,0 -12,0', fillColor: '#22d3ee', fillOpacity: 1, strokeWeight: 0, scale: 1 }} />
          );
        })}
      </GoogleMap>
    </div>
  );
}
