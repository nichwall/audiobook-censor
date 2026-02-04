import React from 'react';

function Sidebar({ files, selectedFile, onSelectFile, onRefresh }) {
  return (
    <div className="sidebar">
      <div className="sidebar-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>Audio Censor</span>
        <button 
          onClick={(e) => { e.stopPropagation(); onRefresh(); }} 
          title="Refresh List"
          style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', padding: 0 }}
        >
          ↻
        </button>
      </div>
      <div className="file-list">
        {files.map(file => (
          <div 
            key={file.filename}
            className={`file-item ${selectedFile && selectedFile.filename === file.filename ? 'active' : ''}`}
            onClick={() => onSelectFile(file)}
          >
            <div className="file-name" title={file.filename}>{file.filename}</div>
            <div className="file-status">
               <span style={{color: file.transcribed ? 'var(--success)' : 'var(--text-secondary)'}}>
                 {file.transcribed ? '✓ Transcribed' : '○ Pending'}
               </span>
            </div>
            {file.censored && (
                <div className="file-status">
                    <span style={{color: 'var(--accent-secondary)'}}>✓ Censored</span>
                </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default Sidebar;
