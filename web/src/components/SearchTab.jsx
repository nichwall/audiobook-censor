import React, { useState, useEffect, memo, useMemo } from 'react';

// Memoized vocab component to prevent re-renders on every keystroke in SearchBar
const VocabSidebar = memo(({ vocab, onSelectWord }) => {
  const [filter, setFilter] = useState("");
  
  const filteredVocab = useMemo(() => {
    let list = vocab;
    if (filter) {
      list = vocab.filter(v => v.word.includes(filter.toLowerCase()));
    }
    return list.slice(0, 1000); // Limit to 1000 for performance
  }, [vocab, filter]);

  return (
    <div className="vocab-sidebar" style={{width: 280, display: 'flex', flexDirection: 'column', borderRight: '1px solid var(--border-color)', paddingRight: 16}}>
      <h3>Vocabulary</h3>
      <input 
        type="text" 
        placeholder="Filter vocabulary..." 
        value={filter}
        onChange={e => setFilter(e.target.value)}
        style={{
          width: '100%',
          padding: '8px',
          marginBottom: 12,
          backgroundColor: 'var(--bg-primary)',
          color: 'var(--text-primary)',
          border: '1px solid var(--border-color)',
          borderRadius: 4
        }}
      />
      <div style={{flex: 1, overflowY: 'auto'}}>
        {filteredVocab.map((v, i) => (
          <div 
            key={i} 
            className="vocab-item"
            onClick={() => onSelectWord(v.word)}
            style={{
              padding: '8px 12px',
              cursor: 'pointer',
              borderRadius: 4,
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '0.9em'
            }}
          >
            <span className="word">{v.word}</span>
            <span className="count" style={{color: 'var(--text-secondary)'}}>{v.count}</span>
          </div>
        ))}
        {vocab.length > 1000 && !filter && <div style={{padding: 10, fontSize: '0.8em', color: 'var(--text-secondary)'}}>Showing top 1000 words...</div>}
      </div>
    </div>
  );
});

function SearchTab({ file, apiBase }) {
  const [query, setQuery] = useState("");
  const [vocab, setVocab] = useState([]);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    if (!file.transcribed) return;
    fetch(`${apiBase}/files/${file.id}/vocabulary`)
      .then(res => res.json())
      .then(data => setVocab(data || []))
      .catch(err => console.error(err));
  }, [file, apiBase]);

  const handleSearch = (q) => {
    const searchQ = q || query;
    if (!searchQ.trim()) return;
    
    setLoading(true);
    fetch(`${apiBase}/files/${file.id}/search?q=${encodeURIComponent(searchQ)}`)
      .then(res => res.json())
      .then(data => {
        setResults(data || []);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  };

  const handleAddToBlocklist = async (word) => {
    if (!word) return;
    setStatus(`Adding "${word}" to blocklist...`);
    try {
      const res = await fetch(`${apiBase}/config/global`);
      const config = await res.json();
      
      let blocklist = config.blocklist || "";
      const words = blocklist.split('\n').map(w => w.trim().toLowerCase());
      
      if (!words.includes(word.toLowerCase())) {
        blocklist = blocklist.trim() + (blocklist ? "\n" : "") + word;
        
        await fetch(`${apiBase}/config/global`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...config, blocklist })
        });
        setStatus(`"${word}" added to blocklist!`);
      } else {
        setStatus(`"${word}" is already in blocklist.`);
      }
      
      setTimeout(() => setStatus(""), 3000);
    } catch (e) {
      console.error(e);
      setStatus("Error updating blocklist");
    }
  };

  if (!file.transcribed) {
    return (
      <div className="card">
        <h3>Not Transcribed</h3>
        <p>Please transcribe the file first to search words.</p>
      </div>
    );
  }

  return (
    <div className="search-tab-container" style={{display: 'flex', gap: 24, height: 'calc(100vh - 200px)'}}>
      <VocabSidebar 
        vocab={vocab} 
        onSelectWord={(word) => {
          setQuery(word);
          handleSearch(word);
        }} 
      />

      <div className="search-main" style={{flex: 1, display: 'flex', flexDirection: 'column'}}>
        <div className="search-header" style={{marginBottom: 20}}>
          <div style={{display: 'flex', gap: 12, alignItems: 'center'}}>
            <input 
              type="text" 
              className="list-editor" 
              style={{height: 'auto', padding: '10px 15px'}}
              placeholder="Search for a word..." 
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
            />
            <button className="btn btn-primary" onClick={() => handleSearch()}>Search</button>
            {query && (
              <button 
                className="btn btn-secondary" 
                onClick={() => handleAddToBlocklist(query)}
                title="Add current search term to global blocklist"
              >
                Block "{query}"
              </button>
            )}
          </div>
          {status && <div style={{marginTop: 8, color: 'var(--accent-primary)', fontSize: '0.9em'}}>{status}</div>}
        </div>

        <div className="search-results" style={{flex: 1, overflowY: 'auto'}}>
          {loading ? (
            <div>Searching...</div>
          ) : results.length > 0 ? (
            <div className="results-list" style={{display: 'flex', flexDirection: 'column', gap: 12}}>
              {results.map((r, i) => (
                <div key={i} className="rule-item" style={{justifyContent: 'flex-start', borderLeft: 'none', background: 'var(--bg-secondary)'}}>
                  <div className="rule-text" style={{flex: 1}}>
                    <div className="rule-context" style={{color: 'var(--text-primary)', fontSize: '1.1em'}}>
                       ... {r.prefix} <span style={{color: 'var(--accent-primary)', fontWeight: 'bold'}}>{r.word}</span> {r.suffix} ...
                    </div>
                    <div style={{fontSize: '0.8em', marginTop: 4, color: 'var(--text-secondary)'}}>
                        Time: {r.start.toFixed(2)}s
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : query ? (
            <div style={{color: 'var(--text-secondary)'}}>No instances found for "{query}".</div>
          ) : (
            <div style={{color: 'var(--text-secondary)'}}>Search for a word or pick one from the vocabulary list to see context.</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default SearchTab;
