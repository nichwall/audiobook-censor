import React, { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import SummaryTab from './components/SummaryTab';
import ListsTab from './components/ListsTab';
import FileRulesTab from './components/FileRulesTab';
import SearchTab from './components/SearchTab';

const API_BASE = "/api";

function App() {
  const [files, setFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [activeTab, setActiveTab] = useState('summary');
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [jobStatus, setJobStatus] = useState({ current: null });
  const [isRefreshingMetadata, setIsRefreshingMetadata] = useState(false);

  const handleWebSocketUpdates = useCallback((updates) => {
    setFiles(prev => {
      const map = new Map(prev.map(file => [file.id, file]));
      updates.forEach(update => {
        const existing = map.get(update.id) || {};
        map.set(update.id, { ...existing, ...update });
      });
      return Array.from(map.values());
    });

    setSelectedFile(prev => {
      if (!prev) return null;
      const update = updates.find(item => item.id === prev.id);
      return update ? { ...prev, ...update } : prev;
    });

    setJobStatus(prev => {
      let current = prev.current;
      updates.forEach(item => {
        const job = item.job;
        if (!job) return;
        if (job.status === 'started') {
          current = {
            file_id: item.id,
            filename: item.filename,
            type: job.type,
            duration: job.duration,
            started_at: job.started_at,
            calculated_est_end_at: job.calculated_est_end_at
          };
        } else if (job.status === 'completed' && current && current.file_id === item.id) {
          current = null;
        }
      });
      return { current };
    });
  }, []);

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/updates`;
    const ws = new WebSocket(wsUrl);

    const handleMessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (Array.isArray(data)) {
          handleWebSocketUpdates(data);
        }
      } catch (err) {
        console.error("WebSocket parse error:", err);
      }
    };

    ws.addEventListener('message', handleMessage);
    ws.addEventListener('error', (err) => {
      console.error("WebSocket error:", err);
    });

    return () => {
      ws.removeEventListener('message', handleMessage);
      ws.close();
    };
  }, [handleWebSocketUpdates]);

  // Fetch files whenever refreshTrigger changes
  useEffect(() => {
    fetch(`${API_BASE}/files`)
      .then(res => res.json())
      .then(data => {
        setFiles(data);
        
        // Check URL param for initial selection or deep link
        const params = new URLSearchParams(window.location.search);
        const fileParam = params.get('file'); // Now this holds the ID
        
        if (fileParam) {
           const found = data.find(f => f.id === fileParam);
           if (found) setSelectedFile(found);
           else setSelectedFile(null); // Clear if not found
        } else if (selectedFile) {
           // Refresh existing selection data
           const updated = data.find(f => f.id === selectedFile.id);
           if (updated) setSelectedFile(updated);
           else setSelectedFile(null);
        }
      })
      .catch(err => console.error(err));
  }, [refreshTrigger]);

  // Handle browser back/forward buttons
  useEffect(() => {
      const handlePopState = () => {
          const params = new URLSearchParams(window.location.search);
          const fileParam = params.get('file');
          if (!fileParam) {
              setSelectedFile(null);
          } else {
              const found = files.find(f => f.id === fileParam);
              if (found) setSelectedFile(found);
          }
      };
      
      window.addEventListener('popstate', handlePopState);
      return () => window.removeEventListener('popstate', handlePopState);
  }, [files]);

  const handleSelectFile = (file) => {
    setSelectedFile(file);
    const params = new URLSearchParams(window.location.search);
    params.set('file', file.id);
    window.history.pushState({}, '', '?' + params.toString());
  };

  const handleBack = () => {
      window.history.back();
  };

  const refreshData = useCallback(() => {
    setRefreshTrigger(prev => prev + 1);
  }, []);

  const handleMetadataRefresh = useCallback(async () => {
    setIsRefreshingMetadata(true);
    try {
      await fetch(`${API_BASE}/files/refresh_metadata`, { method: 'POST' });
      refreshData();
    } catch (err) {
      console.error("Metadata refresh failed:", err);
    } finally {
      setIsRefreshingMetadata(false);
    }
  }, [refreshData]);

  const handleConfigChange = useCallback(() => {
    handleMetadataRefresh();
  }, [handleMetadataRefresh]);

  return (
    <div className={`app-container ${selectedFile ? 'has-selection' : ''}`}>
      <Sidebar 
        files={files} 
        selectedFile={selectedFile} 
        onSelectFile={handleSelectFile}
        jobStatus={jobStatus}
        onRefreshMetadata={handleMetadataRefresh}
        isRefreshingMetadata={isRefreshingMetadata}
      />
      
      <div className="main-content">
        {selectedFile ? (
          <>
            <div className="mobile-header">
              <button className="btn-back" onClick={handleBack}>
                ← Back
              </button>
            </div>
            <div className="tabs-header">
              <button 
                className={`tab-btn ${activeTab === 'summary' ? 'active' : ''}`}
                onClick={() => setActiveTab('summary')}
              >
                Summary
              </button>
              <button 
                className={`tab-btn ${activeTab === 'lists' ? 'active' : ''}`}
                onClick={() => setActiveTab('lists')}
              >
                Global Lists
              </button>
              <button 
                className={`tab-btn ${activeTab === 'rules' ? 'active' : ''}`}
                onClick={() => setActiveTab('rules')}
              >
                File Rules
              </button>
              <button 
                className={`tab-btn ${activeTab === 'search' ? 'active' : ''}`}
                onClick={() => setActiveTab('search')}
              >
                Word Search
              </button>
            </div>

            <div className="tab-content">
              {activeTab === 'summary' && (
                <SummaryTab 
                  file={selectedFile} 
                  apiBase={API_BASE} 
                  onUpdate={refreshData}
                  jobStatus={jobStatus}
                />
              )}
              {activeTab === 'lists' && (
                <ListsTab 
                  apiBase={API_BASE}
                  onUpdate={refreshData}
                  onGlobalConfigChange={handleConfigChange}
                />
              )}
              {activeTab === 'rules' && (
                <FileRulesTab 
                  file={selectedFile}
                  apiBase={API_BASE}
                />
              )}
              {activeTab === 'search' && (
                <SearchTab 
                  file={selectedFile}
                  apiBase={API_BASE}
                  onUpdate={refreshData}
                  onGlobalConfigChange={handleConfigChange}
                />
              )}
            </div>
          </>
        ) : (
          <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-secondary)'}}>
            <p>Select a file to begin</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
