function RiskHeatmapTable({ vendors }) {
  return (
    <div className="card-surface p-5 fade-up overflow-x-auto">
      <h3 className="font-display text-lg mb-4">Vendor Risk Heatmap</h3>
      <table className="min-w-full text-sm">
        <thead>
          <tr className="text-left text-slate-500 border-b border-slate-200">
            <th className="py-2 pr-4">Vendor</th>
            <th className="py-2 pr-4">Category</th>
            <th className="py-2 pr-4">Country</th>
            <th className="py-2 pr-4">Risk Score</th>
            <th className="py-2 pr-4">Risk Level</th>
          </tr>
        </thead>
        <tbody>
          {vendors.map((vendor) => {
            const score = vendor.latest_risk_score ?? 0;
            const tone = score >= 70 ? 'bg-rose-100 text-rose-700' : score >= 40 ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700';
            return (
              <tr key={vendor.id} className="border-b border-slate-100">
                <td className="py-3 pr-4 font-semibold">{vendor.name}</td>
                <td className="py-3 pr-4">{vendor.category ?? 'N/A'}</td>
                <td className="py-3 pr-4">{vendor.country ?? 'N/A'}</td>
                <td className="py-3 pr-4">{score.toFixed(2)}</td>
                <td className="py-3 pr-4">
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${tone}`}>
                    {vendor.risk_level ?? 'Unknown'}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default RiskHeatmapTable;
