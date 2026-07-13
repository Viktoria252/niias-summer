import React, { useState } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link,
  useParams,
} from "react-router-dom";
import incidentsData from "./data/incidents";
import "./App.css";

function IncidentsList() {
  return (
    <div className="incident-list">
      <h2>Список инцидентов</h2>
      <div className="incident-list-items">
        {incidentsData.map((inc) => (
          <Link
            key={inc.id}
            to={`/incident/${inc.id}`}
            className="incident-link"
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
    return <div className="container">Инцидент не найден</div>;
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
          "Серия локомотива":
            'В документе П02 указана серия "2ЭС6М", проверьте!',
          "Причина отказа":
            'В документе П02 причина указана как "Износ подшипников коленвала", проверьте!',
        });
      }
    }, 10000);
  };

  const hasHints = Object.keys(hints).length > 0;

  return (
    <div className="container">
      <Link to="/" className="back-link">
        ← Назад к списку
      </Link>

      <h2 className="incident-title">
        Инцидент №{incident.id}: {incident.title}
      </h2>

      <div>
        {Object.entries(incident.data).map(([key, value]) => (
          <div key={key} className="data-field">
            <div className="field-label">{key}:</div>
            <div className="field-value">{value}</div>
            {hints[key] && <div className="field-hint">{hints[key]}</div>}
          </div>
        ))}
      </div>

      <div className="documents-section">
        <h3 className="documents-title">Связанные документы</h3>
        <div className="documents-list">
          {incident.documents.map((doc, idx) => (
            <a key={idx} href={doc.path} download className="document-link">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 384 512"
                width="20"
                height="20"
                style={{ marginRight: "10px", fill: "#c41230" }}
              >
                <path d="M64 0C28.7 0 0 28.7 0 64V448c0 35.3 28.7 64 64 64H320c35.3 0 64-28.7 64-64V160H256c-17.7 0-32-14.3-32-32V0H64zM256 0V128H384L256 0zM128 256c0-17.7 14.3-32 32-32h64c17.7 0 32 14.3 32 32v64c0 17.7-14.3 32-32 32H160c-17.7 0-32-14.3-32-32V256z" />
              </svg>
              <span>{doc.label}</span>
            </a>
          ))}
        </div>
      </div>

      <div className="action-bar">
        <button onClick={handleAgree} disabled={loading} className="btn-agree">
          Согласовать
        </button>

        {loading && (
          <div className="loading-indicator">
            <div className="spinner" />
            <span className="loading-text">
              Подождите пожалуйста, выполняется проверка корректности данных
            </span>
          </div>
        )}

        {checkDone && !loading && (
          <span
            className={`status-message ${hasHints ? "status-error" : "status-success"}`}
          >
            {hasHints ? "Имеются несовпадения" : "Проверка завершена"}
          </span>
        )}
      </div>
    </div>
  );
}

function App() {
  return (
    <Router>
      <div>
        <header className="header">
          <div className="header-content">
            <span className="logo">RZD</span>
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
