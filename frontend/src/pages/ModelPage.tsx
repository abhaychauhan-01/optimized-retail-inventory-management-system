import { useCallback, useState, type FormEvent } from 'react'
import { Activity, CalendarDays, Gauge, ShieldAlert, ShieldCheck } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import { EmptyState, ErrorState, LoadingState } from '../components/AsyncState'
import { errorMessage, getModelMetrics, getModelStatus, predictDailySales } from '../services/api'
import type { DailySalesPrediction, ModelMetrics, ModelStatus } from '../types'
import { useAsyncData } from '../hooks/useAsyncData'

interface ModelPageData {
  status: ModelStatus
  metrics: ModelMetrics | null
}

const emptyForm = {
  date: '',
  category: '',
  season: '',
  stock_qty: '',
  reorder_level: '',
  unit_cost: '',
  lead_days: '',
}

const formatMetric = (value: number | null) => value === null || !Number.isFinite(value) ? 'Unavailable' : value.toFixed(3)

export default function ModelPage() {
  const load = useCallback(async (): Promise<ModelPageData> => {
    const status = await getModelStatus()
    const metrics = status.trained_model_available ? await getModelMetrics() : null
    return { status, metrics }
  }, [])
  const { data, loading, error, retry } = useAsyncData(load)
  const [form, setForm] = useState(emptyForm)
  const [prediction, setPrediction] = useState<DailySalesPrediction | null>(null)
  const [predicting, setPredicting] = useState(false)
  const [predictionError, setPredictionError] = useState('')

  async function submitPrediction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPrediction(null)
    setPredictionError('')
    setPredicting(true)
    try {
      const result = await predictDailySales({
        date: form.date,
        category: form.category,
        season: form.season,
        stock_qty: Number(form.stock_qty),
        reorder_level: Number(form.reorder_level),
        unit_cost: Number(form.unit_cost),
        lead_days: Number(form.lead_days),
      })
      setPrediction(result)
    } catch (reason) {
      setPredictionError(errorMessage(reason))
    } finally {
      setPredicting(false)
    }
  }

  return <>
    <PageHeader title="Model performance" description="Exploratory daily-sales regression metrics and predictions from the trained model." />
    {error ? <ErrorState message={error} retry={retry} /> : loading || !data ? <LoadingState /> : <>
      <div className="model-status">
        <div className="model-status-icon">{data.status.trained_model_available ? <ShieldCheck size={20} /> : <ShieldAlert size={20} />}</div>
        <div><span>Model status</span><strong>{data.status.trained_model_available ? 'Trained' : 'Not trained'}</strong><p>{data.status.model_name ?? data.status.message ?? 'Model artifact unavailable.'} · Target: {data.status.prediction_target}</p></div>
        <span className={`status-label ${data.status.trained_model_available ? 'status-healthy' : 'status-low'}`}>{data.status.trained_model_available ? 'Ready for prediction' : 'Unavailable'}</span>
      </div>

      {!data.status.trained_model_available || !data.metrics ? <EmptyState title="Daily-sales model unavailable" detail={data.status.message ?? 'Training metrics are not available. Run the model training command before making a prediction.'} /> : <>
        <div className="metric-grid model-grid">
          <section className="metric-tile"><div className="metric-top"><span>MAE</span><Activity size={16} /></div><strong>{formatMetric(data.metrics.mae)}</strong><small>Mean absolute error, sales units</small></section>
          <section className="metric-tile"><div className="metric-top"><span>RMSE</span><Gauge size={16} /></div><strong>{formatMetric(data.metrics.rmse)}</strong><small>Root mean squared error, sales units</small></section>
        </div>

        <section className="panel method-panel">
          <div className="panel-heading"><div><h2>Training details</h2><p>{data.metrics.model_name} · target: {data.metrics.prediction_target}</p></div><span className="mini-label">{data.metrics.dataset_type} DATA</span></div>
          <dl className="detail-list">
            <div><dt>Training observations</dt><dd>{data.metrics.training_observations.toLocaleString()}</dd></div>
            <div><dt>Evaluation observations</dt><dd>{data.metrics.evaluation_observations.toLocaleString()}</dd></div>
            <div><dt>Training date range</dt><dd>{data.metrics.training_date_range.start} to {data.metrics.training_date_range.end}</dd></div>
            <div><dt>Testing date range</dt><dd>{data.metrics.testing_date_range.start} to {data.metrics.testing_date_range.end}</dd></div>
            <div><dt>Training timestamp</dt><dd>{new Date(data.metrics.training_timestamp).toLocaleString()}</dd></div>
            <div><dt>Dataset source</dt><dd>{data.metrics.dataset_source}</dd></div>
            <div><dt>Dataset records</dt><dd>{data.metrics.total_observations.toLocaleString()} total · {data.metrics.original_observations.toLocaleString()} source · {data.metrics.synthetic_observations.toLocaleString()} synthetic</dd></div>
            <div><dt>Products / date coverage</dt><dd>{data.metrics.products} / {data.metrics.date_min} to {data.metrics.date_max}</dd></div>
            <div><dt>Repeated product/date rows</dt><dd>{data.metrics.duplicate_product_date_excess_rows} excess rows retained ({data.metrics.duplicate_product_date_participating_rows ?? 0} participating)</dd></div>
            <div><dt>Features</dt><dd>{data.metrics.features.join(', ')}</dd></div>
          </dl>
        </section>

        <section className="panel method-panel model-prediction-panel">
          <div className="panel-heading"><div><h2>Live daily-sales prediction</h2><p>Supply all model input features to get one regression estimate.</p></div><CalendarDays size={17} className="muted-icon" /></div>
          <form onSubmit={(event) => { void submitPrediction(event) }}>
            <div className="form-grid model-input-grid">
              <label>Date<input type="date" required value={form.date} onChange={(event) => setForm({ ...form, date: event.target.value })} /></label>
              <label>Category<select required value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })}><option value="">Select category</option>{(data.status.category_options ?? []).map((category) => <option key={category} value={category}>{category}</option>)}</select></label>
              <label>Season<select required value={form.season} onChange={(event) => setForm({ ...form, season: event.target.value })}><option value="">Select season</option>{(data.status.season_options ?? []).map((season) => <option key={season} value={season}>{season}</option>)}</select></label>
              <label>Stock quantity<input type="number" min="0" step="1" required value={form.stock_qty} onChange={(event) => setForm({ ...form, stock_qty: event.target.value })} /></label>
              <label>Reorder level<input type="number" min="0" step="1" required value={form.reorder_level} onChange={(event) => setForm({ ...form, reorder_level: event.target.value })} /></label>
              <label>Unit cost<input type="number" min="0" step="0.01" required value={form.unit_cost} onChange={(event) => setForm({ ...form, unit_cost: event.target.value })} /></label>
              <label>Lead days<input type="number" min="0" step="1" required value={form.lead_days} onChange={(event) => setForm({ ...form, lead_days: event.target.value })} /></label>
            </div>
            <div className="model-form-actions"><button className="button button-primary" type="submit" disabled={predicting}>{predicting ? 'Predicting…' : 'Predict daily sales'}</button></div>
          </form>
          {predictionError ? <div className="async-state error-state model-feedback" role="alert">{predictionError}</div> : null}
          {predicting ? <LoadingState label="Running model prediction" /> : null}
          {prediction ? <div className="prediction-result" role="status"><div><span>Predicted daily sales</span><strong>{prediction.predicted_daily_sales.toFixed(2)}</strong></div><div><span>Model</span><strong>{prediction.model_name}</strong></div><div><span>Prediction status</span><strong>{prediction.status}</strong></div></div> : null}
        </section>
      </>}
    </>}
  </>
}