import Plot from 'react-plotly.js';
import type { TrackResponse } from '../types';
import { algorithmStyleMap } from '../constants/algorithms';

type FibrePlotProps = {
  data?: TrackResponse;
  hoveredPointIndex?: number | null;
  onHoverPoint?: (index: number | null) => void;
};

export default function FibrePlot({ data, hoveredPointIndex, onHoverPoint }: FibrePlotProps) {
  if (!data || !data.tracks?.length) {
    return (
      <div className="glass flex h-[480px] items-center justify-center rounded-2xl p-4 text-slate-400">
        Plot data will appear here.
      </div>
    );
  }

  const traces: any[] = [];
  const detections = data.fibre_detections ?? [];

  if (detections.length) {
    traces.push({
      type: 'scattergl',
      mode: 'markers',
      x: detections.map((p) => p.time),
      y: detections.map((p) => p.pos_km / 1000),
      marker: {
        color: detections.map((p) => p.z),
        colorscale: 'Viridis',
        showscale: true,
        cmin: -1,
        cmax: 1,
        size: 6,
        opacity: 0.45,
      },
      name: 'Detections',
      hovertemplate: '<b>Time</b>: %{x}<br><b>Pos</b>: %{y:.3f} km<br><b>z</b>: %{marker.color}<extra></extra>',
    });
  }

  data.tracks.forEach((track, index) => {
    const style = algorithmStyleMap[track.name] ?? algorithmStyleMap['VITERBI-BEAM'];
    const points = track.points ?? [];
    const xs = points.map((p) => p.time);
    const ys = points.map((p) => p.pos_km / 1000);
    traces.push({
      type: 'scattergl',
      mode: 'lines+markers',
      name: track.name,
      x: xs,
      y: ys,
      line: {
        color: style.color,
        width: style.lineWidth ?? 2,
        dash: style.dashed ? 'dash' : 'solid',
      },
      marker: {
        color: style.color,
        size: 7,
        symbol: style.marker,
      },
      opacity: hoveredPointIndex === null || index === 0 ? 1 : 0.8,
      hovertemplate: '<b>%{fullData.name}</b><br>Time: %{x}<br>Pos: %{y:.3f} km<extra></extra>',
    });
  });

  if (data.ais_latlon?.length && data.ais_available) {
    traces.push({
      type: 'scattergl',
      mode: 'lines',
      name: 'AIS/GPX ground truth',
      x: data.ais_latlon.map((p) => p.time ?? ''),
      y: data.ais_latlon.map((p) => (p.km ?? 0) / 1000),
      line: { color: '#22d3ee', width: 3 },
      hovertemplate: '<b>AIS / GPX</b><br>Time: %{x}<br>Pos: %{y:.3f} km<extra></extra>',
    });
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-slate-900/30 p-2">
      <Plot
        data={traces}
        layout={{
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(15,23,42,0.6)',
          font: { color: '#e2e8f0' },
          hovermode: 'closest',
          legend: { x: 0, y: 1, bgcolor: 'rgba(15, 23, 42, 0.5)', bordercolor: 'rgba(148, 163, 184, 0.3)' },
          xaxis: {
            title: 'Time (UTC)',
            gridcolor: '#1e293b',
            rangeselector: { bgcolor: 'rgba(59,130,246,0.2)' },
            rangeslider: { visible: true },
          },
          yaxis: {
            title: 'Position along fibre (km)',
            gridcolor: '#1e293b',
          },
          margin: { l: 60, r: 30, t: 40, b: 60 },
          showlegend: true,
        }}
        config={{ responsive: true, displaylogo: false }}
        style={{ width: '100%', height: '480px' }}
        useResizeHandler
        onClick={(_, points) => {
          const first = points?.points?.[0];
          if (first) onHoverPoint?.(first.pointIndex ?? null);
        }}
      />
    </div>
  );
}
