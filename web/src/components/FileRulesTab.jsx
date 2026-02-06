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

  const toggleGroupOverride = async (group, newAllowedState) => {
      // Optimistic update
      setGroups(prevGroups => prevGroups.map(g => {
          if (g.phrase !== group.phrase) return g;
          return {
              ...g,
              matches: g.matches.map(m => ({ ...m, is_allowed: newAllowedState }))
          };
      }));

      // Send to API
      await fetch(`${apiBase}/files/${encodeURIComponent(file.filename)}/overrides/bulk`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
              overrides: group.matches.map(m => ({ start_time: m.start, allow: newAllowedState }))
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
            {groups.map((group) => {
                const allAllowed = group.matches.every(m => m.is_allowed);
                return (
                    <details key={group.phrase} className="rule-group">
                        <summary className="rule-group-summary" style={{display: 'flex', alignItems: 'center', gap: 16}}>
                            <span className="group-phrase" style={{flex: 1}}>"{group.phrase}"</span>
                            <span className="group-count" style={{color: 'var(--text-secondary)', fontSize: '0.9em', whiteSpace: 'nowrap'}}>
                                {group.count} instances
                            </span>
                            <div style={{display: 'flex', alignItems: 'center', gap: 8}} onClick={(e) => e.stopPropagation()}>
                                <span style={{fontSize: '0.7em', fontWeight: 'bold', color: 'var(--text-secondary)'}}>ALL</span>
                                <label className="toggle-switch small">
                                    <input 
                                        type="checkbox" 
                                        checked={allAllowed}
                                        onChange={(e) => toggleGroupOverride(group, e.target.checked)}
                                    />
                                    <span className="slider"></span>
                                </label>
                            </div>
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
                );
            })}
        </div>
    </div>
  );
}

export default FileRulesTab;
