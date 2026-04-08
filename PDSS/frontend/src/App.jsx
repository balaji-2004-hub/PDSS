import { Navigate, Route, Routes } from 'react-router-dom';

import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import ForecastPage from './pages/ForecastPage';
import RiskHeatmap from './pages/RiskHeatmap';
import ScenarioSimulator from './pages/ScenarioSimulator';
import VendorComparison from './pages/VendorComparison';

function App() {
  return (
    <div className="min-h-screen p-4 md:p-6">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-6 lg:flex-row">
        <Sidebar />
        <main className="flex-1">
          <div className="mb-5 rounded-2xl bg-gradient-to-r from-slateDeep via-steel to-slateDeep px-6 py-5 text-cloud shadow-soft fade-up">
            <h2 className="font-display text-2xl">Predictive Decision Support System</h2>
            <p className="mt-1 text-sm text-slate-200">Vendor risk intelligence, delivery reliability, and proactive supply continuity forecasting</p>
          </div>

          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/vendor-comparison" element={<VendorComparison />} />
            <Route path="/risk-heatmap" element={<RiskHeatmap />} />
            <Route path="/forecast" element={<ForecastPage />} />
            <Route path="/scenario" element={<ScenarioSimulator />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default App;
