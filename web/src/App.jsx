import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import SummaryTab from './components/SummaryTab';
import ListsTab from './components/ListsTab';
import FileRulesTab from './components/FileRulesTab';

const API_BASE = "/api";

function App() {
  const [files, setFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [activeTab, setActiveTab] = useState('summary');
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  useEffect(() => {
    fetch(`${API_BASE}/files`)
      .then(res => res.json())
      .then(data => {
        setFiles(data);
        // If we have a selected file, update its data reference
        if (selectedFile) {
          const updated = data.find(f => f.filename === selectedFile.filename);
          if (updated) setSelectedFile(updated);
        }
      })
      .catch(err => console.error(err));
  }, [refreshTrigger]);

  const handleSelectFile = (file) => {
    setSelectedFile(file);
    // Reset to summary when switching files? Or keep tab?
    // start with summary if not set
  };

  const refreshData = () => {
    setRefreshTrigger(prev => prev + 1);
  };

  return (
    <div className={`app-container ${selectedFile ? 'has-selection' : ''}`}>
      <Sidebar 
        files={files} 
        selectedFile={selectedFile} 
        onSelectFile={handleSelectFile}
      />
      
      <div className="main-content">
        {selectedFile ? (
          <>
            <div className="mobile-header">
              <button className="btn-back" onClick={() => setSelectedFile(null)}>
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
            </div>

            <div className="tab-content">
              {activeTab === 'summary' && (
                <SummaryTab 
                  file={selectedFile} 
                  apiBase={API_BASE} 
                  onUpdate={refreshData}
                />
              )}
              {activeTab === 'lists' && (
                <ListsTab 
                  apiBase={API_BASE}
                />
              )}
              {activeTab === 'rules' && (
                <FileRulesTab 
                  file={selectedFile}
                  apiBase={API_BASE}
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
