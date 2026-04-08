import { useState } from 'react';

import { apiClient } from '../services/api';

const initialForm = {
  vendor_code: '',
  lead_time_days: 7,
  order_quantity: 100,
  unit_price: 55,
  on_time_rate: 0.8,
  quality_score: 0.85,
  defect_rate: 0.05,
  demand_variability_score: 0.3,
  cost_volatility: 0.25,
  external_risk_proxy: 0.2,
  delay_frequency: 0.15,
  rolling_delay_average: 0.2,
  reliability_index: 0.75,
  quality_weighted_score: 0.8,
  country: 'United States',
  category: 'Industrial'
};

function ScenarioSimulator() {
  const [form, setForm] = useState(initialForm);
  const [delayResult, setDelayResult] = useState(null);
  const [riskResult, setRiskResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const onChange = (event) => {
    const { name, value } = event.target;
    const numericFields = new Set([
      'lead_time_days',
      'order_quantity',
      'unit_price',
      'on_time_rate',
      'quality_score',
      'defect_rate',
      'demand_variability_score',
      'cost_volatility',
      'external_risk_proxy',
      'delay_frequency',
      'rolling_delay_average',
      'reliability_index',
      'quality_weighted_score'
    ]);
    setForm((prev) => ({
      ...prev,
      [name]: numericFields.has(name) ? Number(value) : value
    }));
  };

  const runSimulation = async () => {
    try {
      setLoading(true);
      setError('');
      const [delay, risk] = await Promise.all([
        apiClient.predictDelay(form),
        apiClient.predictRisk(form)
      ]);
      setDelayResult(delay);
      setRiskResult(risk);
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message ?? 'Prediction failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid gap-6 xl:grid-cols-3">
      <div className="card-surface p-6 fade-up xl:col-span-2">
        <h3 className="font-display text-lg">Scenario Inputs</h3>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {Object.entries(form).map(([key, value]) => (
            <label key={key} className="text-sm text-slate-600">
              <span className="mb-1 block capitalize">{key.replaceAll('_', ' ')}</span>
              <input
                name={key}
                value={value}
                onChange={onChange}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 focus:border-mint focus:outline-none"
              />
            </label>
          ))}
        </div>
        <button
          type="button"
          onClick={runSimulation}
          disabled={loading}
          className="mt-5 rounded-xl bg-slateDeep px-5 py-2 text-sm font-semibold text-white hover:bg-steel disabled:opacity-70"
        >
          {loading ? 'Running...' : 'Run Simulation'}
        </button>
        {error ? <p className="mt-3 text-sm font-semibold text-coral">{error}</p> : null}
      </div>

      <div className="space-y-4">
        <div className="card-surface p-5 fade-up">
          <h4 className="font-display">Delay Prediction</h4>
          {delayResult ? (
            <div className="mt-3 text-sm space-y-1">
              <p><span className="font-semibold">Prediction:</span> {delayResult.prediction}</p>
              <p><span className="font-semibold">Probability:</span> {(delayResult.probability * 100).toFixed(2)}%</p>
              <p><span className="font-semibold">Risk Score:</span> {delayResult.risk_score}</p>
              <p><span className="font-semibold">Risk Level:</span> {delayResult.risk_level}</p>
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-500">Run a scenario to view delay results.</p>
          )}
        </div>

        <div className="card-surface p-5 fade-up">
          <h4 className="font-display">Risk Classification</h4>
          {riskResult ? (
            <div className="mt-3 text-sm space-y-1">
              <p><span className="font-semibold">Class:</span> {riskResult.risk_class}</p>
              <p><span className="font-semibold">Confidence:</span> {(riskResult.confidence * 100).toFixed(2)}%</p>
              <p><span className="font-semibold">Risk Score:</span> {riskResult.risk_score}</p>
              <p><span className="font-semibold">Risk Level:</span> {riskResult.risk_level}</p>
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-500">Run a scenario to view risk results.</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default ScenarioSimulator;
