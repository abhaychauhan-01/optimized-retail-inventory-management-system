import { AlertCircle, LoaderCircle } from 'lucide-react'

export function LoadingState({ label = 'Loading data' }: { label?: string }) {
  return <div className="async-state"><LoaderCircle className="spin" size={19} /><span>{label}</span></div>
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="async-state error-state"><AlertCircle size={19} /><span>{message}</span>{retry ? <button className="text-button" onClick={retry}>Retry</button> : null}</div>
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><strong>{title}</strong><span>{detail}</span></div>
}