import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

function VendorBarChart({ data }) {
  return (
    <div className="card-surface p-5 fade-up">
      <h3 className="font-display text-lg mb-4">Vendor Reliability vs Risk</h3>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#cbd5e1" />
            <XAxis dataKey="vendor_code" tick={{ fontSize: 10 }} interval={0} angle={-25} textAnchor="end" height={75} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="latest_risk_score" name="Risk Score" fill="#ef4444" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default VendorBarChart;
