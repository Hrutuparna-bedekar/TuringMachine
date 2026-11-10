import { SimulationRequest, SimulationResponse } from './machine';

/**
 * Execute simulation by calling POST /api/simulate
 */
export async function simulateMachine(req: SimulationRequest): Promise<SimulationResponse> {
  const response = await fetch('/api/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Unknown network error' }));
    throw new Error(errorData.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Check backend health by calling GET /api/health
 */
export async function checkHealth(): Promise<{ status: string }> {
  const response = await fetch('/api/health');
  if (!response.ok) throw new Error('Health check failed');
  return response.json();
}
