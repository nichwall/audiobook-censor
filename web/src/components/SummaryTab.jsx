import React, { useState } from 'react';

function SummaryTab({ file, apiBase, onUpdate, jobStatus }) {
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  const currentJob = jobStatus.current && jobStatus.current.file_id === file.id ? jobStatus.current : null;
  const queuedJob = !currentJob ? jobStatus.queue.find(q => q.file_id === file.id) : null;
  const anyJobRunning = !!jobStatus.current;
  const isThisFileBusy = !!(currentJob || queuedJob);

  const handleRunAll = async () => {
    const est = (file.duration || 0) * (0.08 + 0.03);
    if (est > 10) {
      if (!window.confirm(`This full workflow will take approximately ${getTimeStr(est)}. Continue?`)) return;
    }

    setLoading(true);
    setMsg("Enqueuing full workflow...");
    try {
      // For Run All, we'll enqueue both steps
      await fetch(`${apiBase}/files/${file.id}/transcribe`, { method: 'POST' });
      await fetch(`${apiBase}/files/${file.id}/censor`, { method: 'POST' });
      setMsg("Full workflow enqueued!");
      onUpdate();
    } catch (e) {
      setMsg("Error enqueuing workflow: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCensor = async () => {
    const est = (file.duration || 0) * 0.03;
    if (est > 10) {
      if (!window.confirm(`Censoring will take approximately ${getTimeStr(est)}. Continue?`)) return;
    }

    setLoading(true);
    setMsg("Enqueuing censoring task...");
    try {
        await fetch(`${apiBase}/files/${file.id}/censor`, { method: 'POST' });
        setMsg("Censoring task enqueued!");
        onUpdate();
    } catch (e) {
        setMsg("Error enqueuing censor: " + e.message);
    } finally {
        setLoading(false);
    }
  };

  const handleTranscribe = async () => {
    const est = (file.duration || 0) * 0.08;
    if (est > 10) {
      if (!window.confirm(`Transcription will take approximately ${getTimeStr(est)}. Continue?`)) return;
    }

    setLoading(true);
    setMsg("Enqueuing transcription task...");
    try {
      await fetch(`${apiBase}/files/${file.id}/transcribe`, { method: 'POST' });
      setMsg("Transcription task enqueued!");
      onUpdate();
    } catch (e) {
      setMsg("Error enqueuing transcribe: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  const formatDuration = (seconds) => {
    const totalSeconds = Math.floor(seconds);
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;
    if (h > 0) return `${h}h ${m}m ${s}s`;
    return `${m}m ${s}s`;
  };

  const getTimeStr = (seconds) => {
    const totalSeconds = Math.floor(seconds);
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;
    
    let parts = [];
    if (h > 0) parts.push(`${h}h`);
    if (m > 0 || h > 0) parts.push(`${m}m`);
    parts.push(`${s}s`);
    return parts.join(' ');
  };

  const formatTime = (timestamp) => {
      if (!timestamp) return "N/A";
      const date = new Date(timestamp * 1000);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const getEstimatedEndTime = (job) => {
      if (!job || !job.started_at || !job.duration) return null;
      const factor = job.type === 'transcribe' ? 0.08 : (job.type === 'censor' ? 0.03 : 0.01);
      return job.started_at + (job.duration * factor);
  };

  const statItemStyle = (isClickable) => ({
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    cursor: isClickable && !loading && !anyJobRunning ? 'pointer' : 'default',
    opacity: loading || (anyJobRunning && !isClickable) ? 0.7 : 1,
    transition: 'all 0.2s',
    border: '1px solid transparent',
    textAlign: 'left',
    width: '100%',
    padding: '16px',
    borderRadius: '8px',
    backgroundColor: 'var(--bg-tertiary)',
    color: 'var(--text-primary)',
    fontFamily: 'inherit'
  });

  const handleItemClick = (handler, isEnabled) => {
    if (isEnabled && !loading && !anyJobRunning) {
      handler();
    }
  };

  return (
    <div>
      <h2 style={{marginTop: 0}}>{file.filename}</h2>
      
      {msg && <div className="card" style={{marginBottom: 20, color: 'var(--accent-primary)', fontWeight: 'bold'}}>{msg}</div>}

      {/* Global Job Status Indicator */}
      {jobStatus.current && (
          <div className="card" style={{marginBottom: 20, display: 'flex', alignItems: 'center', gap: 12, borderLeft: '4px solid var(--accent-primary)'}}>
              <div className="spinner"></div>
              <div style={{flex: 1}}>
                  <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                      <strong>Currently {jobStatus.current.type === 'transcribe' ? 'Transcribing' : 'Censoring'}:</strong>
                      <span style={{fontSize: '0.8rem', color: 'var(--text-secondary)'}}>{jobStatus.current.filename}</span>
                  </div>
                  <div style={{display: 'flex', gap: 16, marginTop: 8, fontSize: '0.85rem'}}>
                      <div><span style={{color: 'var(--text-secondary)'}}>Started:</span> {formatTime(jobStatus.current.started_at)}</div>
                      {jobStatus.current.duration && (
                          <div><span style={{color: 'var(--text-secondary)'}}>Est. End:</span> {formatTime(getEstimatedEndTime(jobStatus.current))}</div>
                      )}
                  </div>
                  {jobStatus.queue.length > 0 && (
                      <div style={{fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 8, borderTop: '1px solid var(--border-color)', paddingTop: 8}}>
                          Next in queue: {jobStatus.queue[0].filename} ({jobStatus.queue.length} more)
                      </div>
                  )}
              </div>
          </div>
      )}

      {queuedJob && !currentJob && (
          <div className="card" style={{marginBottom: 20, color: 'var(--text-secondary)'}}>
              ⌛ This file is waiting in the queue...
          </div>
      )}

      <div className="stat-grid">
        {/* Box 1: Duration & Run All */}
        <button 
            className="stat-item clickable-stat" 
            style={statItemStyle(!file.transcribed)}
            onClick={() => handleItemClick(handleRunAll, !file.transcribed)}
            disabled={loading || anyJobRunning || file.transcribed}
        >
            <div>
                <div className="stat-label">Duration</div>
                <div className="stat-value">{file.duration ? formatDuration(file.duration) : "Unknown"}</div>
            </div>
            {!file.transcribed && (
                <div style={{marginTop: 12, color: 'var(--accent-primary)', fontWeight: 'bold', fontSize: '0.9rem'}}>
                    {anyJobRunning ? 'Busy...' : '→ Run All Steps'}
                </div>
            )}
        </button>

        {/* Box 2: Transcription */}
        <button 
            className="stat-item clickable-stat" 
            style={statItemStyle(!file.transcribed)}
            onClick={() => handleItemClick(handleTranscribe, !file.transcribed)}
            disabled={loading || anyJobRunning || file.transcribed}
        >
            <div className="stat-label">1. Transcription</div>
            <div style={{marginTop: 12}}>
                {file.transcribed ? (
                    <div style={{color: 'var(--success)', fontWeight: 'bold', fontSize: '1.2rem'}}>✓ Complete</div>
                ) : (
                    <div className="stat-value" style={{fontSize: '1.2rem'}}>
                        {isThisFileBusy ? 'In Progress...' : 'Start Transcription'}
                        <div style={{fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 'normal', marginTop: 4}}>
                            (~{file.duration ? getTimeStr(file.duration * 0.08) : "?"})
                        </div>
                    </div>
                )}
            </div>
        </button>

        {/* Box 3: Censoring */}
        <button 
            className="stat-item clickable-stat" 
            style={statItemStyle(file.transcribed && (!file.censored || file.is_out_of_date))}
            onClick={() => handleItemClick(handleCensor, file.transcribed && (!file.censored || file.is_out_of_date))}
            disabled={loading || anyJobRunning || !file.transcribed || (file.censored && !file.is_out_of_date)}
        >
            <div className="stat-label">2. Censoring</div>
            <div style={{marginTop: 12}}>
                {file.censored && !file.is_out_of_date ? (
                    <div style={{color: 'var(--success)', fontWeight: 'bold'}}>
                        <div style={{fontSize: '1.2rem'}}>✓ Up to Date</div>
                        <div style={{fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 'normal', marginTop: 4}}>
                            Censored audio is current
                        </div>
                    </div>
                ) : (
                    <div className="stat-value" style={{fontSize: '1.2rem'}}>
                        {isThisFileBusy ? 'In Progress...' : (file.is_out_of_date ? "Regenerate" : "Start Censoring")}
                        <div style={{fontSize: '0.8rem', color: (file.is_out_of_date ? 'var(--warning)' : 'var(--text-secondary)'), fontWeight: 'normal', marginTop: 4}}>
                            ~{file.duration ? getTimeStr(file.duration * 0.03) : "?"} 
                            {file.is_out_of_date ? " (Out of Date)" : ""}
                        </div>
                    </div>
                )}
            </div>
        </button>
      </div>
    </div>
  );
}

export default SummaryTab;
