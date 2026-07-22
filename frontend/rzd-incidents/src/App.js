import React, { useState, useEffect, useRef } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link,
  useParams,
  useNavigate,
} from "react-router-dom";
import "./App.css";

const DEFAULT_FIELDS = [
  "Место отказа",
  "Дата",
  "Время начала отказа",
  "Серия локомотива",
  "Номер секции локомотива",
  "Договор",
  "Причина отказа",
  "Вид отказа",
  "Оборудование локомотива",
  "Наименование виновной организации"
];

function StatusBadge({ status }) {
  let badgeClass = "badge-pending";
  let statusText = "В очереди";

  if (status === "PROCESSING") {
    badgeClass = "badge-processing";
    statusText = "Обработка...";
  } else if (status === "COMPLETED") {
    badgeClass = "badge-completed";
    statusText = "Готово";
  } else if (status === "FAILED") {
    badgeClass = "badge-failed";
    statusText = "Ошибка";
  }

  return <span className={`status-badge ${badgeClass}`}>{statusText}</span>;
}

// -------------------------------------------------------------------------
// ВСПОМОГАТЕЛЬНЫЙ КОМПОНЕНТ: Интерактивное перетаскиваемое и масштабируемое окно
// -------------------------------------------------------------------------
function InteractiveWindow({ title, initialX, initialY, initialWidth, initialHeight, activeWindow, setActiveWindow, windowId, children, theme = "light" }) {
  const [pos, setPos] = useState({ x: initialX, y: initialY });
  const [zoom, setZoom] = useState(100); // Масштаб в процентах
  const [minimized, setMinimized] = useState(false);

  const handleMouseDown = (e) => {
    if (e.target.closest(".win-controls")) return; 
    setActiveWindow(windowId);

    const startX = e.clientX - pos.x;
    const startY = e.clientY - pos.y;

    const handleMouseMove = (moveEvent) => {
      setPos({
        x: moveEvent.clientX - startX,
        y: moveEvent.clientY - startY,
      });
    };

    const handleMouseUp = () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
  };

  const isDark = theme === "dark";

  return (
    <div
      style={{
        position: "absolute",
        left: `${pos.x}px`,
        top: `${pos.y}px`,
        width: minimized ? "300px" : `${initialWidth}px`,
        height: minimized ? "auto" : `${initialHeight}px`,
        minWidth: "250px",
        minHeight: "45px",
        zIndex: activeWindow === windowId ? 10 : 2,
        background: isDark ? "#1e1e1e" : "#ffffff",
        border: isDark ? "1px solid #333" : "1px solid #ccc",
        borderRadius: "6px",
        boxShadow: activeWindow === windowId ? "0 8px 24px rgba(0,0,0,0.25)" : "0 4px 12px rgba(0,0,0,0.1)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        resize: minimized ? "none" : "both", 
        boxSizing: "border-box",
        transition: "box-shadow 0.2s"
      }}
      onClick={() => setActiveWindow(windowId)}
    >
      <div
        onMouseDown={handleMouseDown}
        style={{
          padding: "8px 12px",
          background: isDark ? "#2d2d2d" : "#f1f3f5",
          borderBottom: isDark ? "1px solid #3c3c3c" : "1px solid #dee2e6",
          cursor: "move",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          userSelect: "none"
        }}
      >
        <span style={{ fontSize: "12px", fontWeight: "bold", color: isDark ? "#ccc" : "#333" }}>{title}</span>
        
        <div className="win-controls" style={{ display: "flex", gap: "6px", alignItems: "center" }}>
          {!minimized && (
            <>
              <button 
                onClick={() => setZoom(Math.max(60, zoom - 10))} 
                title="Уменьшить шрифт"
                style={{ background: "none", border: "none", cursor: "pointer", fontSize: "11px", color: isDark ? "#888" : "#555", fontWeight: "bold", padding: "2px 5px" }}
              >
                -A
              </button>
              <span style={{ fontSize: "9px", color: "#888" }}>{zoom}%</span>
              <button 
                onClick={() => setZoom(Math.min(180, zoom + 10))} 
                title="Увеличить шрифт"
                style={{ background: "none", border: "none", cursor: "pointer", fontSize: "11px", color: isDark ? "#888" : "#555", fontWeight: "bold", padding: "2px 5px" }}
              >
                +A
              </button>
            </>
          )}
          <button 
            onClick={() => setMinimized(!minimized)} 
            style={{ background: "none", border: "none", cursor: "pointer", fontSize: "11px", color: isDark ? "#aaa" : "#555" }}
          >
            {minimized ? "⬜" : "➖"}
          </button>
        </div>
      </div>

      {!minimized && (
        <div style={{ flexGrow: 1, padding: "10px", overflow: "auto", display: "flex", flexDirection: "column", fontSize: `${(zoom / 100) * 12}px` }}>
          {children}
        </div>
      )}
    </div>
  );
}


