import { useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const NAV = [
  ['overview', 'Overview', '01'],
  ['analysis', 'Forecast analysis', '02'],
  ['accuracy', 'Forecast accuracy', '03'],
  ['quality', 'Data quality', '04'],
]

async function request(path, signal, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, { ...options, signal })
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try { detail = (await response.json()).detail || detail } catch { /* non-JSON error */ }
    throw new Error(detail)
  }
  return response.json()
}

function query(start, end) {
  return `?${new URLSearchParams({ start_date: start, end_date: end })}`
}

const number = (value, digits = 0) => value == null ? '—' : new Intl.NumberFormat('en-GB', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value)
const dateTime = value => value ? new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'UTC' }).format(new Date(value)) + ' UTC' : '—'
const day = value => value ? new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', timeZone: 'UTC' }).format(new Date(value)) : '—'
const unit = 'MW'
const fullDay = value => new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${value}T00:00:00Z`))
const dateRange = (start, end) => start === end ? fullDay(start) : `${fullDay(start)} — ${fullDay(end)}`

function App() {
  const [page, setPage] = useState('overview')
  const [start, setStart] = useState('2026-01-01')
  const [end, setEnd] = useState('2026-01-04')
  const [refresh, setRefresh] = useState(0)
  const [summary, setSummary] = useState(null)
  const [records, setRecords] = useState([])
  const [accuracy, setAccuracy] = useState(null)
  const [quality, setQuality] = useState(null)
  const [health, setHealth] = useState(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    setStatus('loading')
    setError('')
    Promise.allSettled([
      request(`/api/summary${query(start, end)}`, controller.signal),
      request(`/api/forecasts${query(start, end)}&limit=2000`, controller.signal),
      request(`/api/accuracy${query(start, end)}`, controller.signal),
      request(`/api/data-quality${query(start, end)}`, controller.signal),
      request('/api/health', controller.signal),
    ]).then(results => {
      if (controller.signal.aborted) return
      const [nextSummary, nextRecords, nextAccuracy, nextQuality, nextHealth] = results
      const failures = results
        .filter(result => result.status === 'rejected' && result.reason?.name !== 'AbortError')
        .map(result => result.reason?.message || 'A data request failed')
      if (nextSummary.status === 'fulfilled') setSummary(nextSummary.value)
      if (nextRecords.status === 'fulfilled') setRecords(nextRecords.value)
      if (nextAccuracy.status === 'fulfilled') setAccuracy(nextAccuracy.value)
      if (nextQuality.status === 'fulfilled') setQuality(nextQuality.value)
      if (nextHealth.status === 'fulfilled') setHealth(nextHealth.value)
      setError([...new Set(failures)].join('; '))
      setStatus(failures.length ? 'degraded' : 'ready')
    })
    return () => controller.abort()
  }, [start, end, refresh])

  const changePage = next => { setPage(next); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  const refreshData = async () => {
    if (status === 'loading') return
    setStatus('loading'); setError('')
    try {
      await request('/api/refresh', undefined, { method: 'POST' })
      setRefresh(value => value + 1)
    } catch (nextError) {
      setError(nextError.message); setStatus('error')
    }
  }
  return <div className={`app-shell ${page === 'overview' ? 'overview-mode' : ''}`}>
    <Sidebar page={page} onNavigate={changePage} status={status} health={health} start={start} end={end} />
    <main className="main">
      <header className="topbar">
        {page === 'overview' && <div className="delivery-meta">
          <div><span className="meta-label">DELIVERY DATE</span><strong>{dateRange(start, end)}</strong></div>
          <div className="source-meta"><span className="meta-label">DATA SOURCE</span><strong>Elexon BMRS</strong><span className={`source-state ${status === 'ready' && health?.status === 'ok' ? 'connected' : 'disconnected'}`}><span className="live-dot" />{status === 'loading' ? 'Checking source' : status === 'ready' && health?.status === 'ok' ? 'Source connected' : 'Source unavailable'}</span></div>
        </div>}
        <div className="mobile-brand"><span className="brand-mark small">↗</span><span>WIND / FI</span></div>
        {page === 'overview' && <div className="topbar-meta"><span className="live-dot" /> ELEXON BMRS <span className="meta-divider" /> UTC</div>}
        <button className="refresh-button" onClick={refreshData} disabled={status === 'loading'}><span className={status === 'loading' ? 'spin' : ''}>↻</span> Refresh data</button>
      </header>
      <div className="content">
        <PageIntro page={page} summary={summary} />
        <DateFilter start={start} end={end} setStart={setStart} setEnd={setEnd} />
        {status === 'loading' ? <LoadingState /> : <>
          {error && <ErrorState message={error} onRetry={refreshData} />}
          <PageContent page={page} summary={summary} records={records} accuracy={accuracy} quality={quality} health={health} start={start} end={end} onNavigate={changePage} />
        </>}
      </div>
    </main>
  </div>
}

function Sidebar({ page, onNavigate, status, health, start, end }) {
  return <aside className="sidebar">
    <div className="brand"><span className="brand-mark">≋</span><div><strong>WindCast</strong><small>UK WIND INTELLIGENCE</small></div></div>
    <div className="sidebar-label">Workspace</div>
    <nav>{NAV.map(([id, label, index]) => <button key={id} className={page === id ? 'nav-item active' : 'nav-item'} onClick={() => onNavigate(id)}><span className="nav-index">{index}</span>{label}<span className="nav-arrow">→</span></button>)}</nav>
    <div className="sidebar-footer"><div className="period-label">ANALYSIS PERIOD</div><strong>{dateRange(start, end).toUpperCase()}</strong><p>National wind generation<br />and forecast vintages</p><div className={`source-tag ${status === 'ready' && health?.status === 'ok' ? 'connected' : 'disconnected'}`}><span className="live-dot" /> {status === 'loading' ? 'Checking source' : status === 'ready' && health?.status === 'ok' ? 'Source connected' : 'Source unavailable'}</div></div>
  </aside>
}

function PageIntro({ page, summary }) {
  const titles = { overview: ['Overview', 'A clear view of forecast performance for the selected delivery window.'], analysis: ['Forecast analysis', 'Inspect every delivery period and the forecast decision behind it.'], accuracy: ['Forecast accuracy', 'Measure how closely selected forecasts tracked observed generation.'], quality: ['Data quality', 'Understand source availability and completeness before using the analysis.'] }
  return <div className="page-intro"><div><div className="eyebrow">NATIONAL WIND / JANUARY 2026</div><h1>{titles[page][0]}</h1><p>{titles[page][1]}</p></div><div className="assumption"><span className="info-icon">i</span><div><b>Decision policy</b><br /><span>{summary?.decisionCutoffPolicy || 'Latest eligible forecast before delivery'}</span></div></div></div>
}

function DateFilter({ start, end, setStart, setEnd }) {
  return <div className="filter-bar"><div className="filter-title"><span className="filter-icon">◷</span><span>Delivery window</span></div><label>From <input type="date" value={start} min="2026-01-01" max={end} onChange={event => setStart(event.target.value)} /></label><span className="date-separator">—</span><label>To <input type="date" value={end} min={start} max="2026-01-31" onChange={event => setEnd(event.target.value)} /></label><span className="filter-note">All times UTC</span></div>
}

function PageContent({ page, summary, records, accuracy, quality, health, start, end, onNavigate }) {
  if (page === 'analysis') return <Analysis records={records} start={start} end={end} />
  if (page === 'accuracy') return <Accuracy accuracy={accuracy} />
  if (page === 'quality') return <Quality quality={quality} health={health} summary={summary} />
  return <Overview summary={summary} records={records} onNavigate={onNavigate} />
}

function Overview({ summary, records, onNavigate }) {
  const metrics = summary?.metrics
  return <><section className="kpi-grid">
    <Kpi label="Mean absolute error" value={number(metrics?.mae)} suffix={unit} detail="Average size of forecast error" accent="green" />
    <Kpi label="Root mean square error" value={number(metrics?.rmse)} suffix={unit} detail="Penalises larger errors more heavily" />
    <Kpi label="Mean forecast bias" value={number(metrics?.bias)} suffix={unit} detail={metrics?.bias == null ? 'Forecast minus actual' : metrics.bias > 0 ? 'Positive: forecast overestimated' : 'Negative: forecast underestimated'} accent={metrics?.bias > 0 ? 'amber' : 'blue'} />
    <Kpi label="Matched periods" value={number(metrics?.matchedPeriods)} suffix="periods" detail="Periods with both values present" />
    <Kpi label="Data coverage" value={number(summary?.coverage?.coveragePercentage, 1)} suffix="%" detail={`${number(summary?.coverage?.expectedPeriods)} expected hourly periods`} accent="green" />
  </section>
  <section className="panel chart-panel">
    <div className="panel-heading"><div><div className="eyebrow">DELIVERY PROFILE</div><h2>Actual vs selected forecast</h2></div><div className="chart-meta">MW · hourly comparison</div><div className="legend"><span><i className="legend-line actual" /> Actual generation</span><span><i className="legend-line forecast" /> Selected forecast</span></div></div>
    <TimeChart records={records} />
  </section>
  <section className="overview-bottom">
    <div className="panel insight-panel"><div className="eyebrow">READING THE SIGNAL</div><h2>What this tells you</h2><p>Each hourly WINDFOR value is compared with the average of its two FUELHH half-hour actuals. Use the accuracy view to see how performance varies day to day.</p><button className="text-button" onClick={() => onNavigate('accuracy')}>Explore accuracy <span>→</span></button></div>
    <div className="panel snapshot-panel"><div className="eyebrow">DATA SNAPSHOT</div><div className="snapshot-row"><span>Observed hours</span><strong>{number(summary?.coverage?.observedActualPeriods)} <small>/ {number(summary?.coverage?.expectedPeriods)}</small></strong></div><div className="snapshot-row"><span>Eligible forecast hours</span><strong>{number(summary?.coverage?.observedForecastPeriods)} <small>/ {number(summary?.coverage?.expectedPeriods)}</small></strong></div><div className="snapshot-row"><span>Last retrieved</span><strong className="small-value">{dateTime(summary?.latestSuccessfulRetrieval)}</strong></div></div>
  </section></>
}

function Kpi({ label, value, suffix, detail, accent }) { return <article className={`kpi ${accent || ''}`}><div className="kpi-label">{label}<span className="kpi-dot" /></div><div className="kpi-value">{value} <span>{suffix}</span></div><div className="kpi-detail">{detail}</div></article> }

function TimeChart({ records }) {
  const points = records.filter(record => record.actualGeneration != null || record.forecastGeneration != null)
  if (!points.length) return <EmptyState message="No forecast records are available for this date range." />
  const width = 1000, height = 460, pad = { top: 20, right: 24, bottom: 46, left: 76 }
  const values = points.flatMap(record => [record.actualGeneration, record.forecastGeneration]).filter(value => value != null)
  const minData = Math.min(...values)
  const maxData = Math.max(...values, 1)
  const axisPadding = Math.max((maxData - minData) * .1, 500)
  const axisMin = Math.max(0, Math.floor((minData - axisPadding) / 500) * 500)
  const axisMax = Math.ceil((maxData + axisPadding) / 500) * 500
  const x = index => pad.left + (index / Math.max(points.length - 1, 1)) * (width - pad.left - pad.right)
  const y = value => height - pad.bottom - ((value - axisMin) / Math.max(axisMax - axisMin, 1)) * (height - pad.top - pad.bottom)
  const path = key => {
    let drawing = false
    return points.map((record, index) => {
      if (record[key] == null) { drawing = false; return null }
      const command = drawing ? 'L' : 'M'
      drawing = true
      return `${command} ${x(index).toFixed(1)} ${y(record[key]).toFixed(1)}`
    }).filter(Boolean).join(' ')
  }
  const grid = [0, .25, .5, .75, 1]
  const markers = key => points.map((record, index) => record[key] == null ? null : <circle key={`${key}-${record.startTime}`} cx={x(index)} cy={y(record[key])} r="3.5" className={`${key === 'forecastGeneration' ? 'forecast' : 'actual'}-marker`}><title>{`${dateTime(record.startTime)}\nActual generation: ${number(record.actualGeneration)} MW\nSelected forecast: ${number(record.forecastGeneration)} MW\nForecast error: ${number(record.error)} MW`}</title></circle>)
  const tickCount = Math.min(8, points.length)
  const tickIndices = Array.from({ length: tickCount }, (_, index) => Math.round(index * (points.length - 1) / Math.max(tickCount - 1, 1)))
  const singleDay = points[0]?.startTime?.slice(0, 10) === points[points.length - 1]?.startTime?.slice(0, 10)
  const time = value => new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'UTC' }).format(new Date(value))
  const tickLabel = value => singleDay ? time(value) : `${day(value)} ${time(value)}`
  return <div className="chart-wrap">
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Actual and forecast wind generation over time">
      <g className="chart-grid">{grid.map(value => { const tick = axisMin + (axisMax - axisMin) * value; return <g key={value}><line x1={pad.left} x2={width - pad.right} y1={y(tick)} y2={y(tick)} /><text x={pad.left - 12} y={y(tick) + 4} textAnchor="end">{number(tick)} MW</text></g> })}</g>
      <path className="chart-line forecast-line" d={path('forecastGeneration')} />
      <path className="chart-line actual-line" d={path('actualGeneration')} />
      <g>{markers('forecastGeneration')}{markers('actualGeneration')}</g>
    </svg>
    <div className="chart-axis" style={{ gridTemplateColumns: `repeat(${tickCount}, minmax(0, 1fr))` }}>{tickIndices.map((index, tick) => <span key={`${points[index].startTime}-${tick}`} className={tick === 0 ? 'first' : tick === tickIndices.length - 1 ? 'last' : ''}>{tickLabel(points[index].startTime)}</span>)}</div>
  </div>
}

function Analysis({ records, start, end }) {
  const [sort, setSort] = useState('startTime')
  const [vintageDate, setVintageDate] = useState(start)
  const [vintages, setVintages] = useState(null)
  const [vintageError, setVintageError] = useState('')
  const [vintagesLoading, setVintagesLoading] = useState(false)
  const vintageRequest = useRef(null)
  useEffect(() => {
    vintageRequest.current?.abort()
    setVintageDate(start)
    setVintages(null)
    setVintageError('')
    setVintagesLoading(false)
  }, [start])
  useEffect(() => () => vintageRequest.current?.abort(), [])
  const sorted = useMemo(() => [...records].sort((a, b) => {
    if (sort !== 'error') return new Date(a.startTime) - new Date(b.startTime)
    if (a.error == null) return b.error == null ? 0 : 1
    if (b.error == null) return -1
    return Math.abs(b.error) - Math.abs(a.error)
  }), [records, sort])
  const loadVintages = async () => {
    vintageRequest.current?.abort()
    const controller = new AbortController()
    vintageRequest.current = controller
    setVintagesLoading(true); setVintageError('')
    try {
      const nextVintages = await request(`/api/forecasts/vintages?delivery_date=${vintageDate}`, controller.signal)
      if (!controller.signal.aborted) setVintages(nextVintages)
    } catch (error) {
      if (error.name !== 'AbortError' && !controller.signal.aborted) setVintageError(error.message)
    } finally {
      if (!controller.signal.aborted) setVintagesLoading(false)
    }
  }
  return <><section className="panel table-panel"><div className="panel-heading"><div><div className="eyebrow">PERIOD-LEVEL DETAIL</div><h2>Forecast observations</h2><p className="panel-subtitle">{number(records.length)} delivery periods in selected window</p></div><a className="export-button" href={`${API_BASE}/api/export/csv?start_date=${start}&end_date=${end}`}>↓ Export CSV</a></div><div className="table-scroll"><table><thead><tr><th>Delivery period <button onClick={() => setSort('startTime')}>↕</button></th><th>Forecast published</th><th>Forecast ({unit})</th><th>Actual ({unit})</th><th><button onClick={() => setSort('error')}>Error ({unit}) ↕</button></th><th>Absolute error</th></tr></thead><tbody>{sorted.slice(0, 200).map((record, index) => <tr key={`${record.startTime}-${index}`}><td className="strong">{dateTime(record.startTime)}</td><td>{dateTime(record.publishTime)}</td><td>{number(record.forecastGeneration)}</td><td>{number(record.actualGeneration)}</td><td className={record.error > 0 ? 'positive' : record.error < 0 ? 'negative' : ''}>{number(record.error)}</td><td>{number(record.absoluteError)}</td></tr>)}</tbody></table>{!sorted.length && <EmptyState message="No records match the selected delivery window." />}</div>{records.length > 200 && <div className="table-foot">Showing first 200 periods. Use CSV export for the complete result.</div>}</section><section className="panel vintages-panel"><div className="panel-heading"><div><div className="eyebrow">FORECAST HISTORY</div><h2>Inspect forecast vintages</h2><p className="panel-subtitle">Publication history for a delivery date. Later versions may contain information unavailable at decision time.</p></div><div className="vintage-control"><label htmlFor="vintage-date">Delivery date</label><input id="vintage-date" type="date" min={start} max={end} value={vintageDate} onChange={event => { vintageRequest.current?.abort(); setVintagesLoading(false); setVintageDate(event.target.value); setVintages(null); setVintageError('') }} /><button className="primary-button" onClick={loadVintages} disabled={vintagesLoading}>{vintagesLoading ? 'Loading…' : 'Load vintages'}</button></div></div>{vintageError && <div className="inline-error">{vintageError}</div>}{vintages && <div className="table-scroll"><table><thead><tr><th>Delivery timestamp</th><th>Published timestamp</th><th>Forecast ({unit})</th></tr></thead><tbody>{vintages.map((vintage, index) => <tr key={`${vintage.publishTime}-${index}`}><td className="strong">{dateTime(vintage.startTime)}</td><td>{dateTime(vintage.publishTime)}</td><td>{number(vintage.generation)}</td></tr>)}</tbody></table></div>}</section></>
}

function Accuracy({ accuracy }) {
  const metrics = accuracy?.overall
  return <><section className="kpi-grid accuracy-kpis"><Kpi label="MAE" value={number(metrics?.mae)} suffix={unit} detail="Average absolute error" accent="green" /><Kpi label="RMSE" value={number(metrics?.rmse)} suffix={unit} detail="Sensitivity to large misses" /><Kpi label="Forecast bias" value={number(metrics?.bias)} suffix={unit} detail="Forecast minus actual" accent="amber" /><Kpi label="Largest miss" value={number(metrics?.maxAbsoluteError)} suffix={unit} detail={metrics?.maxAbsoluteErrorAt ? `At ${dateTime(metrics.maxAbsoluteErrorAt)}` : 'Maximum absolute error'} /></section><section className="panel table-panel"><div className="panel-heading"><div><div className="eyebrow">DAILY BREAKDOWN</div><h2>Accuracy by day</h2></div><div className="metric-note">Lower MAE indicates closer forecasts</div></div><div className="table-scroll"><table><thead><tr><th>Date</th><th>MAE ({unit})</th><th>RMSE ({unit})</th><th>Bias ({unit})</th><th>Matched periods</th></tr></thead><tbody>{(accuracy?.daily || []).map((row, index) => { const metricsForDay = row.metrics || row; return <tr key={row.date || index}><td className="strong">{day(row.date)}</td><td>{number(metricsForDay.mae)}</td><td>{number(metricsForDay.rmse)}</td><td className={metricsForDay.bias > 0 ? 'positive' : metricsForDay.bias < 0 ? 'negative' : ''}>{number(metricsForDay.bias)}</td><td>{number(metricsForDay.matchedPeriods)}</td></tr> })}</tbody></table>{!accuracy?.daily?.length && <EmptyState message="Daily accuracy is unavailable for this window." />}</div></section></>
}

function Quality({ quality, health, summary }) {
  const cards = [['API service', health?.status === 'ok' ? 'Operational' : 'Unavailable', health?.service || 'Backend health'], ['Cache status', health?.cacheStatus || '—', 'Data cache availability'], ['Observed periods', `${number(quality?.observedPeriods)} / ${number(quality?.expectedPeriods)}`, 'Observed hourly comparison periods'], ['Missing actuals', number(quality?.missingActualPeriods), 'No value returned'], ['Missing forecasts', number(quality?.missingEligibleForecastPeriods), 'No eligible forecast returned'], ['Last retrieval', dateTime(quality?.retrievedAt || summary?.latestSuccessfulRetrieval), 'UTC timestamp'] ]
  return <><section className="quality-grid">{cards.map(([label, value, detail]) => <article className="quality-card" key={label}><div className="kpi-label">{label}<span className={label === 'API service' && health?.status === 'ok' ? 'status-check' : 'kpi-dot'}>{label === 'API service' && health?.status === 'ok' ? '✓' : ''}</span></div><strong>{value}</strong><span>{detail}</span></article>)}</section><section className="panel quality-note"><div className="note-icon">i</div><div><h2>How to read data quality</h2><p>Missing observations are excluded from accuracy calculations; they are never treated as zero. A valid zero-generation value remains part of the analysis.</p></div></section></>
}

function LoadingState() { return <div className="loading-state"><div className="loader" /><h2>Loading live analysis</h2><p>Retrieving wind generation and forecast data from the backend.</p></div> }
function ErrorState({ message, onRetry }) { return <div className="state-card error-state"><div className="state-icon">!</div><h2>Could not load analysis</h2><p>{message || 'The backend is unavailable. Check that FastAPI is running and try again.'}</p><button className="primary-button" onClick={onRetry}>Retry connection</button></div> }
function EmptyState({ message }) { return <div className="empty-state">{message}</div> }

createRoot(document.getElementById('root')).render(<App />)
