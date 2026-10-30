import type { ReactNode } from 'react'

export default function PageHeader({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow">INVENTORY OPERATIONS</div><h1>{title}</h1><p>{description}</p></div>{action ? <div className="page-heading-action">{action}</div> : null}</div>
}