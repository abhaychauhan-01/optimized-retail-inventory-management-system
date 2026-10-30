import { useCallback, useState } from 'react'
import { Download, FileCheck2, FileUp, Save } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import { ErrorState, LoadingState } from '../components/AsyncState'
import { confirmImport, errorMessage, getSettings, previewImport, putSettings, inventoryExportUrl } from '../services/api'
import { useAsyncData } from '../hooks/useAsyncData'

interface Preview { valid: boolean; rows: number; products: number; suppliers: number; duplicate_product_dates: number; message: string }

export default function SettingsPage() {
  const [draft, setDraft] = useState<{ safety_stock_rate: number; replenishment_horizon_days: number } | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [importing, setImporting] = useState(false)

  const load = useCallback(() => getSettings(), [])
  const { data: savedValues, loading, error: loadError, retry } = useAsyncData(load)
  const values = draft ?? savedValues ?? { safety_stock_rate: 0.2, replenishment_horizon_days: 14 }
  const save = async (event: React.FormEvent) => { event.preventDefault(); setSaving(true); setError(''); setNotice(''); try { await putSettings(values); setDraft(values); setNotice('Inventory policy settings saved.') } catch (reason) { setError(errorMessage(reason)) } finally { setSaving(false) } }
  const runPreview = async () => { if (!file) return; setError(''); setPreview(null); try { setPreview(await previewImport(file) as Preview) } catch (reason) { setError(errorMessage(reason)) } }
  const importFile = async () => { if (!file || !preview) return; if (!window.confirm(`Import ${preview.rows} observations and update ${preview.products} products?`)) return; setImporting(true); setError(''); try { await confirmImport(file); setNotice('CSV import completed.'); setPreview(null); setFile(null) } catch (reason) { setError(errorMessage(reason)) } finally { setImporting(false) } }

  return <>
    <PageHeader title="Data & settings" description="Configure the replenishment policy and manage inventory data." />
    {notice ? <div className="feedback success-feedback" role="status">{notice}<button onClick={() => setNotice('')}>Dismiss</button></div> : null}
    {error ? <ErrorState message={error} /> : null}
    {loading ? <LoadingState label="Loading settings" /> : <div className="settings-grid">
      <section className="panel settings-panel"><div className="panel-heading"><div><h2>Replenishment assumptions</h2><p>Applied to model-estimated reorder calculations</p></div></div>{loadError ? <ErrorState message={loadError} retry={retry} /> : <form onSubmit={(event) => void save(event)}><label className="setting-field"><span><strong>Safety stock rate</strong><small>Fraction of model-estimated lead-time demand added as buffer.</small></span><div className="number-input"><input type="number" min="0" max="2" step="0.05" value={values.safety_stock_rate} onChange={(event) => setDraft({ ...values, safety_stock_rate: Number(event.target.value) })} /><span>×</span></div></label><label className="setting-field"><span><strong>Replenishment horizon</strong><small>Target coverage period used to calculate recommended order quantity.</small></span><div className="number-input"><input type="number" min="1" max="365" value={values.replenishment_horizon_days} onChange={(event) => setDraft({ ...values, replenishment_horizon_days: Number(event.target.value) })} /><span>days</span></div></label><div className="policy-formula">Reorder point = lead-time model estimate + safety stock<br />Order quantity = max(0, target stock − on-hand stock)</div><button className="button button-primary" disabled={saving}><Save size={15} />{saving ? 'Saving…' : 'Save assumptions'}</button></form>}</section>
      <section className="panel settings-panel"><div className="panel-heading"><div><h2>Inventory export</h2><p>Download current stock records for local analysis.</p></div></div><p className="setting-copy">Unit cost and supplier pricing are excluded from this export to reduce accidental external disclosure.</p><a className="button button-secondary" href={inventoryExportUrl} download><Download size={15} /> Export inventory CSV</a></section>
      <section className="panel settings-panel import-panel"><div className="panel-heading"><div><h2>CSV import</h2><p>Validate the file before confirming database changes.</p></div></div><p className="setting-copy">Expected schema: date, product_id, category, season, stock_qty, reorder_level, daily_sales, unit_cost, supplier_id, lead_days. Maximum file size 5 MB.</p><label className="upload-field"><FileUp size={18} /><span>{file?.name ?? 'Choose a CSV file'}</span><input type="file" accept=".csv,text/csv" onChange={(event) => { setFile(event.target.files?.[0] ?? null); setPreview(null) }} /></label><div className="import-actions"><button className="button button-secondary" disabled={!file} onClick={() => void runPreview()}><FileCheck2 size={15} /> Preview validation</button>{preview ? <button className="button button-primary" disabled={importing} onClick={() => void importFile()}>{importing ? 'Importing…' : 'Confirm import'}</button> : null}</div>{preview ? <div className="preview-result"><strong>Validated preview</strong><span>{preview.rows} rows · {preview.products} products · {preview.suppliers} suppliers</span><span>{preview.duplicate_product_dates} duplicate product/date keys. Valid rows are retained; latest dated row is used to update product state.</span><span>{preview.message}</span></div> : null}</section>
    </div>}
  </>
}