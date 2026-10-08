import axios from 'axios';
import type { TrackRequest, TrackResponse } from '../types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
});

export function formatDateTimeForBackend(value: string): string {
  if (!value) return '';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) {
    const raw = value.replace('T', ' ');
    return `${raw}:00.000000+00`;
  }
  return `${dt.toISOString().slice(0, 19).replace('T', ' ')}.000000+00`;
}

export const submitTrack = async (payload: TrackRequest): Promise<TrackResponse> => {
  const normalized = {
    ...payload,
    start_time: formatDateTimeForBackend(payload.start_time),
    end_time: formatDateTimeForBackend(payload.end_time),
  };
  const { data } = await api.post<TrackResponse>('/api/track', normalized);
  return data;
};
