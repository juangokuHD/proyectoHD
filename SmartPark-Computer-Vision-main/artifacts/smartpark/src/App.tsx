import { useRef, useState, type ChangeEvent, type CSSProperties, type MouseEvent } from 'react';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import { useAnalyzeParkingImage, useDeleteParkingCamera, useListParkingCameras, useSaveParkingCamera, getListParkingCamerasQueryKey, type ParkingCamera, type ParkingCameraInput, type ParkingAnalysisResult } from '@workspace/api-client-react';
import { Activity, AlertCircle, ArrowDownToLine, Camera, Check, ChevronDown, CircleHelp, Crosshair, HardDriveUpload, LoaderCircle, MapPin, Plus, RefreshCw, ScanLine, ShieldCheck, SlidersHorizontal, Trash2, UploadCloud, X } from 'lucide-react';
import './index.css';

const queryClient = new QueryClient();
type Point = { x: number; y: number };
type Slot = { id: string; polygon: Point[] };
const palette = ['#2bd4a1', '#f5b957', '#75bfe8', '#ed8075', '#bd9ce9'];

function AppWorkspace() {
  const qc = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const { data: cameras, isLoading: camerasLoading, isError: camerasError, refetch } = useListParkingCameras();
  const saveCamera = useSaveParkingCamera();
  const deleteCamera = useDeleteParkingCamera();
  const analyze = useAnalyzeParkingImage();
  const cameraList = cameras ?? [];
  const [selectedId, setSelectedId] = useState('');
  const activeCamera = cameraList.find((cam) => cam.id === selectedId) ?? null;
  const [imageSrc, setImageSrc] = useState('');
  const [imageBase64, setImageBase64] = useState('');
  const [imageName, setImageName] = useState('');
  const [naturalSize, setNaturalSize] = useState({ width: 0, height: 0 });
  const [draftSlots, setDraftSlots] = useState<Slot[]>([]);
  const [workingPoints, setWorkingPoints] = useState<Point[]>([]);
  const [cameraName, setCameraName] = useState('');
  const [isNaming, setIsNaming] = useState(false);
  const [confidence, setConfidence] = useState(0.35);
  const [result, setResult] = useState<ParkingAnalysisResult | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [uploadError, setUploadError] = useState('');

  const displayedSlots: Slot[] = isNaming || !activeCamera ? draftSlots : activeCamera.spaces;
  const occupancyTone = result?.occupancyLevel.toLowerCase() ?? '';
  const canAnalyze = Boolean(imageBase64 && activeCamera && activeCamera.spaces.length > 0 && !analyze.isPending);

  const acceptFile = (file?: File) => {
    if (!file) return;
    if (!['image/png', 'image/jpeg'].includes(file.type)) {
      setUploadError('Choose a PNG or JPEG image to continue.');
      return;
    }
    setUploadError('');
    setResult(null);
    const reader = new FileReader();
    reader.onload = () => {
      const src = String(reader.result ?? '');
      const image = new Image();
      image.onload = () => {
        setImageSrc(src);
        setImageBase64(src);
        setImageName(file.name);
        setNaturalSize({ width: image.naturalWidth, height: image.naturalHeight });
        setDraftSlots([]);
        setWorkingPoints([]);
      };
      image.onerror = () => setUploadError('This image could not be opened. Try another file.');
      image.src = src;
    };
    reader.onerror = () => setUploadError('The image could not be read. Please try again.');
    reader.readAsDataURL(file);
  };

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    acceptFile(event.target.files?.[0]);
    event.target.value = '';
  };

  const newCamera = () => {
    setSelectedId('');
    setDraftSlots([]);
    setWorkingPoints([]);
    setCameraName('');
    setIsNaming(false);
    setResult(null);
  };

  const addPoint = (event: MouseEvent<HTMLDivElement>) => {
    if (!imageSrc || !isNaming || !naturalSize.width) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const p = {
      x: Math.max(0, Math.min(naturalSize.width, ((event.clientX - bounds.left) / bounds.width) * naturalSize.width)),
      y: Math.max(0, Math.min(naturalSize.height, ((event.clientY - bounds.top) / bounds.height) * naturalSize.height)),
    };
    setWorkingPoints((prev) => {
      const next = [...prev, p];
      if (next.length === 4) {
        const idx = draftSlots.length + 1;
        setDraftSlots((slots) => [...slots, { id: `space-${String(idx).padStart(2, '0')}`, polygon: next }]);
        return [];
      }
      return next;
    });
  };

  const startCamera = () => {
    if (!imageSrc) {
      fileInput.current?.click();
      return;
    }
    setSelectedId('');
    setDraftSlots([]);
    setWorkingPoints([]);
    setCameraName('');
    setResult(null);
    setIsNaming(true);
  };

  const persistCamera = () => {
    if (!cameraName.trim() || !naturalSize.width || draftSlots.length === 0) return;
    const payload: ParkingCameraInput = {
      id: `camera-${crypto.randomUUID()}`,
      name: cameraName.trim(),
      referenceWidth: naturalSize.width,
      referenceHeight: naturalSize.height,
      spaces: draftSlots,
    };
    saveCamera.mutate({ data: payload }, {
      onSuccess: (saved) => {
        qc.invalidateQueries({ queryKey: getListParkingCamerasQueryKey() });
        setSelectedId(saved.id);
        setIsNaming(false);
        setWorkingPoints([]);
      },
    });
  };

  const removeCamera = () => {
    if (!activeCamera || !window.confirm(`Delete “${activeCamera.name}” and its ${activeCamera.spaces.length} mapped spaces?`)) return;
    const target = activeCamera.id;
    deleteCamera.mutate({ cameraId: target }, {
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: getListParkingCamerasQueryKey() });
        setSelectedId('');
        setResult(null);
      },
    });
  };

  const runAnalysis = () => {
    if (!canAnalyze || !activeCamera) return;
    setResult(null);
    analyze.mutate({ data: { imageBase64, cameraId: activeCamera.id, confidence } }, { onSuccess: setResult });
  };

  const downloadResult = () => {
    if (!result) return;
    const href = result.imageBase64.startsWith('data:') ? result.imageBase64 : `data:image/png;base64,${result.imageBase64}`;
    const link = document.createElement('a');
    link.href = href;
    link.download = `smartpark-${new Date().toISOString().slice(0, 10)}.png`;
    link.click();
  };

  const clearImage = () => {
    setImageSrc('');
    setImageBase64('');
    setImageName('');
    setResult(null);
    setNaturalSize({ width: 0, height: 0 });
    setDraftSlots([]);
    setWorkingPoints([]);
  };

  const activeImage = result?.imageBase64
    ? result.imageBase64.startsWith('data:') ? result.imageBase64 : `data:image/png;base64,${result.imageBase64}`
    : imageSrc;

  return (
    <main className="noise min-h-[100dvh] bg-[#111820] text-[#e5ebed]">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark"><ScanLine size={19} strokeWidth={2.2} /></div>
          <div><div className="brand-name">smart<span>park</span></div><div className="brand-tag">CAMPUS OPERATIONS</div></div>
        </div>
        <div className="topbar-center"><span className="live-pip" /> LOCAL ANALYSIS <span className="topbar-divider" /> YOLO ENGINE</div>
          <div className="topbar-right"><span className="secure-label"><ShieldCheck size={14} /> PROJECT SERVICE · NO EXTERNAL AI</span><button className="icon-button help-button" aria-label="About SmartPark" title="Images are sent to this project's API worker for local YOLO inference; no external AI service is called"><CircleHelp size={17} /></button></div>
      </header>
      <div className="workspace">
        <section className="intro-row fade-in">
          <div>
            <div className="eyebrow"><span className="eyebrow-line" /> PARKING INTELLIGENCE <span className="mono">/ 01</span></div>
            <h1>Lot overview<span className="title-period">.</span></h1>
            <p className="intro-copy">Map a camera view, then run a precise occupancy read.</p>
          </div>
          <div className="intro-stamp"><div className="stamp-icon"><Activity size={16} /></div><div><span className="stamp-label">SYSTEM STATUS</span><strong><i /> READY FOR INPUT</strong></div></div>
        </section>

        <section className="control-strip fade-in">
          <div className="strip-cell camera-cell">
            <div className="strip-label"><Camera size={14} /> CAMERA VIEW</div>
            <div className="select-wrap">
              <select aria-label="Select camera configuration" data-testid="select-camera" value={isNaming ? '__new' : selectedId} onChange={(e) => {
                if (e.target.value === '__new') return;
                setSelectedId(e.target.value); setIsNaming(false); setWorkingPoints([]); setResult(null);
              }}>
                <option value="">Choose a saved camera…</option>
                {cameraList.map((camera) => <option key={camera.id} value={camera.id}>{camera.name} · {camera.spaces.length} spaces</option>)}
              </select><ChevronDown size={15} className="select-chevron" />
            </div>
          </div>
          <div className="strip-cell strip-meta">
            <span className="strip-label"><MapPin size={14} /> MAPPED SPACES</span>
            <strong className="strip-value mono">{(isNaming ? draftSlots.length : activeCamera?.spaces.length) ?? 0}<small> / SLOTS</small></strong>
          </div>
          <div className="strip-cell strip-meta confidence-cell">
            <span className="strip-label"><SlidersHorizontal size={14} /> CONFIDENCE</span>
            <div className="confidence-control"><input aria-label="Detection confidence" type="range" min="0.05" max="0.95" step="0.05" value={confidence} onChange={(e) => setConfidence(Number(e.target.value))} /><strong className="mono">{Math.round(confidence * 100)}%</strong></div>
          </div>
          <button className="strip-settings" aria-label="Toggle analysis settings" onClick={() => setShowSettings(!showSettings)}><SlidersHorizontal size={16} /><span>Settings</span></button>
        </section>
        {showSettings && <div className="settings-note fade-in"><div><strong>Detection threshold</strong><span>Higher confidence reduces uncertain detections. Recommended range: 30–50%.</span></div><button className="icon-button" onClick={() => setShowSettings(false)} aria-label="Close settings"><X size={15} /></button></div>}

        <div className="main-grid">
          <section className="visual-column fade-in">
            <div className="panel image-panel">
              <div className="panel-heading">
                <div><div className="panel-title"><span className="step-number">01</span> IMAGE CANVAS</div><div className="panel-subtitle">{imageSrc ? <><span className="file-dot" />{imageName} <span className="subtle-separator">·</span> {naturalSize.width.toLocaleString()} × {naturalSize.height.toLocaleString()} PX</> : 'UPLOAD A LOT IMAGE TO BEGIN'}</div></div>
                <div className="canvas-actions">
                  {imageSrc && <button className="small-button" onClick={() => fileInput.current?.click()}><RefreshCw size={13} /> Replace</button>}
                  {result && <button className="small-button export-button" onClick={downloadResult}><ArrowDownToLine size={14} /> Export PNG</button>}
                </div>
              </div>
              <input ref={fileInput} className="visually-hidden" type="file" accept="image/png,image/jpeg,.jpg,.jpeg" onChange={onFileChange} data-testid="input-image-upload" />
              <div className={`image-stage ${!imageSrc ? 'empty-stage' : ''} ${isNaming ? 'authoring-stage' : ''}`} onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); acceptFile(e.dataTransfer.files[0]); }}>
                {imageSrc ? (
                  <div className={`image-hitarea ${isNaming ? 'is-authoring' : ''}`} onClick={addPoint} role={isNaming ? 'button' : undefined} aria-label={isNaming ? 'Click four corners to map a parking space' : undefined}>
                    <img className="lot-image" src={activeImage} alt="Parking lot analysis canvas" />
                    <svg className="overlay-svg" viewBox={`0 0 ${naturalSize.width || result?.width || 1} ${naturalSize.height || result?.height || 1}`} preserveAspectRatio="none">
                      {!result && displayedSlots.map((slot, idx) => {
                        const scaleX = !isNaming && activeCamera ? naturalSize.width / activeCamera.referenceWidth : 1;
                        const scaleY = !isNaming && activeCamera ? naturalSize.height / activeCamera.referenceHeight : 1;
                        const mapped = slot.polygon.map((p) => ({ x: p.x * scaleX, y: p.y * scaleY }));
                        const points = mapped.map((p) => `${p.x},${p.y}`).join(' ');
                        const color = palette[idx % palette.length];
                        const center = mapped.reduce((acc, p) => ({ x: acc.x + p.x / 4, y: acc.y + p.y / 4 }), { x: 0, y: 0 });
                        const scale = (naturalSize.width || 1) / 1000;
                        return <g key={slot.id}><polygon points={points} fill={color} fillOpacity=".17" stroke={color} strokeWidth={Math.max(2, scale * 2.2)} vectorEffect="non-scaling-stroke" /><circle cx={center.x} cy={center.y} r={Math.max(11, scale * 12)} fill="#111820" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" /><text x={center.x} y={center.y} textAnchor="middle" dominantBaseline="central" fill={color} fontSize={Math.max(9, scale * 10)} fontFamily="DM Mono, monospace" fontWeight="500">{String(idx + 1).padStart(2, '0')}</text></g>;
                      })}
                      {isNaming && workingPoints.length > 0 && <g>
                        {workingPoints.length > 1 && <polyline points={workingPoints.map((p) => `${p.x},${p.y}`).join(' ')} fill="none" stroke="#2bd4a1" strokeWidth="2" strokeDasharray="5 4" vectorEffect="non-scaling-stroke" />}
                        {workingPoints.map((p, i) => <g key={i}><circle cx={p.x} cy={p.y} r="6" fill="#2bd4a1" stroke="#10201c" strokeWidth="2" vectorEffect="non-scaling-stroke" /><text x={p.x + 11} y={p.y - 10} fill="#eafff7" fontSize="12" fontFamily="DM Mono, monospace">{i + 1}</text></g>)}
                      </g>}
                    </svg>
                    {isNaming && <div className="canvas-hint"><Crosshair size={14} /> {workingPoints.length === 0 ? 'CLICK FOUR CORNERS · START TOP-LEFT, GO CLOCKWISE' : `CORNER ${workingPoints.length + 1} OF 4 · ${4 - workingPoints.length} LEFT`}</div>}
                  </div>
                ) : (
                  <button className="upload-dropzone" onClick={() => fileInput.current?.click()} data-testid="button-upload-image">
                    <div className="upload-symbol"><HardDriveUpload size={23} /></div><strong>Drop your lot image here</strong><span>or browse files to select an image</span><small>PNG · JPG · JPEG <b>·</b> LOCAL FILES ONLY</small>
                  </button>
                )}
                {analyze.isPending && <div className="analysis-overlay"><div className="analysis-scan" /><div className="analysis-status"><LoaderCircle size={18} className="spin" /><strong>Reading the lot…</strong><span>Running local vehicle detection</span></div></div>}
              </div>
              {uploadError && <div className="inline-error"><AlertCircle size={15} />{uploadError}</div>}
              {analyze.isError && <div className="inline-error"><AlertCircle size={15} />Analysis failed. Check your connection to the local analysis service and try again.</div>}
              {isNaming && <div className="authoring-footer">
                <div className="authoring-instructions"><span className="authoring-dot" /> <b>{workingPoints.length === 0 ? 'Click to trace a space' : `${workingPoints.length} / 4 corners`}</b><span>Each slot is a four-point polygon, ordered clockwise.</span></div>
                <button className="text-button" disabled={!workingPoints.length && !draftSlots.length} onClick={() => workingPoints.length ? setWorkingPoints((points) => points.slice(0, -1)) : setDraftSlots((slots) => slots.slice(0, -1))}><RefreshCw size={13} /> Undo last</button>
              </div>}
              {imageSrc && !isNaming && !result && <div className="canvas-footer"><span><span className="footer-indicator" /> {activeCamera ? `${activeCamera.spaces.length} MAPPED SLOTS` : 'NO CAMERA LAYOUT SELECTED'}</span><button className="text-button" onClick={clearImage}><X size={13} /> Clear image</button></div>}
              {result && <div className="canvas-footer result-footer"><span><span className="footer-indicator success" /> ANNOTATED RESULT <span className="subtle-separator">·</span> {result.width} × {result.height} PX</span><button className="text-button" onClick={clearImage}><X size={13} /> Clear result</button></div>}
            </div>

            <div className="panel layout-panel">
              <div className="layout-head"><div><div className="panel-title"><span className="step-number">02</span> CAMERA LAYOUT</div><div className="panel-subtitle">A layout belongs to one fixed camera view.</div></div><button className="outline-button" onClick={startCamera} data-testid="button-new-camera"><Plus size={15} /> New view</button></div>
              {isNaming ? (
                <div className="camera-editor fade-in">
                  <div className="editor-top"><div className="editor-icon"><Camera size={16} /></div><div><strong>Define a camera view</strong><span>Click four corners per parking space on the image above.</span></div><button className="icon-button" onClick={() => { setIsNaming(false); setWorkingPoints([]); setDraftSlots([]); }} aria-label="Cancel new camera"><X size={15} /></button></div>
                  <div className="editor-form">
                    <label className="field-label" htmlFor="camera-name">VIEW NAME</label>
                    <input id="camera-name" className="field-input" placeholder="e.g. North lot · Gate camera" value={cameraName} onChange={(e) => setCameraName(e.target.value)} data-testid="input-camera-name" />
                  </div>
                  <div className="editor-summary"><span>{draftSlots.length} mapped {draftSlots.length === 1 ? 'space' : 'spaces'}</span><span className="mono">{naturalSize.width} × {naturalSize.height}</span></div>
                  <div className="view-warning"><AlertCircle size={14} /><span>Coordinates are saved at this image's natural dimensions. Reuse this layout only with the same camera angle and framing.</span></div>
                  {saveCamera.isError && <div className="inline-error"><AlertCircle size={14} />Could not save this camera layout. Please retry.</div>}
                  <button className="primary-button save-layout" disabled={!cameraName.trim() || draftSlots.length === 0 || saveCamera.isPending} onClick={persistCamera} data-testid="button-save-camera">{saveCamera.isPending ? <LoaderCircle size={15} className="spin" /> : <Check size={15} />} {saveCamera.isPending ? 'Saving layout…' : 'Save camera layout'}</button>
                </div>
              ) : activeCamera ? (
                <div className="selected-layout fade-in">
                  <div className="layout-current">
                    <div className="camera-tile"><Camera size={17} /></div>
                    <div className="layout-details"><strong>{activeCamera.name}</strong><span>{activeCamera.spaces.length} mapped spaces <i /> {activeCamera.referenceWidth} × {activeCamera.referenceHeight}</span></div>
                    <div className="layout-actions"><button className="icon-button danger-on-hover" onClick={removeCamera} disabled={deleteCamera.isPending} aria-label="Delete camera layout" title="Delete camera layout"><Trash2 size={15} /></button><button className="icon-button" onClick={newCamera} aria-label="Create another camera view" title="Create another camera view"><Plus size={16} /></button></div>
                  </div>
                  <div className="space-chip-row">
                    {activeCamera.spaces.map((space, idx) => <span className="space-chip" key={space.id} style={{ '--slot-color': palette[idx % palette.length] } as CSSProperties}><i /> {space.id}</span>)}
                    {!activeCamera.spaces.length && <span className="muted-copy">This saved view has no mapped spaces.</span>}
                  </div>
                  <div className="reuse-note"><ShieldCheck size={14} /><span>Camera-specific mapping · {activeCamera.referenceWidth} × {activeCamera.referenceHeight} reference</span></div>
                  {deleteCamera.isError && <div className="inline-error"><AlertCircle size={14} />Unable to delete the selected layout.</div>}
                </div>
              ) : camerasLoading ? (
                <div className="skeleton-layout"><div className="skeleton-block" /><div className="skeleton-lines"><i /><i /></div></div>
              ) : camerasError ? (
                <div className="layout-empty error-empty"><AlertCircle size={17} /><div><strong>Camera layouts unavailable</strong><span>Saved layouts could not be loaded.</span></div><button className="text-button" onClick={() => refetch()}>Retry</button></div>
              ) : (
                <div className="layout-empty"><div className="empty-camera-icon"><Camera size={18} /></div><div><strong>No camera view selected</strong><span>Upload an image, then map its parking spaces.</span></div><button className="text-button" onClick={startCamera}><Plus size={13} /> Create layout</button></div>
              )}
            </div>
          </section>

          <aside className="results-column fade-in">
            <div className="panel run-panel">
              <div className="panel-title"><span className="step-number">03</span> OCCUPANCY READ</div>
              <p className="run-description">Analyze this frame against the selected camera layout.</p>
              <button className="primary-button analyze-button" onClick={runAnalysis} disabled={!canAnalyze} data-testid="button-analyze">
                {analyze.isPending ? <><LoaderCircle size={16} className="spin" /> Analyzing frame…</> : <><ScanLine size={16} /> Analyze parking lot <span className="button-arrow">→</span></>}
              </button>
              {!imageSrc && <div className="prereq"><span className="prereq-dot" /> Add a lot image to begin</div>}
              {imageSrc && !activeCamera && <div className="prereq"><span className="prereq-dot" /> Select or create a camera layout</div>}
              {activeCamera && activeCamera.spaces.length === 0 && <div className="prereq"><span className="prereq-dot" /> Map at least one parking space</div>}
            </div>
            {result ? (
              <>
                <div className={`occupancy-hero level-${occupancyTone} fade-in`}>
                  <div className="occupancy-label"><span className="result-check"><Check size={13} /></span> CURRENT OCCUPANCY <span className={`level-pill ${occupancyTone}`}>{result.occupancyLevel}</span></div>
                  <div className="occupancy-number">{result.occupancyPercent}<span>%</span></div>
                  <div className="occupancy-meter"><i style={{ width: `${Math.max(0, Math.min(result.occupancyPercent, 100))}%` }} /></div>
                  <div className="occupancy-caption"><span>{result.occupiedSpaces} occupied</span><span>{result.availableSpaces} available</span></div>
                </div>
                <div className="stat-grid fade-in">
                  <div className="stat-card"><span className="stat-title">TOTAL SPACES</span><strong>{result.totalSpaces.toLocaleString()}</strong><span className="stat-foot">IN THIS VIEW</span></div>
                  <div className="stat-card occupied-stat"><span className="stat-title">OCCUPIED</span><strong>{result.occupiedSpaces.toLocaleString()}</strong><span className="stat-foot"><i /> {result.totalSpaces ? Math.round((result.occupiedSpaces / result.totalSpaces) * 100) : 0}% OF CAPACITY</span></div>
                  <div className="stat-card available-stat"><span className="stat-title">AVAILABLE</span><strong>{result.availableSpaces.toLocaleString()}</strong><span className="stat-foot"><i /> READY TO PARK</span></div>
                  <div className="stat-card vehicle-stat"><span className="stat-title">VEHICLES FOUND</span><strong>{result.vehicles.length.toLocaleString()}</strong><span className="stat-foot">DETECTIONS</span></div>
                </div>
                <div className="panel detections-panel fade-in">
                  <div className="detection-head"><div className="panel-title">SPACE STATUS</div><span className="mono">{result.spaces.length} TOTAL</span></div>
                  {result.spaces.length ? <div className="space-status-list">{result.spaces.map((space) => <div className="space-status-row" key={space.id}><span className={`status-indicator ${space.status.toLowerCase()}`} /><span className="space-status-name">{space.id}</span><span className={`status-text ${space.status.toLowerCase()}`}>{space.status}</span></div>)}</div> : <div className="no-spaces"><MapPin size={15} /> No parking spaces returned for this analysis.</div>}
                  {!!result.vehicles.length && <div className="vehicle-summary"><span>DETECTIONS</span>{result.vehicles.map((vehicle, idx) => <span className="vehicle-pill" key={`${vehicle.label}-${idx}`}>{vehicle.label} <b>{Math.round(vehicle.confidence * 100)}%</b></span>)}</div>}
                </div>
                {!result.vehicles.length && <div className="no-vehicle-note fade-in"><div className="no-vehicle-icon"><ScanLine size={15} /></div><span><strong>No vehicles detected</strong><small>The frame was analyzed successfully; no vehicles met the current confidence threshold.</small></span></div>}
              </>
            ) : (
              <div className="results-empty">
                <div className="empty-graphic"><div className="empty-orbit orbit-one" /><div className="empty-orbit orbit-two" /><div className="empty-center"><ScanLine size={21} /></div><span className="orbit-dot dot-a" /><span className="orbit-dot dot-b" /><span className="orbit-dot dot-c" /></div>
                <div className="empty-overline">ANALYSIS STANDING BY</div>
                <h2>Your lot, at a glance.</h2>
                <p>Upload a frame and select its camera view to see live space occupancy.</p>
                <div className="empty-checklist"><div className={imageSrc ? 'complete' : ''}><span>{imageSrc ? <Check size={11} /> : '01'}</span> Image frame</div><div className={activeCamera ? 'complete' : ''}><span>{activeCamera ? <Check size={11} /> : '02'}</span> Camera layout</div><div className={result ? 'complete' : ''}><span>03</span> Occupancy read</div></div>
                <button className="secondary-upload" onClick={() => fileInput.current?.click()}><UploadCloud size={15} /> Upload lot image</button>
              </div>
            )}
          </aside>
        </div>
        <footer className="page-footer"><span>SMARTPARK <b>·</b> FACILITIES INTELLIGENCE</span><span>PROJECT-SERVICE INFERENCE <i /> NO THIRD-PARTY AI API</span></footer>
      </div>
    </main>
  );
}

function App() {
  return <QueryClientProvider client={queryClient}><AppWorkspace /></QueryClientProvider>;
}

export default App;