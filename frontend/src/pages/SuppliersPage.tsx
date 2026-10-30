import { useCallback, useState } from 'react'
import { Pencil, Plus, Search, X } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState'
import { errorMessage, getSuppliers, saveSupplier } from '../services/api'
import type { Supplier } from '../types'
import { useAsyncData } from '../hooks/useAsyncData'

const blank: Supplier = { supplier_id: '', contact_name: '', email: '', phone: '', lead_days: 0 }

export default function SuppliersPage() {
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [modal, setModal] = useState(false)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState(blank)
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')

  const load = useCallback(() => getSuppliers(search || undefined), [search])
  const { data: supplierData, loading, error: loadError, retry } = useAsyncData(load)
  const items = supplierData ?? []
  const pageError = error || loadError
  const open = (supplier?: Supplier) => { setEditing(Boolean(supplier)); setForm(supplier ? { ...supplier } : { ...blank }); setModal(true) }
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true); setError('')
    try { await saveSupplier({ ...form, contact_name: form.contact_name || null, email: form.email || null, phone: form.phone || null }, editing); setModal(false); setNotice(editing ? 'Supplier updated.' : 'Supplier created.'); retry() }
    catch (reason) { setError(errorMessage(reason)) } finally { setSaving(false) }
  }

  return <>
    <PageHeader title="Suppliers" description="Maintain supplier IDs, contacts, and lead-time assumptions." action={<button className="button button-primary" onClick={() => open()}><Plus size={16} /> Add supplier</button>} />
    {notice ? <div className="feedback success-feedback" role="status">{notice}<button onClick={() => setNotice('')}>Dismiss</button></div> : null}
    {pageError ? <ErrorState message={pageError} retry={() => { setError(''); retry() }} /> : null}
    <section className="panel table-panel">
      <div className="filter-bar"><label className="search-field"><Search size={16} /><input placeholder="Search supplier ID" value={search} onChange={(event) => setSearch(event.target.value)} aria-label="Search supplier" /></label><span className="filter-count">{items.length} suppliers</span></div>
      {loading ? <LoadingState label="Loading suppliers" /> : items.length ? <div className="table-scroll"><table><thead><tr><th>Supplier ID</th><th>Contact</th><th>Email</th><th>Phone</th><th>Lead time</th><th>Products</th><th></th></tr></thead><tbody>{items.map((supplier) => <tr key={supplier.supplier_id}><td><strong>{supplier.supplier_id}</strong></td><td>{supplier.contact_name || 'Not provided'}</td><td>{supplier.email || 'Not provided'}</td><td>{supplier.phone || 'Not provided'}</td><td>{supplier.lead_days} days</td><td>{supplier.products_count ?? '—'}</td><td><button className="icon-button" aria-label={`Edit ${supplier.supplier_id}`} title="Edit supplier" onClick={() => open(supplier)}><Pencil size={15} /></button></td></tr>)}</tbody></table></div> : <EmptyState title="No suppliers found" detail="Add a supplier ID and contact details, or clear the search." />}
    </section>
    {modal ? <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setModal(false) }}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="supplier-title"><div className="modal-heading"><div><h2 id="supplier-title">{editing ? `Edit ${form.supplier_id}` : 'Add supplier'}</h2><p>Only enter contact information verified by your organization.</p></div><button className="icon-button" onClick={() => setModal(false)} aria-label="Close"><X size={17} /></button></div><form onSubmit={(event) => void submit(event)}><div className="form-grid"><label>Supplier ID<input required maxLength={80} disabled={editing} value={form.supplier_id} onChange={(event) => setForm({ ...form, supplier_id: event.target.value.trim() })} /></label><label>Lead time (days)<input type="number" min="0" required value={form.lead_days} onChange={(event) => setForm({ ...form, lead_days: Number(event.target.value) })} /></label><label>Contact name<input maxLength={160} value={form.contact_name ?? ''} onChange={(event) => setForm({ ...form, contact_name: event.target.value })} /></label><label>Email<input type="email" maxLength={254} value={form.email ?? ''} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label><label>Phone<input type="tel" maxLength={40} value={form.phone ?? ''} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></label></div><div className="modal-actions"><button type="button" className="button button-secondary" onClick={() => setModal(false)}>Cancel</button><button className="button button-primary" disabled={saving}>{saving ? 'Saving…' : 'Save supplier'}</button></div></form></section></div> : null}
  </>
}