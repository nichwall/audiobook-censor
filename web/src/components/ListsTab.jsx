import React, { useState, useEffect } from 'react';

function ListsTab({ apiBase }) {
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
      setTimeout(() => setStatus(""), 2000);
    } catch (e) {
      setStatus("Error saving");
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
                <h3>Blocklist (one phrase per line)</h3>
                <textarea 
                    className="list-editor" 
                    value={blocklist}
                    onChange={e => setBlocklist(e.target.value)}
                />
            </div>
            <div style={{flex: 1}}>
                <h3>Allowlist (exceptions)</h3>
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
