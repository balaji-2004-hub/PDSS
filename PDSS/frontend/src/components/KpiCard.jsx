function KpiCard({ title, value, subtitle, tone = 'slate' }) {
  const toneClasses = {
    slate: 'from-slate-100 to-white text-slate-800',
    mint: 'from-emerald-100 to-white text-emerald-900',
    amber: 'from-amber-100 to-white text-amber-900',
    coral: 'from-rose-100 to-white text-rose-900'
  };

  return (
    <div className={`card-surface bg-gradient-to-br ${toneClasses[tone]} p-5 fade-up`}>
      <p className="text-sm font-semibold uppercase tracking-wide opacity-70">{title}</p>
      <p className="mt-3 text-3xl font-display font-semibold">{value}</p>
      <p className="mt-2 text-sm opacity-75">{subtitle}</p>
    </div>
  );
}

export default KpiCard;
