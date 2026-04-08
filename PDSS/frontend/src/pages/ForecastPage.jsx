import { useEffect, useState } from 'react';

import ForecastLineChart from '../charts/ForecastLineChart';
import { apiClient } from '../services/api';

function ForecastPage() {
  const [vendors, setVendors] = useState([]);
  const [selectedVendorId, setSelectedVendorId] = useState('');
  const [forecast, setForecast] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadVendors = async () => {
      try {
        const vendorData = await apiClient.getVendors();
        setVendors(vendorData);
        if (vendorData.length > 0) {
          setSelectedVendorId(String(vendorData[0].id));
        }
      } catch (err) {
        setError(err.response?.data?.detail ?? err.message ?? 'Unable to load vendors.');
      }
    };

    loadVendors();
  }, []);

  useEffect(() => {
    const loadForecast = async () => {
      if (!selectedVendorId) {
        return;
      }
      try {
        const forecastData = await apiClient.getForecast(selectedVendorId);
        setForecast(forecastData.points);
      } catch (err) {
        setError(err.response?.data?.detail ?? err.message ?? 'Unable to load forecast.');
      }
    };

    loadForecast();
  }, [selectedVendorId]);

  return (
    <div className="space-y-6">
      <div className="card-surface p-5 fade-up">
        <label className="text-sm font-semibold text-slate-600">Select Vendor</label>
        <select
          className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm focus:border-mint focus:outline-none"
          value={selectedVendorId}
          onChange={(event) => setSelectedVendorId(event.target.value)}
        >
          {vendors.map((vendor) => (
            <option key={vendor.id} value={vendor.id}>
              {vendor.name} ({vendor.vendor_code})
            </option>
          ))}
        </select>
      </div>

      {error ? <div className="card-surface p-6 text-coral font-semibold">{error}</div> : null}

      <ForecastLineChart data={forecast} />
    </div>
  );
}

export default ForecastPage;
