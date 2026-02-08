import React, { useState, useEffect } from 'react';

function ListsTab({ apiBase, onUpdate }) {
  const [blocklist, setBlocklist] = useState("");
  const [allowlist, setAllowlist] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    fetch(`${apiBase}/config/global`)
      .then(res => res.json())
      .then(data => {
        setBlocklist(data.blocklist || "");
        setAllowlist(data.allowlist || "");
      });
  }, [apiBase]);

  const handleSave = async () => {
    setStatus("Saving...");
    try {
      await fetch(`${apiBase}/config/global`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ blocklist, allowlist })
      });
      setStatus("Saved!");
      if (onUpdate) onUpdate();
      setTimeout(() => setStatus(""), 2000);
    } catch (e) {
      setStatus("Error saving");
    }
  };

  const handleSort = (type) => {
    if (type === 'block') {
      const sorted = blocklist.split('\n').filter(l => l.trim()).sort((a, b) => a.localeCompare(b)).join('\n');
      setBlocklist(sorted);
    } else {
      const sorted = allowlist.split('\n').filter(l => l.trim()).sort((a, b) => a.localeCompare(b)).join('\n');
      setAllowlist(sorted);
    }
  };


  return (
    <div>
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16}}>
            <h2 style={{margin: 0}}>Global Lists</h2>
            {status && <span style={{color: 'var(--success)'}}>{status}</span>}
            <button className="btn btn-primary" onClick={handleSave}>Save Changes</button>
        </div>

        <div style={{display: 'flex', gap: 24}}>
            <div style={{flex: 1}}>
                <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8}}>
                    <h3 style={{margin: 0}}>Blocklist (one phrase per line)</h3>
                    <button className="btn btn-secondary" style={{padding: '4px 10px', fontSize: '0.8rem'}} onClick={() => handleSort('block')}>Sort A-Z</button>
                </div>
                <textarea 
                    className="list-editor" 
                    value={blocklist}
                    onChange={e => setBlocklist(e.target.value)}
                />
            </div>
            <div style={{flex: 1}}>
                <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8}}>
                    <h3 style={{margin: 0}}>Allowlist (exceptions)</h3>
                    <button className="btn btn-secondary" style={{padding: '4px 10px', fontSize: '0.8rem'}} onClick={() => handleSort('allow')}>Sort A-Z</button>
                </div>
                <textarea 
                    className="list-editor"
                    value={allowlist}
                    onChange={e => setAllowlist(e.target.value)}
                />
            </div>
        </div>
    </div>
  );
}

export default ListsTab;
