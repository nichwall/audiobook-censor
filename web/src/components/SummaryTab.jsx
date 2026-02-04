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

  const handleCensor = async () => {
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

  return (
    <div>
      <h2 style={{marginTop: 0}}>{file.filename}</h2>
      
      <div className="card">
        <h3>Actions</h3>
        {msg && <div style={{marginBottom: 16, color: 'var(--accent-primary)'}}>{msg}</div>}
        
        <div style={{display: 'flex', gap: 16}}>
          <button 
            className="btn btn-primary" 
            onClick={handleTranscribe}
            disabled={loading}
          >
            {file.transcribed ? "Re-Transcribe" : "Start Transcription"}
          </button>
          
          <button 
            className="btn btn-primary"
            onClick={handleCensor}
            disabled={loading || !file.transcribed}
            style={{opacity: !file.transcribed ? 0.5 : 1}}
          >
            Start Censor
          </button>
        </div>
      </div>

      <div className="stat-grid">
        <div className="stat-item">
            <div className="stat-label">File Size</div>
            <div className="stat-value">{(file.size_bytes / 1024 / 1024).toFixed(2)} MB</div>
        </div>
        <div className="stat-item">
            <div className="stat-label">Transcribed</div>
            <div className="stat-value" style={{color: file.transcribed ? 'var(--success)' : 'var(--text-secondary)'}}>
                {file.transcribed ? "Yes" : "No"}
            </div>
        </div>
        <div className="stat-item">
             <div className="stat-label">Censored</div>
             <div className="stat-value" style={{color: file.censored ? 'var(--success)' : 'var(--text-secondary)'}}>
                 {file.censored ? "Yes" : "No"}
             </div>
        </div>
      </div>
      
      {file.transcribed && (
          <div className="card">
              <h3>Estimates</h3>
              <p>Transcription already done.</p>
              <p>Censoring usually takes about 10% of audio duration.</p>
          </div>
      )}
    </div>
  );
}

export default SummaryTab;
