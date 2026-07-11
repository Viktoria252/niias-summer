import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useParams } from 'react-router-dom';
import incidentsData from './data/incidents';

function IncidentsList() {
  return (
    <div style={{ padding: '40px', maxWidth: '800px', margin: '0 auto' }}>
      <h2 style={{ marginBottom: '30px', fontWeight: '400', color: '#333' }}>Список инцидентов</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {incidentsData.map((inc) => (
          <Link
            key={inc.id}
            to={`/incident/${inc.id}`}
            style={{
              display: 'block',
              padding: '14px 20px',
              backgroundColor: '#f0f0f0',
              borderRadius: '8px',
              textDecoration: 'none',
              color: '#1a1a1a',
              fontSize: '16px',
              transition: 'background 0.2s',
              border: '1px solid #ddd',
            }}
            onMouseEnter={(e) => (e.target.style.backgroundColor = '#e0e0e0')}
            onMouseLeave={(e) => (e.target.style.backgroundColor = '#f0f0f0')}
          >
            №{inc.id}. {inc.title}
          </Link>
        ))}
      </div>
    </div>
  );
}

function IncidentDetails() {
  const { id } = useParams();
  const incident = incidentsData.find((inc) => inc.id === parseInt(id));
  const [loading, setLoading] = useState(false);
  const [checkDone, setCheckDone] = useState(false);
  const [hints, setHints] = useState({}); 

  if (!incident) {
    return <div style={{ padding: '40px' }}>Инцидент не найден</div>;
  }

  const handleAgree = () => {
    setLoading(true);
    setCheckDone(false);
    setHints({}); 

    setTimeout(() => {
      setLoading(false);
      setCheckDone(true);

      if (incident.id === 2) {
        setHints({
          'Номер поезда': 'В документе Р02.pdf указан номер "3305", проверьте!',
          'Железная дорога': 'В документе Р02.pdf указано "Свердловской железной дороге", проверьте!',
        });
      }
    }, 10000);
  };

  const hasHints = Object.keys(hints).length > 0;

  return (
    <div style={{ padding: '40px', maxWidth: '900px', margin: '0 auto' }}>
      <Link to="/" style={{ display: 'inline-block', marginBottom: '20px', color: '#555', textDecoration: 'none' }}>
        ← Назад к списку
      </Link>

      <h2 style={{ marginBottom: '30px', fontWeight: '400', color: '#222' }}>
        Инцидент №{incident.id}: {incident.title}
      </h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {Object.entries(incident.data).map(([key, value]) => (
          <div key={key}>
            <div style={{ fontSize: '14px', color: '#666', marginBottom: '4px', fontWeight: '500' }}>
              {key}:
            </div>
            <div
              style={{
                backgroundColor: '#f5f5f5',
                padding: '12px 16px',
                borderRadius: '8px',
                border: '1px solid #e0e0e0',
                color: '#1a1a1a',
                wordBreak: 'break-word',
              }}
            >
              {value}
            </div>
            {hints[key] && (
              <div style={{ fontSize: '14px', color: '#d32f2f', marginTop: '4px' }}>
                {hints[key]}
              </div>
            )}
          </div>
        ))}
      </div>

      <div style={{ marginTop: '40px' }}>
        <h3 style={{ fontWeight: '400', color: '#333', marginBottom: '12px' }}>Связанные документы</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {incident.documents.map((doc, idx) => (
            <a
              key={idx}
              href={doc.path}
              download
              style={{
                display: 'flex',
                alignItems: 'center',
                padding: '12px 16px',
                backgroundColor: '#fafafa',
                border: '1px solid #ddd',
                borderRadius: '8px',
                textDecoration: 'none',
                color: '#222',
                fontSize: '15px',
                transition: 'background 0.2s',
                width: '100%',
                boxSizing: 'border-box',
              }}
              onMouseEnter={(e) => (e.target.style.backgroundColor = '#f0f0f0')}
              onMouseLeave={(e) => (e.target.style.backgroundColor = '#fafafa')}
            >
              <span style={{ marginRight: '10px', fontSize: '20px' }}>📄</span>
              <span>{doc.label}</span>
            </a>
          ))}
        </div>
      </div>

      <div style={{ marginTop: '40px', display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap' }}>
        <button
          onClick={handleAgree}
          disabled={loading}
          style={{
            padding: '10px 30px',
            backgroundColor: '#d0d0d0',
            border: '1px solid #bbb',
            borderRadius: '6px',
            fontSize: '16px',
            cursor: loading ? 'default' : 'pointer',
            color: loading ? '#888' : '#111',
          }}
        >
          Согласовать
        </button>

        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              className="spinner"
              style={{
                border: '4px solid #e0e0e0',
                borderTop: '4px solid #888',
                borderRadius: '50%',
                width: '24px',
                height: '24px',
                animation: 'spin 1s linear infinite',
              }}
            />
            <span style={{ color: '#555', fontSize: '15px' }}>
              Подождите пожалуйста, выполняется проверка корректности данных
            </span>
          </div>
        )}

        {checkDone && !loading && (
          <span style={{ color: hasHints ? '#d32f2f' : '#2c7a2c', fontSize: '15px', fontWeight: '500' }}>
            {hasHints ? 'Имеются несовпадения' : 'Проверка завершена'}
          </span>
        )}
      </div>

      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

function App() {
  return (
    <Router>
      <div style={{ fontFamily: 'Arial, sans-serif', backgroundColor: '#fff', minHeight: '100vh' }}>
        <header style={{ padding: '20px 40px', borderBottom: '1px solid #eee' }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <span
              style={{
                fontSize: '24px',
                fontWeight: 'bold',
                color: '#c41230',
                letterSpacing: '1px',
                fontFamily: 'Arial, sans-serif',
              }}
            >
              RZD
            </span>
          </div>
        </header>

        <main>
          <Routes>
            <Route path="/" element={<IncidentsList />} />
            <Route path="/incident/:id" element={<IncidentDetails />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;