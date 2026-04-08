import { useEffect, useState } from 'react';

import VendorBarChart from '../charts/VendorBarChart';
import { apiClient } from '../services/api';

function VendorComparison() {
  const [vendors, setVendors] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const data = await apiClient.getVendors();
        const sorted = [...data].sort((a, b) => (b.latest_risk_score ?? 0) - (a.latest_risk_score ?? 0));
        setVendors(sorted);
      } catch (err) {
        setError(err.response?.data?.detail ?? err.message ?? 'Failed to load vendors.');
      }
    };

    load();
  }, []);

  if (error) {
    return <div className="card-surface p-6 text-coral font-semibold">{error}</div>;
  }

  return (
    <div className="space-y-6">
      <VendorBarChart data={vendors.slice(0, 15)} />
      <div className="card-surface p-5 fade-up overflow-x-auto">
        <h3 className="font-display text-lg mb-4">Vendor Ranking</h3>
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-slate-500">
              <th className="py-2 pr-4">Vendor</th>
              <th className="py-2 pr-4">Code</th>
              <th className="py-2 pr-4">Category</th>
              <th className="py-2 pr-4">Risk Score</th>
              <th className="py-2 pr-4">Risk Level</th>
            </tr>
          </thead>
          <tbody>
            {vendors.map((vendor) => (
              <tr key={vendor.id} className="border-b border-slate-100">
                <td className="py-3 pr-4 font-semibold">{vendor.name}</td>
                <td className="py-3 pr-4">{vendor.vendor_code}</td>
                <td className="py-3 pr-4">{vendor.category ?? 'N/A'}</td>
                <td className="py-3 pr-4">{(vendor.latest_risk_score ?? 0).toFixed(2)}</td>
                <td className="py-3 pr-4">{vendor.risk_level ?? 'Unknown'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default VendorComparison;