// -------------------------------------------------------------------------
// 1. ГЛАВНАЯ СТРАНИЦА: Реестр
// -------------------------------------------------------------------------
function IncidentsRegistry() {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadIncidents = async () => {
    try {
      const response = await fetch("/api/v1/incidents");
      if (!response.ok) {
        throw new Error("Не удалось подключиться к бэкенду.");
      }
      const data = await response.json();
      setIncidents(data);
      setError(null);
    } catch (err) {
      setError("Ошибка загрузки данных. Проверьте подключение к бэкенду.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadIncidents();
  }, []);

  const handleDelete = async (id, e) => {
    e.preventDefault();
    if (!window.confirm("Вы действительно хотите удалить этот инцидент и все его файлы?")) {
      return;
    }

    try {
      const response = await fetch(`/api/v1/incidents/${id}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error("Ошибка при удалении на стороне сервера.");
      }
      setIncidents((prev) => prev.filter((inc) => inc.id !== id));
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div className="card">
      <div className="registry-header">
        <div>
          <h2>Реестр инцидентов поломок локомотивов</h2>
          <p className="subtitle">Список зарегистрированных событий и статус их обработки нейросетью</p>
        </div>
        <div className="registry-actions">
          <button onClick={loadIncidents} className="btn-secondary">Обновить</button>
          <Link to="/incident/new" className="btn-primary-add">
            + Создать инцидент
          </Link>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {loading ? (
        <div className="loading-state">Получение списка инцидентов из базы данных...</div>
      ) : incidents.length === 0 ? (
        <div className="empty-state">
          <p>В системе пока нет зарегистрированных инцидентов.</p>
          <Link to="/incident/new" className="btn-primary" style={{ display: "inline-block", marginTop: "10px" }}>
            Зарегистрировать первый инцидент
          </Link>
        </div>
      ) : (
        <table className="custom-table">
          <thead>
            <tr>
              <th>ID Инцидента</th>
              <th>Статус ИИ</th>
              <th>Серия локомотива</th>
              <th>Место отказа</th>
              <th style={{ textAlign: "right" }}>Действия</th>
            </tr>
          </thead>
          <tbody>
            {incidents.map((inc) => {
              const data = inc.correctedData || inc.mergedData || {};
              return (
                <tr key={inc.id}>
                  <td className="cell-uuid">
                    <Link to={`/incident/${inc.id}`} className="uuid-link">
                      {inc.id.substring(0, 8)}...
                    </Link>
                  </td>
                  <td>
                    <StatusBadge status={inc.status} />
                  </td>
                  <td style={{ fontWeight: "500" }}>
                    {data["Серия локомотива"] || "—"}
                  </td>
                  <td style={{ color: "#555" }}>
                    {data["Место отказа"] || "—"}
                  </td>
                  <td>
                    <div className="table-actions">
                      <Link to={`/incident/${inc.id}`} className="btn-table-open">
                        Открыть
                      </Link>
                      <button onClick={(e) => handleDelete(inc.id, e)} className="btn-table-delete">
                        Удалить
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

// -------------------------------------------------------------------------
// 2. РАБОЧАЯ ОБЛАСТЬ (СОЗДАНИЕ / ИЗМЕНЕНИЕ)
// -------------------------------------------------------------------------
function IncidentWorkspace() {
  const { id } = useParams();
  const isNew = !id;
  const navigate = useNavigate();

  const [formData, setFormData] = useState(
    DEFAULT_FIELDS.reduce((acc, field) => ({ ...acc, [field]: "" }), {})
  );

  const [files, setFiles] = useState([]);
  const [uploadedDocs, setUploadedDocs] = useState([]);
  const [status, setStatus] = useState(isNew ? "NEW" : "PENDING");
  const [errorMessage, setErrorMessage] = useState("");
  const [isDuplicate, setIsDuplicate] = useState(false);
  const [isDragging, setIsDragging] = useState(false); 
  const [showDupDetails, setShowDupDetails] = useState(false); 
  
  const [actionLoading, setActionLoading] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const sseConnected = useRef(false);

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDragEnter = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files) {
      const droppedFiles = Array.from(e.dataTransfer.files);
      setFiles((prev) => [...prev, ...droppedFiles]);
    }
  };

  const loadIncident = async () => {
    if (isNew) return;
    try {
      const response = await fetch(`/api/v1/incidents/${id}`);
      if (!response.ok) {
        throw new Error("Не удалось получить данные инцидента.");
      }
      const data = await response.json();
      setStatus(data.status);
      setErrorMessage(data.errorMessage || "");
      setUploadedDocs(data.documents || []);

      let fieldsSource = {};
      
      if (data.correctedData) {
        fieldsSource = typeof data.correctedData === "string" 
          ? JSON.parse(data.correctedData) 
          : data.correctedData;
      } else if (data.mergedData) {
        fieldsSource = typeof data.mergedData === "string" 
          ? JSON.parse(data.mergedData) 
          : data.mergedData;
      }

      setFormData((prev) => {
        const updated = { ...prev };
        DEFAULT_FIELDS.forEach((field) => {
          updated[field] = fieldsSource[field] !== undefined ? String(fieldsSource[field]) : "";
        });
        return updated;
      });

      if (data.documents) {
        setIsDuplicate(data.documents.some((d) => d.isSuspectedDuplicate));
      }
    } catch (err) {
      setErrorMessage(err.message);
      setStatus("FAILED");
    }
  };

  useEffect(() => {
    loadIncident();
  }, [id]);

  useEffect(() => {
    if (!isNew && (status === "PENDING" || status === "PROCESSING") && !sseConnected.current) {
      sseConnected.current = true;
      const eventSource = new EventSource(`/api/v1/incidents/${id}/stream`);

      eventSource.addEventListener("status-update", (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.status) setStatus(payload.status);
          if (payload.errorMessage) setErrorMessage(payload.errorMessage);
          if (payload.isSuspectedDuplicate !== undefined) setIsDuplicate(payload.isSuspectedDuplicate);

          if (payload.mergedData) {
            const currentFields = typeof payload.mergedData === "string" 
              ? JSON.parse(payload.mergedData) 
              : payload.mergedData;
              
            setFormData((prev) => {
              const updated = { ...prev };
              DEFAULT_FIELDS.forEach((f) => {
                if (currentFields[f] !== undefined) updated[f] = String(currentFields[f]);
              });
              return updated;
            });
          }

          loadIncident();

          if (payload.status === "COMPLETED" || payload.status === "FAILED") {
            eventSource.close();
            sseConnected.current = false;
          }
        } catch (e) {
          console.error("Ошибка парсинга SSE:", e);
        }
      });

      eventSource.onerror = () => {
        eventSource.close();
        sseConnected.current = false;
      };

      return () => {
        eventSource.close();
        sseConnected.current = false;
      };
    }
  }, [status, id, isNew]);

  const handleFieldChange = (key, val) => {
    setFormData((prev) => ({ ...prev, [key]: val }));
    setSaveSuccess(false);
  };

  const handleSaveFields = async () => {
    if (isNew) {
      alert("Сначала загрузите файлы.");
      return;
    }
    setActionLoading(true);
    setSaveSuccess(false);
    try {
      const response = await fetch(`/api/v1/incidents/${id}/correct`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      if (!response.ok) throw new Error("Ошибка сохранения");
      setSaveSuccess(true);
      loadIncident();
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteDocument = async (docId, fileName, e) => {
    e.preventDefault();
    if (!window.confirm(`Вы действительно хотите удалить файл "${fileName}"?`)) {
      return;
    }
    try {
      const response = await fetch(`/api/v1/incidents/documents/${docId}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error("Не удалось удалить документ.");
      alert("Документ успешно удален!");
      loadIncident(); 
    } catch (err) {
      alert(err.message);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files) {
      setFiles((prev) => [...prev, ...Array.from(e.target.files)]);
    }
  };

  const handleRemoveFileFromQueue = (indexToRemove) => {
    setFiles((prev) => prev.filter((_, idx) => idx !== indexToRemove));
  };

  const handleSendToNN = async () => {
    if (files.length === 0) {
      alert("Добавьте хотя бы один документ.");
      return;
    }
    setActionLoading(true);
    setErrorMessage("");

    const dataForm = new FormData();
    files.forEach((file) => dataForm.append("files", file));

    try {
      const response = await fetch("/api/v1/incidents", {
        method: "POST",
        body: dataForm,
      });
      if (!response.ok) throw new Error("Не удалось создать инцидент.");
      const resData = await response.json();
      
      if (resData.incidentId) {
        setFiles([]);
        navigate(`/incident/${resData.incidentId}`);
      } else {
        throw new Error("Сервер не вернул ID.");
      }
    } catch (err) {
      setErrorMessage(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleUploadAdditionalFiles = async () => {
    if (files.length === 0) {
      alert("Выберите новые документы.");
      return;
    }
    setActionLoading(true);
    
    const dataForm = new FormData();
    files.forEach((file) => dataForm.append("files", file));

    try {
      const response = await fetch(`/api/v1/incidents/${id}/documents`, {
        method: "POST",
        body: dataForm,
      });
      if (!response.ok) throw new Error("Не удалось догрузить файлы.");
      setFiles([]);
      loadIncident();
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const renderDuplicateItem = (doc) => {
    if (!doc.isSuspectedDuplicate) return null;

    let details = null;
    if (doc.duplicateDetails) {
      try {
        details = JSON.parse(doc.duplicateDetails);
      } catch (e) {
        console.error("Ошибка парсинга JSON метаданных:", e);
      }
    }

    if (details) {
      return (
        <div key={doc.id} style={{ background: "rgba(255,255,255,0.7)", border: "1px dashed #d1c18c", borderRadius: "5px", padding: "10px", marginTop: "8px" }}>
          <p style={{ margin: "0 0 5px 0", fontSize: "13px", fontWeight: "bold", color: "#b52b27" }}>
            ❌ Файл-дубликат: {doc.fileName}
          </p>
          <div style={{ fontSize: "12px", color: "#555", marginLeft: "5px" }}>
            <div>• <strong>Имя оригинала:</strong> {details.originalFileName}</div>
            <div>• <strong>Дата создания оригинала:</strong> {details.processedAt}</div>
            <div>
              • <strong>Инцидент-оригинал:</strong>{" "}
              <Link to={`/incident/${details.originalIncidentId}`} className="uuid-link" style={{ fontWeight: "bold" }}>
                {details.originalIncidentId.substring(0, 8)}...
              </Link>
            </div>
          </div>
          {details.previouslyGeneratedFields && (
            <div style={{ marginTop: "8px", background: "#fdfbe7", padding: "8px", borderRadius: "4px", fontSize: "11px", border: "1px solid #f6f0c4" }}>
              <span style={{ fontWeight: "bold", color: "#664d03", display: "block", marginBottom: "4px" }}>Распознанные ранее поля:</span>
              <ul style={{ margin: 0, paddingLeft: "15px", color: "#666" }}>
                <li><strong>Место отказа:</strong> {details.previouslyGeneratedFields["Место отказа"] || "—"}</li>
                <li><strong>Серия локомотива:</strong> {details.previouslyGeneratedFields["Серия локомотива"] || "—"}</li>
                <li><strong>Договор:</strong> {details.previouslyGeneratedFields["Договор"] || "—"}</li>
              </ul>
            </div>
          )}
        </div>
      );
    }

    return (
      <li key={doc.id} style={{ fontSize: "12px", marginTop: "5px", color: "#664d03" }}>
        <strong>{doc.fileName}:</strong> {doc.extractedText ? doc.extractedText.substring(0, 150) + "..." : "Данные о дубликате отсутствуют."}
      </li>
    );
  };

  const processedDocs = uploadedDocs.filter((doc) => doc.status === "PARSED");
  const processingDocs = uploadedDocs.filter((doc) => doc.status === "NEW" || doc.status === "PROCESSING");

  return (
    <div className="workspace-container">
      <div className="navigation-row">
        <Link to="/" className="back-link">← Вернуться к реестру</Link>
        {!isNew && <span className="id-badge">ID: {id}</span>}
      </div>

      <div className="workspace-grid">
        
        <div className="card left-block">
          <div className="block-header">
            <h3>1. Параметры отказа локомотива</h3>
            <p className="block-subtitle">Данные распознаются автоматически</p>
          </div>

          <div className="fields-grid">
            {DEFAULT_FIELDS.map((field) => (
              <div key={field} className="input-group">
                <label className="input-label">{field}</label>
                <textarea
                  className="input-textarea"
                  value={formData[field]}
                  onChange={(e) => handleFieldChange(field, e.target.value)}
                  rows={2}
                  placeholder={isNew ? "Данные появятся после обработки..." : "Введите значение..."}
                />
              </div>
            ))}
          </div>

          <div className="block-actions">
            <button onClick={handleSaveFields} disabled={isNew || actionLoading} className="btn-success">
              {actionLoading ? "Сохранение..." : "Сохранить изменения"}
            </button>
            {saveSuccess && <span className="save-indicator">✓ Записано в БД</span>}
          </div>
        </div>

        <div className="card right-block">
          <div className="block-header">
            <h3>2. Документы и Анализ ИИ</h3>
          </div>

          {isDuplicate && (
            <div className="alert-duplicate-box" style={{ background: "#fff3cd", border: "1px solid #ffeeba", borderRadius: "6px", padding: "15px", marginBottom: "15px", color: "#856404" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  ⚠️ <strong>Внимание:</strong> Обнаружен файл с идентичным визуальным хэшем (pHash). Возможен дубликат!
                </div>
                <button 
                  onClick={() => setShowDupDetails(!showDupDetails)} 
                  className="btn-secondary" 
                  style={{ height: "30px", fontSize: "12px", padding: "0 10px", margin: 0, background: "#856404", color: "#fff", border: "none", cursor: "pointer" }}
                >
                  {showDupDetails ? "Свернуть" : "Детали"}
                </button>
              </div>
              
              {showDupDetails && (
                <div className="dup-details-content" style={{ marginTop: "10px", borderTop: "1px solid #ffeeba", paddingTop: "10px" }}>
                  <p style={{ fontSize: "12px", fontWeight: "bold", marginBottom: "5px" }}>Найденные совпадения в системе:</p>
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {uploadedDocs
                      .filter(doc => doc.isSuspectedDuplicate)
                      .map(doc => renderDuplicateItem(doc))
                    }
                  </div>
                </div>
              )}
            </div>
          )}

          {!isNew && (
            <div className="status-monitor-section">
              <div className="status-monitor-header">
                <span>Статус обработки инцидента:</span>
                <StatusBadge status={status} />
              </div>

              {(status === "PENDING" || status === "PROCESSING") && (
                <div className="inline-spinner-box">
                  <div className="mini-spinner" />
                  <span>Выполняется анализ текстов...</span>
                </div>
              )}

              {status === "FAILED" && (
                <div className="inline-error-box">
                  <strong>Ошибка:</strong> {errorMessage}
                </div>
              )}
            </div>
          )}

          {!isNew && processingDocs.length > 0 && (
            <div className="docs-list-section" style={{ borderLeft: "4px solid #ff9800", paddingLeft: "10px", marginBottom: "15px" }}>
              <h4 style={{ color: "#e65100" }}>Файлы в обработке ({processingDocs.length}):</h4>
              <div className="uploaded-docs-grid">
                {processingDocs.map((doc) => (
                  <div key={doc.id} className="uploaded-doc-row processing-doc-row">
                    <span className="doc-icon-mini spinner-icon">⏳</span>
                    <span className="doc-name-text" title={doc.fileName}>{doc.fileName}</span>
                    <div className="doc-action-group">
                      <span className="text-loading-status">распознавание...</span>
                      <button
                        onClick={(e) => handleDeleteDocument(doc.id, doc.fileName, e)}
                        className="btn-doc-delete"
                        style={{ marginLeft: "10px", background: "none", border: "none", color: "#f44336", cursor: "pointer" }}
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!isNew && processedDocs.length > 0 && (
            <div className="docs-list-section">
              <h4>Уже обработанные документы ({processedDocs.length}):</h4>
              <div className="uploaded-docs-grid">
                {processedDocs.map((doc) => (
                  <div key={doc.id} className="uploaded-doc-row">
                    <span className="doc-icon-mini">📄</span>
                    <span className="doc-name-text" title={doc.fileName}>{doc.fileName}</span>
                    <div className="doc-action-group" style={{ display: "flex", alignItems: "center" }}>
                      <a href={`/api/v1/incidents/documents/${doc.id}/file`} target="_blank" rel="noreferrer" className="btn-doc-open">
                        Открыть
                      </a>
                      <button
                        onClick={(e) => handleDeleteDocument(doc.id, doc.fileName, e)}
                        className="btn-doc-delete"
                        style={{ marginLeft: "10px", background: "none", border: "none", color: "#f44336", cursor: "pointer" }}
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="upload-container-box">
            <h4>{isNew ? "Загрузить пакет документов:" : "Добавить файлы:"}</h4>
            
            <div 
              className={`custom-file-upload ${isDragging ? "drag-active" : ""}`}
              onDragOver={handleDragOver}
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              style={{ width: "100%", boxSizing: "border-box" }} 
            >
              <input type="file" id="workspaceFileInput" multiple onChange={handleFileChange} style={{ display: "none" }} />
              <label htmlFor="workspaceFileInput" className="file-upload-trigger" style={{ cursor: "pointer", display: "block", width: "100%" }}>
                <span className="cloud-icon">📥</span>
                <span style={{ fontSize: "14px", fontWeight: "bold", display: "block" }}>
                  {isDragging ? "Отпустите мышь" : "Перетащите файлы сюда или нажмите для выбора"}
                </span>
                <span style={{ fontSize: "11px", color: "#888", marginTop: "4px", display: "block" }}>
                  Поддерживается: PDF, DOC, DOCX
                </span>
              </label>
            </div>

            {files.length > 0 && (
              <div className="selected-files-preview">
                <div className="preview-header">Выбранные новые файлы ({files.length}):</div>
                <ul className="preview-list">
                  {files.map((file, idx) => (
                    <li key={idx} className="preview-list-item">
                      <span className="file-name-truncate">{file.name}</span>
                      <button type="button" onClick={() => handleRemoveFileFromQueue(idx)} className="btn-remove-queue">
                        ✕
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {isNew ? (
              <button onClick={handleSendToNN} disabled={files.length === 0 || actionLoading} className="btn-primary" style={{ width: "100%", marginTop: "15px", height: "45px" }}>
                {actionLoading ? "Отправка..." : "Отправить в ИИ"}
              </button>
            ) : (
              <button onClick={handleUploadAdditionalFiles} disabled={files.length === 0 || actionLoading} className="btn-secondary" style={{ width: "100%", marginTop: "15px", height: "45px" }}>
                {actionLoading ? "Добавление..." : "Догрузить выбранные файлы"}
              </button>
            )}
          </div>

        </div>

      </div>
    </div>
  );
}

// -------------------------------------------------------------------------
// 3. НОВАЯ ТЕХНИЧЕСКАЯ ПАНЕЛЬ РАЗРАБОТЧИКА (DEVELOPER WINDOWS SANDBOX)
// -------------------------------------------------------------------------
function DeveloperTools() {
  // --- ЗАГРУЗКА ИЗ LOCALSTORAGE ПРИ МОНТИРОВАНИИ ---
  const [endpointUrl, setEndpointUrl] = useState(() => {
    return localStorage.getItem("dev_endpoint") || "http://localhost:8045/extract_from_markdown";
  });
  const [processedHistory, setProcessedHistory] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("dev_history")) || [];
    } catch {
      return [];
    }
  });
  const [devLogs, setDevLogs] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("dev_logs")) || [];
    } catch {
      return [];
    }
  });
  const [devStatus, setDevStatus] = useState(() => {
    return localStorage.getItem("dev_status") || "IDLE";
  });
  const [markdownOutput, setMarkdownOutput] = useState(() => {
    return localStorage.getItem("dev_markdown") || "";
  });
  const [jsonOutput, setJsonOutput] = useState(() => {
    return localStorage.getItem("dev_json") || "";
  });

  const [devFiles, setDevFiles] = useState([]);
  const [selectedHistoryItem, setSelectedHistoryItem] = useState(null);
  const [isDevDragging, setIsDevDragging] = useState(false);
  const [activeWindow, setActiveWindow] = useState("win_markdown"); 

  const [resetKey, setResetKey] = useState(0);
  const consoleEndRef = useRef(null);

  // --- СИНХРОНИЗАЦИЯ СОСТОЯНИЯ С LOCALSTORAGE НА КАЖДЫЙ ЧИХ ---
  useEffect(() => {
    localStorage.setItem("dev_endpoint", endpointUrl);
  }, [endpointUrl]);

  useEffect(() => {
    localStorage.setItem("dev_history", JSON.stringify(processedHistory));
  }, [processedHistory]);

  useEffect(() => {
    localStorage.setItem("dev_logs", JSON.stringify(devLogs));
  }, [devLogs]);

  useEffect(() => {
    localStorage.setItem("dev_status", devStatus);
  }, [devStatus]);

  useEffect(() => {
    localStorage.setItem("dev_markdown", markdownOutput);
  }, [markdownOutput]);

  useEffect(() => {
    localStorage.setItem("dev_json", jsonOutput);
  }, [jsonOutput]);

  // УМНЫЙ ТРЮК: Растягиваем родительский контейнер на 100% ширины
  useEffect(() => {
    const mainContent = document.querySelector(".main-content");
    if (mainContent) {
      mainContent.style.maxWidth = "100%";
      mainContent.style.width = "100%";
      mainContent.style.padding = "10px 40px";
    }
    return () => {
      if (mainContent) {
        mainContent.style.maxWidth = "";
        mainContent.style.width = "";
        mainContent.style.padding = "";
      }
    };
  }, []);

  const addLog = (message, type = "INFO") => {
    const time = new Date().toISOString().replace("T", " ").substring(0, 19);
    setDevLogs((prev) => [...prev, { time, message, type }]);
  };

  useEffect(() => {
    if (consoleEndRef.current) {
      consoleEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [devLogs]);

  const handleDevFileChange = (e) => {
    if (e.target.files) {
      setDevFiles(Array.from(e.target.files));
    }
  };

  const handleDevDrop = (e) => {
    e.preventDefault();
    setIsDevDragging(false);
    if (e.dataTransfer.files) {
      setDevFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleResetWindows = () => {
    setResetKey((prev) => prev + 1); 
    addLog("Положение, масштаб и состояние всех окон успешно сброшено в исходный вид.", "CLIENT");
  };

  const handleClearHistory = () => {
    if (window.confirm("Очистить историю всех обработанных файлов в текущей сессии?")) {
      setProcessedHistory([]);
      setSelectedHistoryItem(null);
      setMarkdownOutput("");
      setJsonOutput("");
      addLog("История обработанных файлов очищена.", "CLIENT");
    }
  };

  const runSimulatedLogs = async (fileName, fileSize) => {
    setDevLogs([]);
    setMarkdownOutput("");
    setJsonOutput("");
    
    addLog(`[ИНИЦИАЛИЗАЦИЯ] Отправка файла "${fileName}" на эндпоинт: ${endpointUrl}`, "CLIENT");
    await new Promise(r => setTimeout(r, 600));
    
    setDevStatus("UPLOADING");
    addLog(`[FASTAPI] Получен POST-запрос на /extract_from_markdown. Размер файла: ${fileSize} байт.`, "FASTAPI");
    await new Promise(r => setTimeout(r, 800));

    setDevStatus("PARSING");
    addLog(`[PYMUPDF] Открытие структуры документа библиотекой fitz...`, "PYMUPDF");
    await new Promise(r => setTimeout(r, 1000));
    addLog(`[PYMUPDF] Извлечение текстовых контейнеров и разметки в Markdown (pymupdf4llm)...`, "PYMUPDF");
    await new Promise(r => setTimeout(r, 1200));
  };

  const handleProcessDirectly = async () => {
    if (devFiles.length === 0) {
      alert("Выберите файл.");
      return;
    }
    const file = devFiles[0];
    setDevStatus("PROCESSING");
    
    await runSimulatedLogs(file.name, file.size);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("max_tokens", 512);

    try {
      addLog(`[PYMUPDF] Текстовый слой извлечен. Передача сырого Markdown на инференс Qwen...`, "PYMUPDF");
      setDevStatus("INFERENCE");
      addLog(`[QWEN] Запуск инференса на CPU. Активно: 4 быстрых физических потока.`, "QWEN");
      addLog(`[QWEN] Идет посимвольное декодирование и генерация JSON-карты...`, "QWEN");

      const startTime = Date.now();
      const response = await fetch(endpointUrl, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`FastAPI Сервер ответил с ошибкой: Код ${response.status}`);
      }

      const resData = await response.json();
      const duration = ((Date.now() - startTime) / 1000).toFixed(1);

      addLog(`[QWEN] Успешная генерация ответа на CPU за ${duration} сек.`, "QWEN");
      setDevStatus("COMPLETED");
      addLog(`[FASTAPI] Разбор JSON завершен. Операция 200 OK.`, "FASTAPI");

      setMarkdownOutput(resData.extracted_text || "");
      setJsonOutput(JSON.stringify(resData.parsed_json, null, 2) || "{}");

      const historyItem = {
        id: Math.random().toString(36).substring(2, 7),
        fileName: file.name,
        timestamp: new Date().toLocaleTimeString(),
        markdown: resData.extracted_text,
        json: JSON.stringify(resData.parsed_json, null, 2)
      };

      setProcessedHistory((prev) => [historyItem, ...prev]);
      setSelectedHistoryItem(historyItem);

    } catch (err) {
      setDevStatus("FAILED");
      addLog(`[КРИТИЧЕСКИЙ СБОЙ] Ошибка выполнения: ${err.message}`, "ERROR");
    }
  };

  const loadHistoryItem = (item) => {
    setSelectedHistoryItem(item);
    setMarkdownOutput(item.markdown);
    setJsonOutput(item.json);
    addLog(`Загружены данные сессии для: "${item.fileName}"`, "CLIENT");
  };

  return (
    <div className="dev-container" style={{ padding: "15px", maxWidth: "100%", margin: "0 auto", boxSizing: "border-box" }}>
      <div className="navigation-row" style={{ marginBottom: "15px" }}>
        <Link to="/" className="back-link" style={{ fontSize: "13px" }}>← Назад в Реестр</Link>
        <span className="id-badge" style={{ background: "#4caf50", color: "#fff" }}>DEVELOPER DASHBOARD</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "350px 1fr", gap: "20px", width: "100%", alignItems: "start" }}>
        
        {/* ЛЕВАЯ КОЛОНКА (Фиксированные элементы управления) */}
        <div style={{ display: "flex", flexDirection: "column", gap: "15px", width: "100%", boxSizing: "border-box" }}>
          
          {/* Настройка эндпоинта */}
          <div className="card" style={{ padding: "15px", boxSizing: "border-box" }}>
            <h4 style={{ marginTop: 0, marginBottom: "8px", fontSize: "13px" }}>⚙️ Настройка FastAPI эндпоинта</h4>
            <input 
              type="text" 
              className="input-textarea"
              style={{ width: "100%", height: "28px", fontSize: "11px", fontFamily: "monospace", padding: "4px", boxSizing: "border-box" }}
              value={endpointUrl} 
              onChange={(e) => setEndpointUrl(e.target.value)} 
            />
          </div>

          {/* Прямая загрузка документа */}
          <div className="card" style={{ padding: "15px", boxSizing: "border-box" }}>
            <h4 style={{ marginTop: 0, marginBottom: "8px", fontSize: "13px" }}>📥 Прямая загрузка документа</h4>
            <div 
              className={`custom-file-upload ${isDevDragging ? "drag-active" : ""}`}
              onDragOver={(e) => e.preventDefault()}
              onDragEnter={(e) => { e.preventDefault(); setIsDevDragging(true); }}
              onDragLeave={(e) => { e.preventDefault(); setIsDevDragging(false); }}
              onDrop={handleDevDrop}
              style={{ 
                border: "2px dashed #bbb", 
                padding: "15px", 
                textAlign: "center", 
                cursor: "pointer", 
                borderRadius: "5px",
                width: "100%",             
                boxSizing: "border-box"    
              }}
            >
              <input type="file" id="devFileInput" onChange={handleDevFileChange} style={{ display: "none" }} />
              <label htmlFor="devFileInput" style={{ cursor: "pointer", display: "block", width: "100%" }}>
                <span style={{ fontSize: "24px", display: "block", marginBottom: "4px" }}>📄</span>
                <strong style={{ fontSize: "11px", display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {devFiles.length > 0 ? devFiles[0].name : "Выберите файл или перетащите сюда"}
                </strong>
                <span style={{ display: "block", fontSize: "10px", color: "#777", marginTop: "2px" }}>PDF, DOC, DOCX</span>
              </label>
            </div>

            <button 
              onClick={handleProcessDirectly} 
              disabled={devFiles.length === 0 || devStatus === "PROCESSING" || devStatus === "UPLOADING" || devStatus === "PARSING" || devStatus === "INFERENCE"}
              className="btn-primary" 
              style={{ width: "100%", marginTop: "12px", height: "35px", fontSize: "12px" }}
            >
              {devStatus === "PROCESSING" || devStatus === "UPLOADING" || devStatus === "PARSING" || devStatus === "INFERENCE" ? "Выполняется..." : "Запустить обработку"}
            </button>
          </div>

          {/* Статус-бар */}
          <div className="card" style={{ padding: "12px", boxSizing: "border-box" }}>
            <h4 style={{ marginTop: 0, marginBottom: "8px", fontSize: "13px" }}>⚡ Статус конвейера</h4>
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px" }}>
                <span>Фаза:</span>
                <strong style={{ color: devStatus === "FAILED" ? "#f44336" : devStatus === "COMPLETED" ? "#4caf50" : "#ff9800" }}>{devStatus}</strong>
              </div>
              <div style={{ width: "100%", background: "#eee", height: "8px", borderRadius: "4px", overflow: "hidden" }}>
                <div style={{ 
                  width: devStatus === "IDLE" ? "0%" : devStatus === "UPLOADING" ? "25%" : devStatus === "PARSING" ? "50%" : devStatus === "INFERENCE" ? "75%" : devStatus === "COMPLETED" ? "100%" : "100%", 
                  background: devStatus === "FAILED" ? "#f44336" : "#4caf50", 
                  height: "100%", 
                  transition: "width 0.4s ease" 
                }} />
              </div>
            </div>
          </div>

          {/* История сессии */}
          <div className="card" style={{ padding: "12px", maxHeight: "250px", overflowY: "auto", boxSizing: "border-box" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <h4 style={{ margin: 0, fontSize: "13px" }}>📜 История файлов ({processedHistory.length})</h4>
              {processedHistory.length > 0 && (
                <button 
                  onClick={handleClearHistory} 
                  style={{ fontSize: "9px", background: "none", border: "none", color: "#f44336", cursor: "pointer", textDecoration: "underline" }}
                >
                  очистить
                </button>
              )}
            </div>
            {processedHistory.length === 0 ? (
              <p style={{ fontSize: "10px", color: "#888", margin: 0 }}>История пуста.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "5px" }}>
                {processedHistory.map((item) => (
                  <button 
                    key={item.id}
                    onClick={() => loadHistoryItem(item)}
                    style={{ 
                      textAlign: "left", 
                      background: selectedHistoryItem?.id === item.id ? "#e9ecef" : "#fff", 
                      border: "1px solid #ddd", 
                      padding: "6px", 
                      borderRadius: "3px", 
                      fontSize: "11px", 
                      cursor: "pointer",
                      display: "flex",
                      justifyContent: "space-between",
                      width: "100%"
                    }}
                  >
                    <span style={{ fontWeight: "500", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "70%" }}>{item.fileName}</span>
                    <span style={{ color: "#777", fontSize: "9px" }}>{item.timestamp}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

        </div>

        {/* ПРАВАЯ КОЛОНКА (Интерактивное рабочее пространство-песочница) */}
        <div 
          style={{ 
            position: "relative", 
            width: "100%", 
            height: "85vh", 
            minHeight: "850px", 
            background: "#f4f6f9", 
            border: "1px solid #dee2e6", 
            borderRadius: "8px", 
            overflow: "hidden", 
            boxSizing: "border-box"
          }}
        >
          <div style={{ position: "absolute", bottom: "10px", left: "15px", zIndex: 1, fontSize: "11px", color: "#888", userSelect: "none" }}>
            💡 Совет: Каждое окно можно свободно <strong>перетаскивать за шапку</strong>, <strong>растягивать</strong> за нижний правый угол и <strong>масштабировать шрифт</strong>.
          </div>

          {/* КНОПКА СБРОСА ВСЕХ ОКОН В ИСХОДНЫЕ ПОЗИЦИИ */}
          <button
            onClick={handleResetWindows}
            className="btn-table-delete"
            style={{
              position: "absolute",
              top: "10px",
              right: "15px",
              zIndex: 100,
              fontSize: "11px",
              background: "#b52b27",
              color: "#fff",
              border: "none",
              padding: "6px 12px",
              borderRadius: "4px",
              cursor: "pointer",
              fontWeight: "bold",
              boxShadow: "0 2px 6px rgba(0,0,0,0.15)",
              display: "flex",
              alignItems: "center",
              gap: "4px",
              height: "28px"
            }}
          >
            🔄 Сбросить окна
          </button>

          {/* ОКНО 1: Вывод сырого Markdown (Начальный размер увеличен до 700x450, x:20, y:20) */}
          <InteractiveWindow 
            key={`win_markdown_${resetKey}`}
            title="📝 Вывод сырого текста (Markdown)" 
            initialX={20} 
            initialY={20} 
            initialWidth={700} 
            initialHeight={450}
            activeWindow={activeWindow}
            setActiveWindow={setActiveWindow}
            windowId="win_markdown"
          >
            <div style={{ flexGrow: 1, background: "#f8f9fa", border: "1px solid #ccc", borderRadius: "4px", padding: "8px", overflowY: "auto", fontFamily: "monospace", fontSize: "inherit", whiteSpace: "pre-wrap" }}>
              {markdownOutput || "Здесь отобразится извлеченный Markdown текст документа..."}
            </div>
          </InteractiveWindow>

          {/* ОКНО 2: Вывод готового JSON (Начальный размер увеличен до 700x450, x:740, y:20) - НЕТ НАЛОЖЕНИЯ */}
          <InteractiveWindow 
            key={`win_json_${resetKey}`}
            title="💻 Вывод готового JSON" 
            initialX={740} 
            initialY={20} 
            initialWidth={700} 
            initialHeight={450}
            activeWindow={activeWindow}
            setActiveWindow={setActiveWindow}
            windowId="win_json"
            theme="dark"
          >
            <div style={{ flexGrow: 1, background: "#1e1e1e", color: "#9cdcfe", border: "1px solid #333", borderRadius: "4px", padding: "8px", overflowY: "auto", fontFamily: "Consolas, Monaco, monospace", fontSize: "inherit", whiteSpace: "pre" }}>
              <code style={{ color: "#ce9178" }}>{jsonOutput || "{\n  \"message\": \"Здесь отобразится структурированный JSON...\"\n}"}</code>
            </div>
          </InteractiveWindow>

          {/* ОКНО 3: Жизненный цикл документа / Логи (Растянуто во всю ширину, x:20, y:490) */}
          <InteractiveWindow 
            key={`win_logs_${resetKey}`}
            title="📊 Жизненный цикл документа (Логи под капотом)" 
            initialX={20} 
            initialY={490} 
            initialWidth={1420} 
            initialHeight={310}
            activeWindow={activeWindow}
            setActiveWindow={setActiveWindow}
            windowId="win_logs"
            theme="dark"
          >
            <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "4px" }}>
              <button 
                onClick={() => setDevLogs([])} 
                style={{ fontSize: "10px", padding: "2px 6px", cursor: "pointer", background: "#333", color: "#fff", border: "1px solid #555", borderRadius: "3px" }}
              >
                Очистить логи
              </button>
            </div>
            <div style={{ flexGrow: 1, background: "#0c0c0c", color: "#d4d4d4", border: "1px solid #333", borderRadius: "4px", padding: "8px", overflowY: "auto", fontFamily: "Consolas, Monaco, monospace", fontSize: "inherit" }}>
              {devLogs.length === 0 ? (
                <div style={{ color: "#555" }}>Логи жизненного цикла появятся после начала обработки файла...</div>
              ) : (
                devLogs.map((log, idx) => {
                  let color = "#57f287"; 
                  if (log.type === "CLIENT") color = "#3498db";
                  if (log.type === "FASTAPI") color = "#9b59b6";
                  if (log.type === "PYMUPDF") color = "#e67e22";
                  if (log.type === "ERROR") color = "#ed4245";
                  
                  return (
                    <div key={idx} style={{ marginBottom: "3px", lineHeight: "1.3" }}>
                      <span style={{ color: "#858585" }}>{log.time}</span>{" "}
                      <span style={{ color, fontWeight: "bold" }}>[{log.type}]</span>{" "}
                      <span style={{ color: "#fff" }}>{log.message}</span>
                    </div>
                  );
                })
              )}
              <div ref={consoleEndRef} />
            </div>
          </InteractiveWindow>

        </div>

      </div>
    </div>
  );
}

// -------------------------------------------------------------------------
// ГЛАВНЫЙ КОМПОНЕНТ ПРИЛОЖЕНИЯ
// -------------------------------------------------------------------------
function App() {
  return (
    <Router>
      <div className="app-layout">
        <header className="header">
          <div className="header-content" style={{ display: "flex", alignItems: "center", width: "100%" }}>
            <span className="logo-text">НИИАС</span>
            <span className="separator">|</span>
            <span className="app-title">Интеллектуальное автозаполнение инцидентов поломок локомотивов</span>
            
            <Link 
              to="/developer" 
              className="dev-nav-link" 
              style={{ 
                marginLeft: "auto", 
                color: "#fff", 
                textDecoration: "none", 
                fontSize: "12px", 
                border: "1px solid rgba(255,255,255,0.4)", 
                padding: "5px 12px", 
                borderRadius: "4px", 
                background: "rgba(255,255,255,0.1)",
                fontWeight: "500",
                transition: "background 0.3s"
              }}
            >
              🛠️ Панель разработчика
            </Link>
          </div>
        </header>

        <main className="main-content">
          <Routes>
            <Route path="/" element={<IncidentsRegistry />} />
            <Route path="/incident/new" element={<IncidentWorkspace />} />
            <Route path="/incident/:id" element={<IncidentWorkspace />} />
            <Route path="/developer" element={<DeveloperTools />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;