import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowDownToLine, ArrowRight, Check, ChevronLeft, ChevronRight, FileSpreadsheet, Layers3, LoaderCircle, Plus, RotateCcw, ShieldCheck, Sparkles, Upload, X } from 'lucide-react';
import { api } from './api';
import './styles.css';

const sample = 'ID,Name,Email,Notes\n1,John Doe,john.doe@example.com,Please contact john.doe@example.com\n2,Jane Smith,jane_smith@domain.com,New customer\n3,Alice Brown,alice.brown@website.org,Follow up next week\n4,Oliver Chen,oliver.chen@example.com,Preferred contact by email\n5,Mia Wilson,mia.wilson@domain.com,Account verified\n6,Noah Patel,noah.patel@website.org,Welcome email sent\n';

function App() {
  const [ready, setReady] = useState(false), [demo, setDemo] = useState(false);
  const [data, setData] = useState(null), [description, setDescription] = useState('');
  const [replacement, setReplacement] = useState('REDACTED'), [columns, setColumns] = useState([]);
  const [preview, setPreview] = useState(null), [busy, setBusy] = useState(''), [error, setError] = useState('');
  const [notice, setNotice] = useState(''), [drag, setDrag] = useState(false);
  const input = useRef(null);
  useEffect(() => { api('bootstrap/').then(d => { setDemo(d.demo_mode); setReady(true); }).catch(e => setError(e.message)); }, []);
  async function run(label, action) {
    setBusy(label); setError(''); setNotice('');
    try { await action(); } catch (e) { setError(e.message); } finally { setBusy(''); }
  }
  function invalidate(fn) { fn(); setPreview(null); setNotice(''); }
  async function upload(file) {
    if (!file || busy || !ready) return;
    await run('Uploading', async () => {
      if (!/\.(csv|xlsx|xls)$/i.test(file.name)) throw new Error('Choose a CSV, XLSX or XLS file.');
      if (file.size > 5 * 1024 * 1024) throw new Error('Choose a file smaller than 5 MB.');
      const form = new FormData(); form.append('file', file);
      const next = await api('datasets/', { method: 'POST', body: form });
      setData(next); setColumns([]); setPreview(null); setNotice('Your file is ready. Describe what you want to change.');
    });
  }
  function example(value) { invalidate(() => setDescription(value)); }
  async function generate(event) {
    event.preventDefault();
    await run('Finding matches', async () => {
      setPreview(null);
      const result = await api(`datasets/${data.id}/preview/`, { method: 'POST', body: JSON.stringify({ description, replacement, ...(columns.length ? { columns } : {}) }) });
      setPreview(result);
    });
  }
  const disabled = !!busy || !ready;
  return <div className="app">
    <header><a className="brand" href="/"><span className="brand-icon"><Layers3 size={21}/></span>pattern<span className="brand-light">studio</span><span className="beta">BETA</span></a><div className="header-right"><span className="status-dot"/>{demo ? 'Sample mode' : 'AI-powered workspace'}<span className="avatar">PS</span></div></header>
    <main>
      <div className="eyebrow">YOUR DATA, A LITTLE MORE HUMAN</div>
      <div className="hero"><div><h1>Text, transformed<span>.</span></h1><p>Describe the pattern. Preview the changes. Make your data work for you.</p></div><div className="privacy"><ShieldCheck size={18}/><span>Your file stays out of the AI.<small>Only your description and column names are sent.</small></span></div></div>
      {demo && <div className="demo-banner"><Sparkles size={16}/><span><strong>You’re in sample mode.</strong> Try emails, phone numbers or URLs. Connect an LLM API key on the server to unlock any description.</span></div>}
      {error && <div role="alert" className="message error">{error}<button aria-label="Dismiss error" onClick={() => setError('')}><X size={16}/></button></div>}
      {notice && <div role="status" className="message success"><Check size={16}/>{notice}</div>}
      <div className="workspace">
        <aside>
          <section className="card upload-card"><div className="section-title"><span className="step">01</span><h2>Add your data</h2></div>
            <input ref={input} type="file" accept=".csv,.xlsx,.xls" aria-label="Upload spreadsheet" hidden onChange={e => { upload(e.target.files?.[0]); e.target.value = ''; }}/>
            <button className={`drop-zone ${drag ? 'drag' : ''}`} disabled={disabled} onClick={() => input.current.click()} onDragOver={e => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={e => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files[0]); }}><span className="upload-icon"><Upload size={21}/></span><strong>{data ? 'Upload another file' : 'Drop your spreadsheet here'}</strong><span>or <b>browse files</b></span><small>CSV, XLSX or XLS · up to 5 MB</small></button>
            {!data && <button className="sample-button" disabled={disabled} onClick={() => upload(new File([sample], 'sample-contacts.csv', { type: 'text/csv' }))}>Just exploring? <b>Try sample data <ArrowRight size={13}/></b></button>}
            {data && <div className="file-chip"><FileSpreadsheet size={20}/><div><strong>{data.name}</strong><small>{data.row_count.toLocaleString()} rows · {data.columns.length} columns</small></div><button aria-label="Delete uploaded dataset" disabled={disabled} onClick={() => run('Deleting', async () => { await api(`datasets/${data.id}/delete/`, { method: 'POST' }); setData(null); setPreview(null); })}><X size={16}/></button></div>}
          </section>
          <section className="card"><div className="section-title"><span className="step">02</span><h2>Describe your change</h2><Sparkles size={16} className="muted"/></div>
            <form onSubmit={generate}><fieldset disabled={disabled || !data}>
              <label htmlFor="description">What should we find?</label><textarea id="description" maxLength={1000} rows={4} value={description} onChange={e => invalidate(() => setDescription(e.target.value))} placeholder="e.g. Find email addresses in the Email column" required/>
              <div className="examples"><button type="button" onClick={() => example('Find email addresses')}>Email addresses</button><button type="button" onClick={() => example('Find phone numbers')}>Phone numbers</button><button type="button" onClick={() => example('Find URLs')}>URLs</button></div>
              <label htmlFor="replacement">Replace with <span>optional</span></label><input id="replacement" maxLength={1000} value={replacement} onChange={e => invalidate(() => setReplacement(e.target.value))} placeholder="Leave empty to remove matches"/><p className="field-hint">Leave blank to remove matched text.</p>
              <label htmlFor="columns">Apply to columns</label><select id="columns" value={columns[0] || ''} onChange={e => invalidate(() => setColumns(e.target.value ? [e.target.value] : []))}><option value="">Let the description decide</option>{data?.columns.map(c => <option key={c} value={c}>{c}</option>)}</select>
              <button className="primary full" type="submit" disabled={!description.trim()}>{busy === 'Finding matches' ? <LoaderCircle className="spin" size={17}/> : <Sparkles size={17}/>} {busy === 'Finding matches' ? 'Finding matches…' : 'Preview changes'}<ArrowRight size={16}/></button>
            </fieldset></form>
          </section>
          <div className="note"><ShieldCheck size={16}/><p>Review before you replace.<br/>Your original data is kept so you can reset anytime.</p></div>
        </aside>
        <div className="data-area">
          <section className="card data-card"><div className="table-heading"><div><span className="tiny-label">WORKSPACE</span><h2>{data ? 'Your data' : 'A clean slate'}</h2></div><div className="table-actions">{data && <><button className="subtle" disabled={disabled || data.version === 0} onClick={() => run('Resetting', async () => { setData(await api(`datasets/${data.id}/reset/`, { method: 'POST' })); setPreview(null); setNotice('Original data restored.'); })}><RotateCcw size={14}/>Reset</button><a className="download" href={`/api/datasets/${data.id}/download/?format=csv`}><ArrowDownToLine size={15}/>CSV</a><a className="download" href={`/api/datasets/${data.id}/download/?format=xlsx`}>Excel</a></>}</div></div>
            {data ? <><div className="data-meta"><span className="pill">{data.version ? 'Updated' : 'Original'}</span><span>{data.row_count.toLocaleString()} rows</span><span>{data.columns.length} columns</span><span className="right-meta">Version {data.version}</span></div><div className="table-scroll"><table><thead><tr><th className="row-number">#</th>{data.columns.map(c => <th key={c}><span className="type-icon">Aa</span>{c}</th>)}</tr></thead><tbody>{data.rows.map((row, i) => <tr key={i}><td className="row-number">{(data.page - 1) * 100 + i + 1}</td>{row.map((cell, j) => <td key={j} title={cell == null ? 'Empty cell' : String(cell)}>{cell == null ? <span className="null">—</span> : String(cell)}</td>)}</tr>)}</tbody></table></div><div className="table-footer"><span>Showing {(data.page - 1) * 100 + 1}–{Math.min(data.page * 100, data.row_count)} of {data.row_count} rows</span><div><button aria-label="Previous page" disabled={disabled || data.page === 1} onClick={() => run('Loading page', async () => setData(await api(`datasets/${data.id}/?page=${data.page - 1}`)))}><ChevronLeft size={16}/></button><button aria-label="Next page" disabled={disabled || data.page * 100 >= data.row_count} onClick={() => run('Loading page', async () => setData(await api(`datasets/${data.id}/?page=${data.page + 1}`)))}><ChevronRight size={16}/></button></div></div></> : <div className="empty"><div className="sheet-art"><div className="sheet-art-top"><FileSpreadsheet size={22}/><span/><span/></div>{[0,1,2,3].map(r => <div className="sheet-art-row" key={r}><span/><span/><span/></div>)}<span className="sheet-plus"><Plus size={19}/></span></div><h3>A fresh start for your spreadsheet</h3><p>Upload a file to see your data here.<br/>A few words are all it takes to transform it.</p><button className="outline" disabled={disabled} onClick={() => upload(new File([sample], 'sample-contacts.csv'))}>Explore with sample data <ArrowRight size={15}/></button></div>}
          </section>
          {preview ? <section className="card preview-card"><div className="section-title"><span className="step">03</span><h2>Review your changes</h2><span className="match-count">{preview.matches} matches</span></div><div className="regex-label">GENERATED REGEX {preview.ignore_case && '· CASE INSENSITIVE'}</div><code>{preview.pattern}</code><p className="explanation">{preview.explanation}</p><div className="row-conditions"><strong>Rows to change: {preview.eligible_rows}</strong>{preview.row_filters?.length ? <><p>Only rows matching all of these conditions:</p>{preview.row_filters.map((filter, i) => <p key={i}><b>{filter.column}</b> matches <code>{filter.pattern}</code>{filter.ignore_case ? " (case insensitive)" : " (case sensitive)"}</p>)}</> : <p>All rows are eligible.</p>}</div><p className="field-hint">Columns: {preview.columns.join(', ')} · {preview.changed_cells} cells will change</p>{preview.changes.length > 0 ? <div className="diff-list">{preview.changes.slice(0, 6).map((c,i) => <div className="diff" key={i}><small>Row {c.row} · {c.column}</small><div><del>{c.before}</del><ArrowRight size={14}/><ins>{c.after || '(empty)'}</ins></div></div>)}</div> : <p>No data changes found. Try another description or column.</p>}{preview.changes.length > 6 && <p className="field-hint">Showing the first 6 changed cells. All {preview.changed_cells} changed cells will be applied.</p>}<div className="apply-footer"><span>Original data is preserved.</span><button className="primary" disabled={disabled || !preview.changed_cells} onClick={() => run('Applying', async () => { const next = await api(`datasets/${data.id}/apply/${preview.operation_id}/`, { method: 'POST' }); setData(next); setPreview(null); setNotice(`Done. Updated ${next.changed_cells} cells with ${next.matches} matches.`); })}><Check size={16}/>Apply replacements</button></div></section> : <div className="how-it-works"><span className="tiny-label">FROM MESSY TO MEANINGFUL</span><div><span><b>1</b>Upload a spreadsheet</span><ArrowRight size={15}/><span><b>2</b>Describe a pattern</span><ArrowRight size={15}/><span><b>3</b>Review & export</span></div></div>}
        </div>
      </div>
      <footer><span>Pattern Studio <span className="footer-divider">/</span> A little language. A lot less busywork.</span><span>CSV & Excel supported · 24-hour workspace access</span></footer>
      <div className="sr-only" role="status" aria-live="polite">{busy ? `${busy}…` : ''}</div>
    </main>
  </div>;
}
createRoot(document.getElementById('root')).render(<App/>);
