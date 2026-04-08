function RiskAlerts({ highRiskCount = 0, recommendation }) {
  return (
    <div className="card-surface p-6 fade-up">
      <h3 className="font-display text-lg">Risk Alert Center</h3>
      <p className="mt-2 text-sm text-slate-500">High risk vendors currently flagged: <span className="font-semibold text-coral">{highRiskCount}</span></p>
      {recommendation ? (
        <div className="mt-4 rounded-xl bg-slate-50 p-4">
          <p className="text-sm font-semibold text-slate-700">Recommended Vendor</p>
          <p className="mt-1 text-lg font-display">{recommendation.vendor_name}</p>
          <p className="text-sm text-slate-500">Risk Score: {recommendation.risk_score.toFixed(2)} | Reliability: {recommendation.reliability_index.toFixed(3)}</p>
          <p className="mt-2 text-sm text-slate-600">{recommendation.reason}</p>
        </div>
      ) : (
        <p className="mt-4 text-sm text-slate-500">Recommendation unavailable.</p>
      )}
    </div>
  );
}

export default RiskAlerts;
