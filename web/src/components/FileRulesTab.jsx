import React, { useState, useEffect } from 'react';

function FileRulesTab({ file, apiBase }) {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!file.transcribed) return;
    setLoading(true);
    fetch(`${apiBase}/files/${encodeURIComponent(file.filename)}/transcript`)
      .then(res => res.json())
      .then(data => {
        setGroups(data.groups || []);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, [file, apiBase]);

  const toggleOverride = async (match, newAllowedState) => {
      // Optimistic update
      setGroups(prevGroups => prevGroups.map(group => {
          if (group.phrase !== match.phrase) return group;
          
          return {
              ...group,
              matches: group.matches.map(m => {
                  if (m.start === match.start) {
                      return { ...m, is_allowed: newAllowedState };
                  }
                  return m;
              })
          };
      }));

      // Send to API
      await fetch(`${apiBase}/files/${encodeURIComponent(file.filename)}/overrides`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
              start_time: match.start,
              allow: newAllowedState
          })
      });
  };

  if (!file.transcribed) {
      return (
          <div className="card">
              <h3>Not Transcribed</h3>
              <p>Please transcribe the file first to view matches.</p>
          </div>
      );
  }

  if (loading) return <div>Loading rules...</div>;

  return (
    <div>
        <h2>File Rules</h2>
        <div className="rules-list">
            {groups.length === 0 && <p>No rules found.</p>}
            {groups.map((group) => (
                <details key={group.phrase} className="rule-group">
                    <summary className="rule-group-summary">
                        <span className="group-phrase">"{group.phrase}"</span>
                        <span className="group-count">{group.count} instances</span>
                    </summary>
                    <div className="rule-group-content">
                        {group.matches.map((match, idx) => (
                            <div key={idx} className={`rule-item ${match.is_allowed ? 'allowed' : 'blocked'}`}>
                                <div className="rule-text">
                                    <div className="rule-context" style={{color: 'var(--text-primary)'}}>
                                        ... {match.prefix} <span style={{
                                            color: match.is_allowed ? 'var(--success)' : 'var(--error)',
                                            fontWeight: 'bold'
                                        }}>{match.phrase}</span> {match.suffix} ...
                                    </div>
                                    <div style={{fontSize: '0.8em', marginTop: 4, color: 'var(--text-secondary)'}}>
                                        {match.is_allowed ? "ALLOWED" : "BLOCKED"} | Time: {match.start.toFixed(2)}s
                                    </div>
                                </div>
                                <label className="toggle-switch">
                                    <input 
                                        type="checkbox" 
                                        checked={match.is_allowed}
                                        onChange={(e) => toggleOverride(match, e.target.checked)}
                                    />
                                    <span className="slider"></span>
                                </label>
                            </div>
                        ))}
                    </div>
                </details>
            ))}
        </div>
    </div>
  );
}

export default FileRulesTab;
