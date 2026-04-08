import { useEffect, useMemo, useState } from 'react';

import ForecastLineChart from '../charts/ForecastLineChart';
import RiskPieChart from '../charts/RiskPieChart';
import KpiCard from '../components/KpiCard';
import RiskAlerts from '../components/RiskAlerts';
import { apiClient } from '../services/api';

function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [vendors, setVendors] = useState([]);
  const [recommendation, setRecommendation] = useState(null);
  const [forecast, setForecast] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const [summaryData, vendorsData, recommendationData] = await Promise.all([
          apiClient.getDashboardSummary(),
          apiClient.getVendors(),
          apiClient.getRecommendation()
        ]);
        setSummary(summaryData);
        setVendors(vendorsData);
        setRecommendation(recommendationData);

        if (vendorsData.length > 0) {
          const forecastData = await apiClient.getForecast(vendorsData[0].id);
          setForecast(forecastData.points);
        }
      } catch (err) {
        setError(err.response?.data?.detail ?? err.message ?? 'Unable to load dashboard data.');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  const riskDistribution = useMemo(() => {
    const levels = { Low: 0, Medium: 0, High: 0 };
    vendors.forEach((vendor) => {
      if (vendor.risk_level && levels[vendor.risk_level] !== undefined) {
        levels[vendor.risk_level] += 1;
      }
    });
    return Object.entries(levels).map(([name, value]) => ({ name, value }));
  }, [vendors]);

  if (loading) {
    return <div className="card-surface p-6">Loading dashboard...</div>;
  }

  if (error) {
    return <div className="card-surface p-6 text-coral font-semibold">{error}</div>;
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard title="Vendors" value={summary?.total_vendors ?? 0} subtitle="Active records" tone="slate" />
        <KpiCard title="Average Risk" value={summary?.avg_risk_score ?? 0} subtitle="Composite score" tone="amber" />
        <KpiCard title="High Risk" value={summary?.high_risk_vendors ?? 0} subtitle="Immediate action" tone="coral" />
        <KpiCard title="Forecast Points" value={summary?.forecast_points ?? 0} subtitle="Projected horizon" tone="mint" />
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <ForecastLineChart data={forecast} />
        </div>
        <RiskPieChart data={riskDistribution} />
      </div>

      <RiskAlerts highRiskCount={summary?.high_risk_vendors ?? 0} recommendation={recommendation} />
    </div>
  );
}

export default Dashboard;
