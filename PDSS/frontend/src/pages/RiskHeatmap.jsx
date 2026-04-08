import { useEffect, useState } from 'react';

import RiskHeatmapTable from '../charts/RiskHeatmapTable';
import { apiClient } from '../services/api';

function RiskHeatmap() {
  const [vendors, setVendors] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const data = await apiClient.getVendors();
        setVendors(data);
      } catch (err) {
        setError(err.response?.data?.detail ?? err.message ?? 'Unable to load risk data.');
      }
    };

    load();
  }, []);

  if (error) {
    return <div className="card-surface p-6 text-coral font-semibold">{error}</div>;
  }

  return <RiskHeatmapTable vendors={vendors} />;
}

export default RiskHeatmap;
