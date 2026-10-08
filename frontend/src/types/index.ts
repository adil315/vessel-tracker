export type Cable = 's1' | 's2';
export type Algorithm =
  | 'ST-DBSCAN'
  | 'RANSAC-CV'
  | 'VGRAPH'
  | 'SEED-GROW'
  | 'SEED-GROW-KINEMATIC'
  | 'VITERBI-BEAM'
  | 'ALL';

export interface TrackRequest {
  cable: Cable;
  algorithm: Algorithm;
  chain: string;
  table: string;
  min_od: number;
  max_od: number;
  start_time: string;
  end_time: string;
  conf_min: number;
  overlay_ais: boolean;
}

export interface FibrePoint {
  time: string;
  pos_km: number;
  z: number;
  confidence: number;
}

export interface TrackPoint {
  time: string;
  pos_km: number;
  z: number;
  on_lat: number;
  on_lon: number;
  boat_lat: number;
  boat_lon: number;
  h_smooth: number;
}

export interface LatLon {
  lat: number;
  lon: number;
  km?: number;
  time?: string;
}

export interface TrackScore {
  n: number;
  mae_km: number;
  coverage: number;
  v_mean: number;
  v_std: number;
}

export interface TrackResult {
  name: string;
  color: string;
  points: TrackPoint[];
  score: TrackScore;
}

export interface TrackResponse {
  fibre_detections: FibrePoint[];
  tracks: TrackResult[];
  fiber_latlon: LatLon[];
  ais_latlon?: LatLon[] | null;
  ais_available: boolean;
  metadata: {
    total_detections: number;
    cable: Cable;
    duration_min: number;
    algorithm: Algorithm | string;
    message?: string;
  };
}
