import React from 'react';

function Sidebar({ files, selectedFile, onSelectFile }) {
  return (
    <div className="sidebar">
      <div className="sidebar-header">Audio Censor</div>
      <div className="file-list">
        {files.map(file => (
          <div 
            key={file.filename}
            className={`file-item ${selectedFile && selectedFile.filename === file.filename ? 'active' : ''}`}
            onClick={() => onSelectFile(file)}
          >
            <div className="file-name" title={file.filename}>{file.filename}</div>
            <div className="file-status" style={{display: 'flex', alignItems: 'center', gap: '12px'}}>
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
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default Sidebar;
