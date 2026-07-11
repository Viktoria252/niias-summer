import React from 'react';

const PdfIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z" stroke="#D32F2F" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M14 2V8H20" stroke="#D32F2F" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M12 18V12" stroke="#D32F2F" strokeWidth="2" strokeLinecap="round"/>
    <path d="M9 15L9 12" stroke="#D32F2F" strokeWidth="2" strokeLinecap="round"/>
    <path d="M15 15L15 12" stroke="#D32F2F" strokeWidth="2" strokeLinecap="round"/>
    <path d="M9 18H15" stroke="#D32F2F" strokeWidth="2" strokeLinecap="round"/>
  </svg>
);

const DocumentCard = ({ label, filename, onDownload }) => {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      padding: '8px 16px',
      backgroundColor: '#f5f5f5',
      borderRadius: '6px',
      border: '1px solid #ddd',
      cursor: 'pointer',
      transition: 'background 0.2s',
    }}
    onClick={onDownload}
    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#e0e0e0'}
    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#f5f5f5'}
    >
      <PdfIcon />
      <span style={{ fontSize: '14px', color: '#222' }}>{label}</span>
      <span style={{ marginLeft: 'auto', fontSize: '12px', color: '#888' }}>.pdf</span>
    </div>
  );
};

export default DocumentCard;