import { NavLink } from 'react-router-dom';

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/vendor-comparison', label: 'Vendor Comparison' },
  { to: '/risk-heatmap', label: 'Risk Heatmap' },
  { to: '/forecast', label: 'Forecast Page' },
  { to: '/scenario', label: 'Scenario Simulator' }
];

function Sidebar() {
  return (
    <aside className="w-full lg:w-72 shrink-0 rounded-2xl bg-slateDeep text-cloud shadow-soft">
      <div className="px-6 pt-8 pb-5 border-b border-slate-700">
        <h1 className="font-display text-xl leading-tight">PDSS Continuity Console</h1>
        <p className="mt-2 text-sm text-slate-300">Vendor Management Intelligence</p>
      </div>
      <nav className="p-4">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `block rounded-xl px-4 py-3 text-sm font-semibold transition ${
                isActive ? 'bg-mint text-slateDeep' : 'text-slate-200 hover:bg-slate-700'
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="px-6 pb-8 text-xs text-slate-400">Real-time risk and forecast insights</div>
    </aside>
  );
}

export default Sidebar;
