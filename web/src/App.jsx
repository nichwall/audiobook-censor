import React, { useState, useEffect, useRef, useCallback } from 'react';
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
  
  const pollingTimeoutRef = useRef(null);
  const prevJobRef = useRef(null);

  const pollJobs = useCallback(async (delay = 30000) => {
    // Clear any existing timeout to avoid overlaps
    if (pollingTimeoutRef.current) {
        clearTimeout(pollingTimeoutRef.current);
    }

    const executePoll = async () => {
        try {
            const res = await fetch(`${API_BASE}/jobs/status`);
            const data = await res.json();
            setJobStatus(data);
        } catch (err) {
            console.error("Poll jobs failed:", err);
        }
        
        // Schedule next regular poll
        pollingTimeoutRef.current = setTimeout(() => executePoll(), 30000);
    };

    pollingTimeoutRef.current = setTimeout(executePoll, delay);
  }, []);

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

  // Refresh file list and job status on mount
  useEffect(() => {
    // Initial status fetch
    fetch(`${API_BASE}/jobs/status`)
      .then(res => res.json())
      .then(setJobStatus)
      .catch(() => {});

    // Start the 30s heartbeat
    pollJobs(30000);
    
    // Cleanup on unmount
    return () => {
      if (pollingTimeoutRef.current) {
        clearTimeout(pollingTimeoutRef.current);
        pollingTimeoutRef.current = null;
      }
    };
  }, [pollJobs]);

  // Trigger file refresh when a job completes
  useEffect(() => {
    const prevJob = prevJobRef.current;
    const currentJob = jobStatus.current;
    
    // Check for transition from "busy" (having a job) to "idle" (no job)
    if (prevJob && !currentJob) {
      console.log("Job completed, refreshing files...");
      setRefreshTrigger(p => p + 1);
    }
    
    prevJobRef.current = currentJob;
  }, [jobStatus.current]);

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

  const refreshData = () => {
    setRefreshTrigger(prev => prev + 1);
    // Restart polling with a short 2-second delay to catch the new job status
    pollJobs(2000);
  };

  return (
    <div className={`app-container ${selectedFile ? 'has-selection' : ''}`}>
      <Sidebar 
        files={files} 
        selectedFile={selectedFile} 
        onSelectFile={handleSelectFile}
        jobStatus={jobStatus}
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
