import { SimulationRequest, SimulationResponse, MultiBudgetPrediction, TuringMachine } from './types';

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
    let errorDetail = `HTTP ${response.status}`;
    try {
      const errorData = await response.json();
      if (typeof errorData.detail === 'string') {
        errorDetail = errorData.detail;
      } else if (Array.isArray(errorData.detail)) {
        // FastAPI / Pydantic validation error list
        errorDetail = errorData.detail.map((d: any) => `${d.loc?.join('.') || 'field'}: ${d.msg}`).join('; ');
      }
    } catch {
      // fallback
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

/**
 * Check backend health by calling GET /api/health
 */
export async function checkHealth(): Promise<{ status: string }> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);
    const response = await fetch('/api/health', { signal: controller.signal });
    clearTimeout(timeoutId);
    if (!response.ok) return { status: 'down' };
    return response.json();
  } catch {
    return { status: 'offline' };
  }
}

/** Request model predictions for the three supported budgets. */
export async function predictBoundedHalting(
  machine: TuringMachine,
  input: string
): Promise<MultiBudgetPrediction> {
  const response = await fetch('/api/predict', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ machine, input }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail;
    const message = Array.isArray(detail)
      ? detail.map((issue) => issue.msg).join(', ')
      : typeof detail === 'string' ? detail : `Prediction request failed (HTTP ${response.status}).`;
    throw new Error(message);
  }

  return response.json();
}
