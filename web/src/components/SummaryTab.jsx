import React, { useState } from 'react';

function SummaryTab({ file, apiBase, onUpdate }) {
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  const handleRunAll = async () => {
    const est = (file.duration || 0) * (0.08 + 0.03);
    if (est > 10) {
      if (!window.confirm(`This full workflow will take approximately ${getTimeStr(est)}. Continue?`)) return;
    }

    setLoading(true);
    setMsg("Starting full workflow...");
    try {
      setMsg("Step 1/3: Transcribing...");
      await fetch(`${apiBase}/files/${file.filename}/transcribe`, { method: 'POST' });
      setMsg("Step 2/3: Preparing matches...");
      await fetch(`${apiBase}/files/${file.filename}/prepare-censor`, { method: 'POST' });
      setMsg("Step 3/3: Censoring...");
      await fetch(`${apiBase}/files/${file.filename}/censor`, { method: 'POST' });
      setMsg("Full workflow complete!");
      onUpdate();
    } catch (e) {
      setMsg("Error in workflow: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  const handlePrepare = async () => {
    setLoading(true);
    setMsg("Updating matches...");
    try {
        await fetch(`${apiBase}/files/${file.filename}/prepare-censor`, { method: 'POST' });
        setMsg("Matches updated!");
        onUpdate();
    } catch (e) {
        setMsg("Error updating matches: " + e.message);
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
    setMsg("Censoring...");
    try {
        await fetch(`${apiBase}/files/${file.filename}/censor`, { method: 'POST' });
        setMsg("Censoring complete!");
        onUpdate();
    } catch (e) {
        setMsg("Error censoring: " + e.message);
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
    setMsg("Transcribing... This may take a while.");
    try {
      await fetch(`${apiBase}/files/${file.filename}/transcribe`, { method: 'POST' });
      setMsg("Transcription complete!");
      onUpdate();
    } catch (e) {
      setMsg("Error transcribing: " + e.message);
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

  const statItemStyle = (isClickable) => ({
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    cursor: isClickable && !loading ? 'pointer' : 'default',
    opacity: loading ? 0.7 : 1,
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
    if (isEnabled && !loading) {
      handler();
    }
  };

  return (
    <div>
      <h2 style={{marginTop: 0}}>{file.filename}</h2>
      
      {msg && <div className="card" style={{marginBottom: 20, color: 'var(--accent-primary)', fontWeight: 'bold'}}>{msg}</div>}

      <div className="stat-grid">
        {/* Box 1: Duration & Run All */}
        <button 
            className="stat-item clickable-stat" 
            style={statItemStyle(!file.transcribed)}
            onClick={() => handleItemClick(handleRunAll, !file.transcribed)}
            disabled={loading || file.transcribed}
        >
            <div>
                <div className="stat-label">Duration</div>
                <div className="stat-value">{file.duration ? formatDuration(file.duration) : "Unknown"}</div>
            </div>
            {!file.transcribed && (
                <div style={{marginTop: 12, color: 'var(--accent-primary)', fontWeight: 'bold', fontSize: '0.9rem'}}>
                    → Run All Steps
                </div>
            )}
        </button>

        {/* Box 2: Transcription */}
        <button 
            className="stat-item clickable-stat" 
            style={statItemStyle(!file.transcribed)}
            onClick={() => handleItemClick(handleTranscribe, !file.transcribed)}
            disabled={loading || file.transcribed}
        >
            <div className="stat-label">1. Transcription</div>
            <div style={{marginTop: 12}}>
                {file.transcribed ? (
                    <div style={{color: 'var(--success)', fontWeight: 'bold', fontSize: '1.2rem'}}>✓ Complete</div>
                ) : (
                    <div className="stat-value" style={{fontSize: '1.2rem'}}>
                        Start Transcription
                        <div style={{fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 'normal', marginTop: 4}}>
                            (~{file.duration ? getTimeStr(file.duration * 0.08) : "?"})
                        </div>
                    </div>
                )}
            </div>
        </button>

        {/* Box 3: Update Matches */}
        <button 
            className="stat-item clickable-stat" 
            style={statItemStyle(file.transcribed)}
            onClick={() => handleItemClick(handlePrepare, file.transcribed)}
            disabled={loading || !file.transcribed}
        >
            <div className="stat-label">2. Rule Matching</div>
            <div style={{marginTop: 12}}>
                <div className="stat-value" style={{fontSize: '1.2rem'}}>Update Matches</div>
                <div style={{fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 4, fontWeight: 'normal'}}>
                    Refreshes in seconds
                </div>
            </div>
        </button>

        {/* Box 4: Censoring */}
        <button 
            className="stat-item clickable-stat" 
            style={statItemStyle(file.transcribed && (!file.censored || file.is_out_of_date))}
            onClick={() => handleItemClick(handleCensor, file.transcribed && (!file.censored || file.is_out_of_date))}
            disabled={loading || !file.transcribed || (file.censored && !file.is_out_of_date)}
        >
            <div className="stat-label">3. Censoring</div>
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
                        {file.is_out_of_date ? "Regenerate" : "Start Censoring"}
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
