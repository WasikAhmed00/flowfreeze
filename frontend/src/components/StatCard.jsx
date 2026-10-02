export default function StatCard({ label, value, sub, icon, tone = 'green' }) {
  return <article className="stat-card"><div className={`stat-icon ${tone}`}>{icon}</div><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-sub">{sub}</div><span className="stat-spark" aria-hidden="true">⌁</span></article>
}
