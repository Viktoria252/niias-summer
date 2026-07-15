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

  // 10 полей формы
  const [formData, setFormData] = useState(
    DEFAULT_FIELDS.reduce((acc, field) => ({ ...acc, [field]: "" }), {})
  );

  // Списки файлов и статусы
  const [files, setFiles] = useState([]);
  const [uploadedDocs, setUploadedDocs] = useState([]);
  const [status, setStatus] = useState(isNew ? "NEW" : "PENDING");
  const [errorMessage, setErrorMessage] = useState("");
  const [isDuplicate, setIsDuplicate] = useState(false);
  const [isDragging, setIsDragging] = useState(false); // Для визуального отклика Drag-and-Drop
  const [showDupDetails, setShowDupDetails] = useState(false); // Для разворачивания плашки дубликатов
  
  const [actionLoading, setActionLoading] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const sseConnected = useRef(false);

  // Загрузка деталей инцидента
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

      // --- БЕЗОПАСНЫЙ ПАРСИНГ СТРОК ИЗ СУБД В JS-ОБЪЕКТЫ ---
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

  // Подписка на SSE события
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

          // НА ЛЕТУ автозаполняем поля формы при любом промежуточном или финальном обновлении данных
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

          // Всегда перезагружаем данные, чтобы обновить списки документов (их статусы изменятся на PARSED)
          loadIncident();

          if (payload.status === "COMPLETED" || payload.status === "FAILED") {
            eventSource.close();
            sseConnected.current = false;
          }
        } catch (e) {
          console.error("Ошибка парсинга события SSE:", e);
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

  // Сохранить правки полей (PUT)
  const handleSaveFields = async () => {
    if (isNew) {
      alert("Сначала загрузите файлы, чтобы создать инцидент.");
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

  // Удаление конкретного документа из инцидента
  const handleDeleteDocument = async (docId, fileName, e) => {
    e.preventDefault();
    if (!window.confirm(`Вы действительно хотите удалить файл "${fileName}"? Это пересчитает параметры отказа.`)) {
      return;
    }
    try {
      const response = await fetch(`/api/v1/incidents/documents/${docId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error("Не удалось удалить документ.");
      }
      alert("Документ успешно удален!");
      loadIncident(); // Перезагружаем форму и файлы
    } catch (err) {
      alert(err.message);
    }
  };

  // Обработка ручного выбора файлов (через клик)
  const handleFileChange = (e) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files);
      setFiles((prev) => [...prev, ...selectedFiles]);
    }
  };

  // Обработчики событий Drag-and-Drop
  const handleDragOver = (e) => {
    e.preventDefault();
  };

  // Обработчики Drag-and-Drop
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

  // Удаление файла из списка подготовки к отправке
  const handleRemoveFileFromQueue = (indexToRemove) => {
    setFiles((prev) => prev.filter((_, idx) => idx !== indexToRemove));
  };

  // Отправка первой партии файлов (POST)
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
      if (!response.ok) throw new Error("Не удалось создать инцидент на сервере.");
      const resData = await response.json();
      
      if (resData.incidentId) {
        setFiles([]);
        navigate(`/incident/${resData.incidentId}`);
      } else {
        throw new Error("Сервер не вернул ID инцидента.");
      }
    } catch (err) {
      setErrorMessage(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // Дозагрузка файлов в существующий инцидент (POST /{id}/documents)
  const handleUploadAdditionalFiles = async () => {
    if (files.length === 0) {
      alert("Выберите новые документы для дозагрузки.");
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
      
      alert("Новые файлы успешно добавлены!");
      setFiles([]);
      loadIncident();
    } catch (err) {
      alert(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  // Разделяем документы на обработанные и находящиеся в обработке
  const processedDocs = uploadedDocs.filter((doc) => doc.status === "PARSED");
  const processingDocs = uploadedDocs.filter((doc) => doc.status === "NEW" || doc.status === "PROCESSING");

  return (
    <div className="workspace-container">
      <div className="navigation-row">
        <Link to="/" className="back-link">← Вернуться к реестру</Link>
        {!isNew && <span className="id-badge">ID: {id}</span>}
      </div>

      <div className="workspace-grid">
        
        {/* БЛОК 1 (СЛЕВА): Параметры инцидента */}
        <div className="card left-block">
          <div className="block-header">
            <h3>1. Параметры отказа локомотива</h3>
            <p className="block-subtitle">Данные распознаются автоматически или вводятся вручную</p>
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
                  placeholder={isNew ? "Данные появятся после обработки документов..." : "Введите значение..."}
                />
              </div>
            ))}
          </div>

          <div className="block-actions">
            <button
              onClick={handleSaveFields}
              disabled={isNew || actionLoading}
              className="btn-success"
            >
              {actionLoading ? "Сохранение..." : "Сохранить изменения"}
            </button>
            {saveSuccess && <span className="save-indicator">✓ Данные записаны в БД</span>}
          </div>
        </div>

        {/* БЛОК 2 (СПРАВА): Файлы и анализ нейросети */}
        <div className="card right-block">
          <div className="block-header">
            <h3>2. Документы и Анализ ИИ</h3>
            <p className="block-subtitle">Оригиналы документов и статус распознавания</p>
          </div>

          {/* Плашка обнаружения дубликатов (С выпадающим списком деталей) */}
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
                  <ul style={{ margin: 0, paddingLeft: "20px" }}>
                    {uploadedDocs
                      .filter(doc => doc.isSuspectedDuplicate && doc.extractedText)
                      .map(doc => (
                        <li key={doc.id} style={{ fontSize: "12px", marginTop: "5px", color: "#664d03", lineHeight: "1.4" }}>
                          <strong>{doc.fileName}:</strong> {doc.extractedText}
                        </li>
                      ))
                    }
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* А. Монитор статуса обработки для существующего инцидента */}
          {!isNew && (
            <div className="status-monitor-section">
              <div className="status-monitor-header">
                <span>Статус обработки инцидента:</span>
                <StatusBadge status={status} />
              </div>

              {(status === "PENDING" || status === "PROCESSING") && (
                <div className="inline-spinner-box">
                  <div className="mini-spinner" />
                  <span>Выполняется анализ текстов в фоновом потоке...</span>
                </div>
              )}

              {status === "FAILED" && (
                <div className="inline-error-box">
                  <strong>Ошибка:</strong> {errorMessage || "Ошибка при выполнении OCR/LLM анализа."}
                </div>
              )}
            </div>
          )}

          {/* Б1. Список файлов В ОБРАБОТКЕ */}
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
                        title="Удалить файл из обработки"
                        style={{ marginLeft: "10px", background: "none", border: "none", color: "#f44336", cursor: "pointer", fontSize: "14px" }}
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Б2. Список ранее прикрепленных и УСПЕШНО ОБРАБОТАННЫХ файлов */}
          {!isNew && processedDocs.length > 0 && (
            <div className="docs-list-section">
              <h4>Уже обработанные документы ({processedDocs.length}):</h4>
              <div className="uploaded-docs-grid">
                {processedDocs.map((doc) => (
                  <div key={doc.id} className="uploaded-doc-row">
                    <span className="doc-icon-mini">📄</span>
                    <span className="doc-name-text" title={doc.fileName}>{doc.fileName}</span>
                    <div className="doc-action-group" style={{ display: "flex", alignItems: "center" }}>
                      <a
                        href={`/api/v1/incidents/documents/${doc.id}/file`}
                        target="_blank"
                        rel="noreferrer"
                        className="btn-doc-open"
                      >
                        Открыть
                      </a>
                      <button
                        onClick={(e) => handleDeleteDocument(doc.id, doc.fileName, e)}
                        className="btn-doc-delete"
                        title="Удалить документ"
                        style={{ marginLeft: "10px", background: "none", border: "none", color: "#f44336", cursor: "pointer", fontSize: "14px" }}
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* В. Зона Drag-and-Drop загрузки файлов */}
          <div className="upload-container-box">
            <h4>{isNew ? "Загрузить пакет документов:" : "Добавить файлы в этот инцидент:"}</h4>
            
            <div 
              className={`custom-file-upload ${isDragging ? "drag-active" : ""}`}
              onDragOver={handleDragOver}
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <input
                type="file"
                id="workspaceFileInput"
                multiple
                onChange={handleFileChange}
                style={{ display: "none" }}
              />
              <label htmlFor="workspaceFileInput" className="file-upload-trigger">
                <span className="cloud-icon">📥</span>
                <span style={{ fontSize: "14px", fontWeight: "bold" }}>
                  {isDragging ? "Отпустите мышь для добавления" : "Перетащите файлы сюда или нажмите для выбора"}
                </span>
                <span style={{ fontSize: "11px", color: "#888", marginTop: "4px" }}>
                  Поддерживается одновременный выбор нескольких файлов (PDF, PNG, JPG)
                </span>
              </label>
            </div>

            {/* Список выбранных на отправку файлов с возможностью удаления лишних */}
            {files.length > 0 && (
              <div className="selected-files-preview">
                <div className="preview-header">Выбранные новые файлы ({files.length}):</div>
                <ul className="preview-list">
                  {files.map((file, idx) => (
                    <li key={idx} className="preview-list-item">
                      <span className="file-name-truncate">{file.name}</span>
                      <button 
                        type="button" 
                        onClick={() => handleRemoveFileFromQueue(idx)}
                        className="btn-remove-queue"
                        title="Убрать из списка"
                      >
                        ✕
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {isNew ? (
              <button
                onClick={handleSendToNN}
                disabled={files.length === 0 || actionLoading}
                className="btn-primary"
                style={{ width: "100%", marginTop: "15px", height: "45px" }}
              >
                {actionLoading ? "Отправка..." : "Отправить пакет документов в ИИ"}
              </button>
            ) : (
              <button
                onClick={handleUploadAdditionalFiles}
                disabled={files.length === 0 || actionLoading}
                className="btn-secondary"
                style={{ width: "100%", marginTop: "15px", height: "45px" }}
              >
                {actionLoading ? "Добавление..." : "Догрузить выбранные файлы"}
              </button>
            )}
          </div>

        </div>

      </div>
    </div>
  );
}

function App() {
  return (
    <Router>
      <div className="app-layout">
        <header className="header">
          <div className="header-content">
            <span className="logo-text">НИИАС</span>
            <span className="separator">|</span>
            <span className="app-title">Интеллектуальное автозаполнение инцидентов поломок локомотивов</span>
          </div>
        </header>

        <main className="main-content">
          <Routes>
            <Route path="/" element={<IncidentsRegistry />} />
            <Route path="/incident/new" element={<IncidentWorkspace />} />
            <Route path="/incident/:id" element={<IncidentWorkspace />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;