import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';

function ForecastLineChart({ data }) {
  return (
    <div className="card-surface p-5 fade-up">
      <h3 className="font-display text-lg mb-4">12-Month Cost Forecast</h3>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#cbd5e1" />
            <XAxis dataKey="forecast_month" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="predicted_cost" name="Predicted" stroke="#0f766e" strokeWidth={2} />
            <Line type="monotone" dataKey="upper_bound" name="Upper" stroke="#f59e0b" strokeDasharray="5 5" />
            <Line type="monotone" dataKey="lower_bound" name="Lower" stroke="#ef4444" strokeDasharray="5 5" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default ForecastLineChart;
