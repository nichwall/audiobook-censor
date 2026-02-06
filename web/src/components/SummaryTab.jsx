import React, { useState } from 'react';

function SummaryTab({ file, apiBase, onUpdate }) {
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  const handleTranscribe = async () => {
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

  const handlePrepare = async () => {
    setLoading(true);
    setMsg("Updating matches...");
    try {
        await fetch(`${apiBase}/files/${file.filename}/prepare-censor`, { method: 'POST' });
        setMsg("Matches updated! You can review them in 'File Rules' or 'Word Search'.");
        onUpdate();
    } catch (e) {
        setMsg("Error updating matches: " + e.message);
    } finally {
        setLoading(false);
    }
  };

  const handleCensor = async () => {
    setLoading(true);
    setMsg("Censoring... This takes a few minutes for long files.");
    try {
        await fetch(`${apiBase}/files/${file.filename}/censor`, { method: 'POST' });
        setMsg("Censoring complete! Output file is in the 'output' directory.");
        onUpdate();
    } catch (e) {
        setMsg("Error censoring: " + e.message);
    } finally {
        setLoading(false);
    }
  };

  return (
    <div>
      <h2 style={{marginTop: 0}}>{file.filename}</h2>
      
      <div className="card">
        {msg && <div style={{marginBottom: 16, color: 'var(--accent-primary)'}}>{msg}</div>}
        
        <div style={{display: 'flex', gap: 16, flexWrap: 'wrap'}}>
          {!file.transcribed && (
            <button 
                className="btn btn-primary" 
                onClick={handleTranscribe}
                disabled={loading}
            >
                Start Transcription
            </button>
          )}
          
          <button 
            className="btn btn-secondary"
            onClick={handlePrepare}
            disabled={loading || !file.transcribed}
            title="Update matches from blocklist/allowlist (Fast)"
          >
            Update Matches
          </button>

          <button 
            className="btn btn-primary"
            onClick={handleCensor}
            disabled={loading || !file.transcribed}
            title="Generate censored audio file (Slow)"
          >
            Run Censoring
          </button>
        </div>
      </div>

      <div className="stat-grid">
        <div className="stat-item">
            <div className="stat-label">Duration</div>
            <div className="stat-value">
              {file.duration ? (() => {
                const totalSeconds = Math.floor(file.duration);
                const h = Math.floor(totalSeconds / 3600);
                const m = Math.floor((totalSeconds % 3600) / 60);
                const s = totalSeconds % 60;
                return `${h}h ${m}m ${s}s`;
              })() : "Unknown"}
            </div>
        </div>

        {/* Transcription Combined Status */}
        <div className="stat-item">
            <div className="stat-label">Transcription (~7-8%)</div>
            {file.duration ? (() => {
                const est = Math.floor(file.duration * 0.08);
                const h = Math.floor(est / 3600);
                const m = Math.floor((est % 3600) / 60);
                const s = est % 60;
                const timeStr = (h > 0) ? `${h}h ${m}m` : `${m}m ${s}s`;

                if (!file.transcribed) {
                    return (
                        <div>
                            <div style={{fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 4}}>Incomplete</div>
                            <div className="stat-value">Est: {timeStr}</div>
                        </div>
                    );
                } else {
                     return (
                        <div>
                            <div style={{fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 4}}>Est: {timeStr}</div>
                            <div className="stat-value" style={{color: 'var(--success)'}}>Complete</div>
                        </div>
                    );
                }
            })() : <div className="stat-value">-</div>}
        </div>

        {/* Censoring Combined Status */}
        <div className="stat-item">
            <div className="stat-label">Censoring (~3%)</div>
             {file.duration ? (() => {
                const est = Math.floor(file.duration * 0.03);
                const h = Math.floor(est / 3600);
                const m = Math.floor((est % 3600) / 60);
                const s = est % 60;
                const timeStr = (h > 0) ? `${h}h ${m}m` : `${m}m ${s}s`;

                if (!file.censored) {
                    return (
                        <div>
                            <div style={{fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 4}}>Incomplete</div>
                            <div className="stat-value">Est: {timeStr}</div>
                        </div>
                    );
                } else {
                     return (
                        <div>
                            <div style={{fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 4}}>Est: {timeStr}</div>
                            <div className="stat-value" style={{color: 'var(--success)'}}>Complete</div>
                        </div>
                    );
                }
            })() : <div className="stat-value">-</div>}
        </div>
        
        {/* Total Est Remaining */}
         <div className="stat-item">
              <div className="stat-label">Total Est. Remaining</div>
              <div className="stat-value">
                  {file.duration ? (() => {
                      let total = 0;
                      if (!file.transcribed) total += file.duration * 0.08;
                      if (!file.censored) total += file.duration * 0.03;
                      
                      if (total === 0) return <span style={{color: 'var(--success)'}}>Done</span>;

                      const est = Math.floor(total);
                      const h = Math.floor(est / 3600);
                      const m = Math.floor((est % 3600) / 60);
                      if (h > 0) return `${h}h ${m}m`;
                      return `${m}m`;
                  })() : "?"}
              </div>
          </div>
      </div>
    </div>
  );
}

export default SummaryTab;
