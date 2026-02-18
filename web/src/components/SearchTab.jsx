import React, { useState, useEffect, useMemo } from 'react';

function SearchTab({ file, apiBase, onUpdate }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [blocklist, setBlocklist] = useState([]);

  // Fetch blocklist
  const fetchBlocklist = async () => {
    try {
      const res = await fetch(`${apiBase}/config/global`);
      const config = await res.json();
      const list = (config.blocklist || "")
        .split('\n')
        .map(w => w.trim().toLowerCase())
        .filter(w => w);
      setBlocklist(list);
    } catch (e) {
      console.error("Error fetching blocklist:", e);
    }
  };

  useEffect(() => {
    fetchBlocklist();
  }, [apiBase]);

  // Real-time search with debounce
  useEffect(() => {
    if (!file.transcribed) return;
    
    const trimmed = query.trim();
    if (!trimmed) {
      setResults([]);
      return;
    }

    const timer = setTimeout(() => {
      setLoading(true);
      fetch(`${apiBase}/files/${file.id}/search?q=${encodeURIComponent(trimmed)}`)
        .then(res => res.json())
        .then(data => {
          setResults(data || []);
          setLoading(false);
        })
        .catch(err => {
          console.error(err);
          setLoading(false);
        });
    }, 300); // 300ms debounce

    return () => clearTimeout(timer);
  }, [query, file.id, apiBase, file.transcribed]);

  const handleAddToBlocklist = async (word) => {
    if (!word) return;
    setStatus(`Adding "${word}" to blocklist...`);
    try {
      const res = await fetch(`${apiBase}/config/global`);
      const config = await res.json();
      
      let currentBlocklistStr = config.blocklist || "";
      const words = currentBlocklistStr.split('\n').map(w => w.trim().toLowerCase());
      
      if (!words.includes(word.toLowerCase())) {
        const newBlocklist = currentBlocklistStr.trim() + (currentBlocklistStr ? "\n" : "") + word;
        
        await fetch(`${apiBase}/config/global`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...config, blocklist: newBlocklist })
        });
        setStatus(`"${word}" added to blocklist!`);
        if (onUpdate) onUpdate();
        fetchBlocklist(); // Refresh local list
      } else {
        setStatus(`"${word}" is already in blocklist.`);
      }
      
      setTimeout(() => setStatus(""), 3000);
    } catch (e) {
      console.error(e);
      setStatus("Error updating blocklist");
    }
  };

  const isBlocked = (text) => {
    if (!text) return false;
    return blocklist.includes(text.trim().toLowerCase());
  };

  const queryIsBlocked = useMemo(() => isBlocked(query), [query, blocklist]);

  if (!file.transcribed) {
    return (
      <div className="card">
        <h3>Not Transcribed</h3>
        <p>Please transcribe the file first to search words.</p>
      </div>
    );
  }

  return (
    <div className="search-tab-container" style={{maxWidth: '800px', margin: '0 auto', display: 'flex', flexDirection: 'column', height: 'calc(100vh - 200px)'}}>
      <div className="search-header" style={{marginBottom: 24}}>
        <div style={{display: 'flex', gap: 12, alignItems: 'center'}}>
          <input 
            type="text" 
            className="list-editor" 
            style={{flex: 1, padding: '12px 20px', fontSize: '1.1rem', borderRadius: '12px', border: '2px solid var(--border-color)', outline: 'none'}}
            placeholder="Type to search the transcript..." 
            value={query}
            onChange={e => setQuery(e.target.value)}
            autoFocus
          />
          {query.trim() && (
            <button 
              className={`btn ${queryIsBlocked ? 'btn-secondary' : 'btn-primary'}`}
              onClick={() => !queryIsBlocked && handleAddToBlocklist(query.trim())}
              disabled={queryIsBlocked}
              style={{padding: '12px 24px', borderRadius: '12px', opacity: queryIsBlocked ? 0.7 : 1}}
              title={queryIsBlocked ? "Already in blocklist" : "Add to global blocklist"}
            >
              {queryIsBlocked ? "Already Blocked" : "Block Phrase"}
            </button>
          )}
        </div>
        {status && <div style={{marginTop: 12, color: 'var(--accent-primary)', fontSize: '0.9em', textAlign: 'center'}}>{status}</div>}
      </div>

      <div className="search-results" style={{flex: 1, overflowY: 'auto', paddingRight: '10px'}}>
        {loading ? (
          <div style={{textAlign: 'center', marginTop: 40, color: 'var(--text-secondary)'}}>Searching...</div>
        ) : results.length > 0 ? (
          <div className="results-list" style={{display: 'flex', flexDirection: 'column', gap: 12}}>
            <div style={{fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 8, textAlign: 'right'}}>
                {results.length} instances found
            </div>
            {results.map((r, i) => {
              const blocked = isBlocked(r.word);
              return (
                <div key={i} className="rule-item" style={{justifyContent: 'flex-start', borderLeft: 'none', background: 'var(--bg-secondary)', padding: '16px', borderRadius: '12px', position: 'relative'}}>
                  <div className="rule-text" style={{flex: 1}}>
                    <div className="rule-context" style={{color: 'var(--text-primary)', fontSize: '1.1rem', lineHeight: '1.5'}}>
                       <span style={{color: 'var(--text-tertiary)', fontSize: '0.9em'}}>...</span> {r.prefix} <span style={{color: 'var(--accent-primary)', fontWeight: 'bold', borderBottom: '2px solid var(--accent-primary)'}}>{r.word}</span> {r.suffix} <span style={{color: 'var(--text-tertiary)', fontSize: '0.9em'}}>...</span>
                    </div>
                    <div style={{fontSize: '0.8rem', marginTop: 8, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 12}}>
                        <div><span style={{color: 'var(--accent-secondary)'}}>●</span> Time: {Math.floor(r.start / 3600)}:{Math.floor((r.start % 3600) / 60).toString().padStart(2, '0')}:{(r.start % 60).toFixed(2).padStart(5, '0')}</div>
                        {blocked && (
                          <span style={{
                            backgroundColor: 'rgba(255, 68, 68, 0.15)',
                            color: '#ff4444',
                            padding: '2px 8px',
                            borderRadius: '4px',
                            fontSize: '0.75rem',
                            fontWeight: 'bold',
                            textTransform: 'uppercase'
                          }}>
                            Blocked
                          </span>
                        )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : query.trim() ? (
          <div style={{textAlign: 'center', marginTop: 60, color: 'var(--text-secondary)'}}>
            No instances found for "{query}".
          </div>
        ) : (
          <div style={{textAlign: 'center', marginTop: 60, color: 'var(--text-secondary)', fontSize: '1.1rem'}}>
             Search for any word or phrase to see every instance in the audiobook.
          </div>
        )}
      </div>
    </div>
  );
}

export default SearchTab;
