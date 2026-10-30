import type { LucideIcon } from 'lucide-react'

export default function MetricTile({ label, value, note, icon: Icon, tone = 'teal' }: { label: string; value: string; note: string; icon: LucideIcon; tone?: 'teal' | 'amber' | 'red' | 'blue' }) {
  return <section className={`metric-tile tone-${tone}`}><div className="metric-top"><span>{label}</span><Icon size={17} strokeWidth={1.8} /></div><strong>{value}</strong><small>{note}</small></section>
}