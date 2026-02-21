import React from 'react';

function Sidebar({ files, selectedFile, onSelectFile, jobStatus, onRefreshMetadata, isRefreshingMetadata }) {
  const getJobForFile = (fileId) => {
    if (jobStatus.current && jobStatus.current.file_id === fileId) {
      return { ...jobStatus.current, isRunning: true };
    }
    return null;
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <span className="sidebar-title">Audio Censor</span>
        <button
          type="button"
          className="btn btn-secondary sidebar-refresh"
          onClick={onRefreshMetadata}
          disabled={isRefreshingMetadata}
        >
          {isRefreshingMetadata ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>
      <div className="file-list">
        {files.map(file => {
          const job = getJobForFile(file.id);
          return (
            <div 
              key={file.id}
              className={`file-item ${selectedFile && selectedFile.id === file.id ? 'active' : ''}`}
              onClick={() => onSelectFile(file)}
            >
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                <div className="file-name" title={file.filename}>{file.filename}</div>
                {job && (
                  <div className="queued-indicator">
                    <div className="spinner"></div>
                  </div>
                )}
              </div>
              <div className="file-status" style={{display: 'flex', alignItems: 'center', gap: '12px', marginTop: 4}}>
                {job ? (
                  <span style={{color: 'var(--accent-primary)', fontWeight: 'bold'}}>
                    {job.type === 'transcribe' ? 'Transcribing...' : (job.type === 'censor' ? 'Censoring...' : 'Processing...')}
                  </span>
                ) : (
                  <>
                    <span style={{color: file.transcribed ? 'var(--success)' : 'var(--text-secondary)'}}>
                      {file.transcribed ? '✓ Transcribed' : '○ Pending'}
                    </span>
                    
                    {file.censored ? (
                        file.is_out_of_date ? (
                            <span style={{color: 'var(--warning)'}}>
                              ⚠ Out of Date
                            </span>
                        ) : (
                            <span style={{color: 'var(--accent-secondary)'}}>
                              ✓ Censored
                            </span>
                        )
                    ) : (
                        <span style={{color: 'var(--text-secondary)', opacity: 0.7}}>
                          ○ Not Censored
                        </span>
                    )}
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default Sidebar;
