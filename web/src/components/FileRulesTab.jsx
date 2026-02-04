import React, { useState, useEffect } from 'react';

function FileRulesTab({ file, apiBase }) {
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!file.transcribed) return;
    setLoading(true);
    fetch(`${apiBase}/files/${file.filename}/transcript`)
      .then(res => res.json())
      .then(data => {
        // Only show items that are either blocked or have been allowed (i.e. relevant to filtering)
        // Or should we show EVERYTHING? No, that's too much.
        // We only care about things that matched the blocklist.
        // The API returns intervals. Some are is_allowed=True (whitelist match/override) or False (blocked).
        // Let's filter to show only "interesting" ones?
        // Actually, the API logic returns intervals. For long audiobooks, this list will be HUGE if we return "silence" intervals. 
        // Wait, `determine_intervals` in censor.py ONLY returns matches from blocklist.
        // So `final_intervals` contains overlaps of blocklist vs allowlist.
        // So everything in `final_intervals` is a match of some sort.
        // So we can show all of them.
        setMatches(data.intervals);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, [file, apiBase]);

  const toggleOverride = async (match, newAllowedState) => {
      // Optimistic update
      const newMatches = matches.map(m => {
          if (m.start === match.start) {
              return { ...m, is_allowed: newAllowedState };
          }
          return m;
      });
      setMatches(newMatches);

      // Send to API
      await fetch(`${apiBase}/files/${file.filename}/overrides`, {
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

  if (loading) return <div>Loading mathces...</div>;

  return (
    <div>
        <h2>Detected Matches</h2>
        <div className="rules-list">
            {matches.length === 0 && <p>No blocklist matches found.</p>}
            {matches.map((match, idx) => (
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
    </div>
  );
}

export default FileRulesTab;
