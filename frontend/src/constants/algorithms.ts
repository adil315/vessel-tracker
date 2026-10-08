export const algorithmStyleMap: Record<string, { color: string; marker: string; dashed?: boolean; lineWidth?: number }> = {
  'ST-DBSCAN': { color: '#d946ef', marker: 'circle', lineWidth: 2 },
  'RANSAC-CV': { color: '#ef4444', marker: 'square', lineWidth: 2 },
  'VGRAPH': { color: '#f59e0b', marker: 'triangle-up', dashed: true, lineWidth: 2 },
  'SEED-GROW': { color: '#a3e635', marker: 'diamond', lineWidth: 2 },
  'SEED-GROW-KINEMATIC': { color: '#22c55e', marker: 'diamond', lineWidth: 2 },
  'VITERBI-BEAM': { color: '#3b82f6', marker: 'circle', lineWidth: 3 },
  AIS: { color: '#22d3ee', marker: 'circle', lineWidth: 3 },
};
