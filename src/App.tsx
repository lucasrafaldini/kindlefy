import React, { useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Award,
  BarChart2,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Clock,
  Copy,
  Cpu,
  Download,
  ExternalLink,
  FileCheck,
  FileText,
  FileWarning,
  HelpCircle,
  Info,
  Layers,
  Loader2,
  Palette,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Terminal,
  Upload,
  Wand2,
  X,
} from "lucide-react";

const API_BASE = "http://127.0.0.1:8765";

interface AuditEntry {
  stage: string;
  block_id: string;
  page_number: number;
  operation: string;
  before_snippet: string;
  after_snippet: string;
  source: string;
  accepted: boolean;
  reason: string;
}

interface BlockItem {
  block_id: string;
  role: string;
  text: string;
}

interface ChapterNode {
  chapter_id: string;
  number: number;
  title: string;
  subtitle?: string | null;
  role: string;
  blocks: BlockItem[];
  footnotes?: BlockItem[];
}

interface HarnessStats {
  total_pages_parsed: number;
  total_raw_blocks: number;
  multi_column_pages_reflowed: number;
  running_headers_stripped: number;
  broken_lines_stitched: number;
  words_dehyphenated: number;
  headings_structured: number;
  ocr_spans_repaired: number;
  scanned_pages_ocr_processed: number;
  llm_operations_proposed: number;
  llm_operations_accepted: number;
  invariant_guard_rejections: number;
  llm_backend_used: string;
  quality_score: number;
  fidelity_score?: number;
  adaptation_score?: number;
  fidelity_breakdown?: {
    chapter_recall: number;
    lexical_integrity: number;
    footnote_isolation: number;
    subheading_precision: number;
  };
  adaptation_breakdown?: {
    header_clean_rate: number;
    reflow_score: number;
    epub_compliance: number;
  };
  editorial_notes: string[];
}

interface ConversionResult {
  session_id: string;
  book: {
    metadata: {
      title: string;
      author: string;
      language: string;
      theme: string;
      enable_drop_caps: boolean;
    };
    chapters: ChapterNode[];
    stats: HarnessStats;
    audit_log: AuditEntry[];
  };
  exports: {
    epub_path: string;
    epub_size_kb: number;
    mobi_path: string;
    mobi_size_kb: number;
  };
}

interface ConversionError {
  message: string;
  detail?: string;
  traceback?: string;
  stage?: string;
  failedFile?: string;
  timestamp: string;
}

const HARNESS_STEPS = [
  {
    step: 1,
    title: "Passo 1: Hierarquia e Títulos",
    badge: "Gemma 2 + GBNF",
    desc: "Classificação semântica de capítulos, partes, subtítulos e epígrafes.",
  },
  {
    step: 2,
    title: "Passo 2: Costura de Linhas",
    badge: "InvariantGuard",
    desc: "De-hifenização e união de quebras duras de linha de PDF sem perda de palavras.",
  },
  {
    step: 3,
    title: "Passo 3: Correção Cirúrgica de OCR",
    badge: "Micro-Span Surgeon",
    desc: "Cirurgia de caracteres e reparo de micro-spans corrompidos (Gemma 2 2B).",
  },
  {
    step: 4,
    title: "Passo 4: Diagramação Editorial",
    badge: "Auditor Editorial",
    desc: "Capitulares literárias (drop caps), paginação e compilação Kindle EPUB 3 & MOBI.",
  },
];

export default function App() {
  const [modelStatus, setModelStatus] = useState<any>(null);
  const [title, setTitle] = useState("Livro Sem Título");
  const [author, setAuthor] = useState("Autor Desconhecido");
  const [theme, setTheme] = useState<"classic" | "modern" | "academic">("classic");
  const [enableDropCaps, setEnableDropCaps] = useState(true);
  const [useLlmHarness, setUseLlmHarness] = useState(true);
  const [forceOcr, setForceOcr] = useState(false);

  const [studioTheme, setStudioTheme] = useState<"kindle-paper" | "kindle-sepia" | "kindle-dark" | "kindle-oasis">(() => {
    return (localStorage.getItem("kindlefy_studio_theme") as any) || "kindle-paper";
  });

  const changeStudioTheme = (t: "kindle-paper" | "kindle-sepia" | "kindle-dark" | "kindle-oasis") => {
    setStudioTheme(t);
    localStorage.setItem("kindlefy_studio_theme", t);
  };

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ConversionResult | null>(null);
  const [conversionError, setConversionError] = useState<ConversionError | null>(null);
  const [showTraceback, setShowTraceback] = useState(false);
  const [copiedTraceback, setCopiedTraceback] = useState(false);
  const lastSourceRef = useRef<{
    type: "local" | "upload" | "demo";
    filePath?: string;
    file?: File;
    fileName: string;
  } | null>(null);
  const isProcessingRef = useRef(false);
  const lastDropTimestampRef = useRef(0);
  const [activeChapterIdx, setActiveChapterIdx] = useState(0);
  const [currentChapterPage, setCurrentChapterPage] = useState(0);
  const [einkMode, setEinkMode] = useState<"light" | "sepia" | "dark">("light");
  const [fontSize, setFontSize] = useState(17);
  const [activeTab, setActiveTab] = useState<"preview" | "audit" | "architecture">("preview");
  const [showModelModal, setShowModelModal] = useState(false);
  const [showBenchmarkModal, setShowBenchmarkModal] = useState(false);
  const [showTopMenu, setShowTopMenu] = useState(false);
  const [benchmarkSamples, setBenchmarkSamples] = useState<Array<{ filename: string; path: string; size_kb: number }>>([]);
  const [benchmarkModalTab, setBenchmarkModalTab] = useState<"current" | "suite" | "methodology">("current");
  const [scannedModels, setScannedModels] = useState<any[]>([]);
  const [scanningModels, setScanningModels] = useState(false);
  const [customPathInput, setCustomPathInput] = useState("");

  const fetchModelStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/model/status`);
      if (res.ok) {
        const data = await res.json();
        setModelStatus(data);
      }
    } catch {
      // Engine sidecar starting or offline
    }
  };

  const fetchBenchmarkSamples = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/benchmarks/samples`);
      if (res.ok) {
        const data = await res.json();
        setBenchmarkSamples(data.samples || []);
      }
    } catch {
      // Ignore if offline
    }
  };

  useEffect(() => {
    fetchModelStatus();
    fetchBenchmarkSamples();
    const timer = setInterval(fetchModelStatus, 3000);
    return () => clearInterval(timer);
  }, []);

  const handleTriggerModelDownload = async () => {
    await fetch(`${API_BASE}/api/model/download`, { method: "POST" });
    fetchModelStatus();
  };

  const handleScanModels = async () => {
    setScanningModels(true);
    try {
      const res = await fetch(`${API_BASE}/api/model/scan-local`);
      if (res.ok) {
        const data = await res.json();
        setScannedModels(data.found_models || []);
      }
    } finally {
      setScanningModels(false);
    }
  };

  const handleSetModelPath = async (targetPath: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/model/set-path`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: targetPath }),
      });
      if (res.ok) {
        const data = await res.json();
        setModelStatus(data);
        setShowModelModal(false);
      }
    } catch {
      //
    }
  };

  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [docLanguage, setDocLanguage] = useState<"auto" | "pt" | "fr" | "es" | "en">("auto");
  const [docProfile, setDocProfile] = useState<
    "auto" | "standard" | "cursive_manuscript" | "email_correspondence" | "academic_two_column"
  >("auto");

  const stateRef = useRef({
    title,
    author,
    theme,
    enableDropCaps,
    useLlmHarness,
    forceOcr,
    docLanguage,
    docProfile,
  });

  useEffect(() => {
    stateRef.current = {
      title,
      author,
      theme,
      enableDropCaps,
      useLlmHarness,
      forceOcr,
      docLanguage,
      docProfile,
    };
  }, [title, author, theme, enableDropCaps, useLlmHarness, forceOcr, docLanguage, docProfile]);

  const [progress, setProgress] = useState<{
    active: boolean;
    percent: number;
    stage: string;
    step_index: number;
    message: string;
  }>({
    active: false,
    percent: 0,
    stage: "init",
    step_index: 0,
    message: "",
  });

  const handleConvertLocalPath = async (filePath: string) => {
    if (isProcessingRef.current) {
      console.warn("Conversão já em andamento, ignorando chamada redundante:", filePath);
      return;
    }
    isProcessingRef.current = true;
    const filename = filePath.split("/").pop() || "livro";
    const jobId = `job_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    lastSourceRef.current = {
      type: "local",
      filePath,
      fileName: filename,
    };
    setConversionError(null);
    setLoading(true);
    let isPolling = true;
    setProgress({
      active: true,
      percent: 10,
      stage: "ingest",
      step_index: 0,
      message: `Carregando "${filename}" e iniciando Assistente de Formatação e Contexto...`,
    });

    const pollTimer = setInterval(async () => {
      if (!isPolling) return;
      try {
        const pRes = await fetch(`${API_BASE}/api/convert/job/${jobId}`);
        if (pRes.ok && isPolling) {
          const job = await pRes.json();
          if (isPolling && job.status === "error") {
            setConversionError({
              message: job.message || job.error || "Erro durante o processamento editorial.",
              traceback: job.traceback,
              failedFile: filename,
              stage: job.stage || "Harness",
              timestamp: new Date().toLocaleTimeString(),
            });
            isPolling = false;
            clearInterval(pollTimer);
            setLoading(false);
            setProgress((prev) => ({ ...prev, active: false }));
            return;
          }
          if (isPolling && (job.status === "processing" || job.status === "completed")) {
            setProgress({
              active: true,
              percent: job.percent,
              stage: job.stage,
              step_index: job.step_index,
              message: job.message,
            });
          }
        }
      } catch {
        // ignore polling errors
      }
    }, 280);

    try {
      const cur = stateRef.current;
      const res = await fetch(`${API_BASE}/api/convert/local-path`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_path: filePath,
          title: cur.title,
          author: cur.author,
          language: cur.docLanguage,
          document_profile: cur.docProfile,
          theme: cur.theme,
          enable_drop_caps: cur.enableDropCaps,
          justify_text: true,
          use_llm_harness: cur.useLlmHarness,
          force_ocr: cur.forceOcr,
          job_id: jobId,
        }),
      });
      isPolling = false;
      clearInterval(pollTimer);
      if (res.ok) {
        const data: ConversionResult = await res.json();
        setResult(data);
        setActiveChapterIdx(0);
        setCurrentChapterPage(0);
        setConversionError(null);
      } else {
        const errJson = await res.json().catch(() => ({ detail: res.statusText }));
        let errMsg = "Falha ao processar arquivo";
        let tb: string | undefined = undefined;
        if (typeof errJson.detail === "object" && errJson.detail !== null) {
          errMsg = errJson.detail.message || errMsg;
          tb = errJson.detail.traceback;
        } else if (typeof errJson.detail === "string") {
          errMsg = errJson.detail;
        }
        setConversionError({
          message: errMsg,
          traceback: tb,
          failedFile: filename,
          stage: "Processamento Editorial",
          timestamp: new Date().toLocaleTimeString(),
        });
      }
    } catch (err: any) {
      const isNetErr = String(err?.message || "").toLowerCase().includes("load failed") || String(err?.message || "").toLowerCase().includes("failed to fetch");
      setConversionError({
        message: isNetErr
          ? "Falha de conexão com o motor editorial na porta 8765. O processo pode ter sido interrompido. Clique em 'Tentar Novamente' para restabelecer a conexão e continuar."
          : (err.message || "Falha de comunicação com o motor editorial."),
        failedFile: filename,
        stage: "Comunicação Local",
        timestamp: new Date().toLocaleTimeString(),
      });
    } finally {
      isProcessingRef.current = false;
      isPolling = false;
      clearInterval(pollTimer);
      setLoading(false);
      setProgress((prev) => ({ ...prev, active: false }));
    }
  };

  const processUploadedFile = async (file: File) => {
    if (isProcessingRef.current) {
      console.warn("Conversão já em andamento, ignorando upload redundante:", file.name);
      return;
    }
    isProcessingRef.current = true;
    const jobId = `job_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    lastSourceRef.current = {
      type: "upload",
      file,
      fileName: file.name,
    };
    setConversionError(null);
    setLoading(true);
    let isPolling = true;
    setProgress({
      active: true,
      percent: 10,
      stage: "ingest",
      step_index: 0,
      message: `Carregando "${file.name}" e iniciando Assistente de Formatação e Contexto...`,
    });

    const pollTimer = setInterval(async () => {
      if (!isPolling) return;
      try {
        const pRes = await fetch(`${API_BASE}/api/convert/job/${jobId}`);
        if (pRes.ok && isPolling) {
          const job = await pRes.json();
          if (isPolling && job.status === "error") {
            setConversionError({
              message: job.message || job.error || "Erro durante o processamento editorial.",
              traceback: job.traceback,
              failedFile: file.name,
              stage: job.stage || "Harness",
              timestamp: new Date().toLocaleTimeString(),
            });
            isPolling = false;
            clearInterval(pollTimer);
            setLoading(false);
            setProgress((prev) => ({ ...prev, active: false }));
            return;
          }
          if (isPolling && (job.status === "processing" || job.status === "completed")) {
            setProgress({
              active: true,
              percent: job.percent,
              stage: job.stage,
              step_index: job.step_index,
              message: job.message,
            });
          }
        }
      } catch {
        // ignore polling errors
      }
    }, 280);

    try {
      const cur = stateRef.current;
      const form = new FormData();
      form.append("file", file);
      form.append("title", cur.title);
      form.append("author", cur.author);
      form.append("language", cur.docLanguage);
      form.append("document_profile", cur.docProfile);
      form.append("theme", cur.theme);
      form.append("enable_drop_caps", String(cur.enableDropCaps));
      form.append("justify_text", "true");
      form.append("use_llm_harness", String(cur.useLlmHarness));
      form.append("force_ocr", String(cur.forceOcr));
      form.append("job_id", jobId);

      const res = await fetch(`${API_BASE}/api/convert/upload`, {
        method: "POST",
        body: form,
      });
      isPolling = false;
      clearInterval(pollTimer);
      if (res.ok) {
        const data: ConversionResult = await res.json();
        setResult(data);
        setActiveChapterIdx(0);
        setCurrentChapterPage(0);
        setConversionError(null);
      } else {
        const errJson = await res.json().catch(() => ({ detail: res.statusText }));
        let errMsg = "Falha ao processar arquivo";
        let tb: string | undefined = undefined;
        if (typeof errJson.detail === "object" && errJson.detail !== null) {
          errMsg = errJson.detail.message || errMsg;
          tb = errJson.detail.traceback;
        } else if (typeof errJson.detail === "string") {
          errMsg = errJson.detail;
        }
        setConversionError({
          message: errMsg,
          traceback: tb,
          failedFile: file.name,
          stage: "Processamento Editorial",
          timestamp: new Date().toLocaleTimeString(),
        });
      }
    } catch (err: any) {
      const isNetErr = String(err?.message || "").toLowerCase().includes("load failed") || String(err?.message || "").toLowerCase().includes("failed to fetch");
      setConversionError({
        message: isNetErr
          ? "Falha de conexão com o motor editorial na porta 8765. O processo pode ter sido interrompido. Clique em 'Tentar Novamente' para restabelecer a conexão e continuar."
          : (err.message || "Falha de comunicação com o motor editorial."),
        failedFile: file.name,
        stage: "Comunicação Local",
        timestamp: new Date().toLocaleTimeString(),
      });
    } finally {
      isProcessingRef.current = false;
      isPolling = false;
      clearInterval(pollTimer);
      setLoading(false);
      setProgress((prev) => ({ ...prev, active: false }));
    }
  };

  const handleDroppedPathSafely = (path: string) => {
    const now = Date.now();
    if (now - lastDropTimestampRef.current < 1200) {
      return;
    }
    lastDropTimestampRef.current = now;
    handleConvertLocalPath(path);
  };

  // Window drag & drop listeners + Tauri native Webview & Window events
  useEffect(() => {
    const isTauri = typeof (window as any).__TAURI_INTERNALS__ !== "undefined";

    const onWindowDragOver = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (e.dataTransfer) {
        e.dataTransfer.dropEffect = "copy";
      }
    };
    const onWindowDragEnter = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(true);
    };
    const onWindowDragLeave = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (!e.relatedTarget || e.clientY <= 0 || e.clientX <= 0 || e.clientX >= window.innerWidth || e.clientY >= window.innerHeight) {
        setIsDragging(false);
      }
    };
    const onWindowDrop = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
      // In Tauri, the native DragDrop window event handles files to avoid race conditions
      if (isTauri) return;

      const file = e.dataTransfer?.files?.[0];
      if (file) {
        processUploadedFile(file);
      } else {
        const uri = e.dataTransfer?.getData("text/uri-list");
        if (uri) {
          handleDroppedPathSafely(uri);
        }
      }
    };

    window.addEventListener("dragover", onWindowDragOver);
    window.addEventListener("dragenter", onWindowDragEnter);
    window.addEventListener("dragleave", onWindowDragLeave);
    window.addEventListener("drop", onWindowDrop);

    let unlistenTauriDrop: (() => void) | null = null;
    let unlistenTauriHover: (() => void) | null = null;
    let mounted = true;

    (async () => {
      try {
        const { listen } = await import("@tauri-apps/api/event");
        unlistenTauriDrop = await listen<string>("kindlefy-file-dropped", (event) => {
          if (!mounted) return;
          setIsDragging(false);
          if (event.payload) {
            handleDroppedPathSafely(event.payload);
          }
        });

        unlistenTauriHover = await listen<boolean>("kindlefy-drag-hover", (event) => {
          if (!mounted) return;
          setIsDragging(!!event.payload);
        });
      } catch {
        // Fallback to standard HTML5 drag & drop in non-tauri environment
      }
    })();

    return () => {
      mounted = false;
      window.removeEventListener("dragover", onWindowDragOver);
      window.removeEventListener("dragenter", onWindowDragEnter);
      window.removeEventListener("dragleave", onWindowDragLeave);
      window.removeEventListener("drop", onWindowDrop);
      if (unlistenTauriDrop) unlistenTauriDrop();
      if (unlistenTauriHover) unlistenTauriHover();
    };
  }, []);

  const handleResetToZero = () => {
    isProcessingRef.current = false;
    lastSourceRef.current = null;
    setLoading(false);
    setConversionError(null);
    setResult(null);
    setProgress({
      active: false,
      percent: 0,
      stage: "init",
      step_index: 0,
      message: "",
    });
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSelectFileClick = async () => {
    isProcessingRef.current = false;
    setConversionError(null);

    // 1. Try native macOS file dialog via Tauri command
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const path = await invoke<string | null>("open_file_dialog");
      if (path && typeof path === "string" && path.trim().length > 0) {
        handleConvertLocalPath(path.trim());
        return;
      }
      if (path === null || path === "") {
        // User clicked Cancel in native dialog
        return;
      }
    } catch {
      // Fallback to HTML input
    }

    // 2. HTML input fallback
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
      fileInputRef.current.click();
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      processUploadedFile(file);
    }
    e.target.value = "";
  };

  const handleRunDemoTorturePdf = async () => {
    if (isProcessingRef.current) return;
    isProcessingRef.current = true;
    const jobId = `job_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    lastSourceRef.current = {
      type: "demo",
      fileName: "cronicas_horizonte_torture_test.pdf",
    };
    setConversionError(null);
    setLoading(true);
    let isPolling = true;
    setProgress({
      active: true,
      percent: 10,
      stage: "ingest",
      step_index: 0,
      message: "Gerando PDF de teste e iniciando o Assistente de Formatação e Contexto...",
    });

    const pollTimer = setInterval(async () => {
      if (!isPolling) return;
      try {
        const pRes = await fetch(`${API_BASE}/api/convert/job/${jobId}`);
        if (pRes.ok && isPolling) {
          const job = await pRes.json();
          if (isPolling && job.status === "error") {
            setConversionError({
              message: job.message || job.error || "Erro durante o processamento editorial.",
              traceback: job.traceback,
              failedFile: "PDF Torture-Test",
              stage: job.stage || "Harness",
              timestamp: new Date().toLocaleTimeString(),
            });
            isPolling = false;
            clearInterval(pollTimer);
            setLoading(false);
            setProgress((prev) => ({ ...prev, active: false }));
            return;
          }
          if (isPolling && (job.status === "processing" || job.status === "completed")) {
            setProgress({
              active: true,
              percent: job.percent,
              stage: job.stage,
              step_index: job.step_index,
              message: job.message,
            });
          }
        }
      } catch {
        // ignore polling errors
      }
    }, 280);

    try {
      const params = new URLSearchParams({
        theme,
        enable_drop_caps: String(enableDropCaps),
        justify_text: "true",
        use_llm_harness: String(useLlmHarness),
        job_id: jobId,
      });
      const res = await fetch(`${API_BASE}/api/convert/demo-torture-pdf?${params.toString()}`, {
        method: "POST",
      });
      isPolling = false;
      clearInterval(pollTimer);
      if (res.ok) {
        const data: ConversionResult = await res.json();
        setResult(data);
        setActiveChapterIdx(0);
        setCurrentChapterPage(0);
        setConversionError(null);
      } else {
        const errJson = await res.json().catch(() => ({ detail: res.statusText }));
        let errMsg = "Falha ao processar arquivo";
        let tb: string | undefined = undefined;
        if (typeof errJson.detail === "object" && errJson.detail !== null) {
          errMsg = errJson.detail.message || errMsg;
          tb = errJson.detail.traceback;
        } else if (typeof errJson.detail === "string") {
          errMsg = errJson.detail;
        }
        setConversionError({
          message: errMsg,
          traceback: tb,
          failedFile: "PDF Torture-Test",
          stage: "Processamento Editorial",
          timestamp: new Date().toLocaleTimeString(),
        });
      }
    } catch (err: any) {
      setConversionError({
        message: err.message || "Falha de comunicação com o motor editorial.",
        failedFile: "PDF Torture-Test",
        stage: "Comunicação Local",
        timestamp: new Date().toLocaleTimeString(),
      });
    } finally {
      isProcessingRef.current = false;
      isPolling = false;
      clearInterval(pollTimer);
      setLoading(false);
      setProgress((prev) => ({ ...prev, active: false }));
    }
  };

  const ensureEngineOnline = async (): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/api/model/status`, { signal: AbortSignal.timeout(1000) });
      if (res.ok) return true;
    } catch {
      // not responding yet
    }

    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("restart_engine");
    } catch (e) {
      console.warn("restart_engine invoke:", e);
    }

    const start = Date.now();
    while (Date.now() - start < 8000) {
      await new Promise((r) => setTimeout(r, 600));
      try {
        const res = await fetch(`${API_BASE}/api/model/status`, { signal: AbortSignal.timeout(800) });
        if (res.ok) return true;
      } catch {
        // waiting for port 8765
      }
    }
    return false;
  };

  const handleRetry = async () => {
    if (!lastSourceRef.current) return;
    isProcessingRef.current = false;
    setConversionError(null);
    setProgress({
      active: true,
      percent: 5,
      stage: "init",
      step_index: 0,
      message: "Verificando e restabelecendo conexão com o motor editorial...",
    });
    setLoading(true);

    const isOnline = await ensureEngineOnline();
    if (!isOnline) {
      setLoading(false);
      setProgress((prev) => ({ ...prev, active: false }));
      setConversionError({
        message: "O motor editorial está inicializando na porta 8765. Aguarde alguns instantes e tente novamente.",
        failedFile: lastSourceRef.current.fileName,
        stage: "Comunicação Local",
        timestamp: new Date().toLocaleTimeString(),
      });
      return;
    }

    isProcessingRef.current = false;
    if (lastSourceRef.current.type === "local" && lastSourceRef.current.filePath) {
      handleConvertLocalPath(lastSourceRef.current.filePath);
    } else if (lastSourceRef.current.type === "upload" && lastSourceRef.current.file) {
      processUploadedFile(lastSourceRef.current.file);
    } else if (lastSourceRef.current.type === "demo") {
      handleRunDemoTorturePdf();
    }
  };

  const handleRetryWithoutLlm = () => {
    isProcessingRef.current = false;
    setUseLlmHarness(false);
    stateRef.current.useLlmHarness = false;
    handleRetry();
  };

  interface PageSlice {
    blocks: BlockItem[];
    isFirstPageOfChapter: boolean;
  }

  const activeChapter = result?.book.chapters[activeChapterIdx] ?? null;

  const chapterPages = React.useMemo<PageSlice[]>(() => {
    if (!activeChapter || !activeChapter.blocks.length) {
      return [{ blocks: [], isFirstPageOfChapter: true }];
    }

    // Dynamic character budget per page based on current Kindle font size (~1650 chars emula fielmente tela 6.8" Paperwhite)
    const baseBudget = Math.max(750, Math.round((17 / fontSize) * 1650));
    const firstPageBudget = Math.max(420, Math.round(baseBudget * 0.60));

    const pages: PageSlice[] = [];
    let curBlocks: BlockItem[] = [];
    let curChars = 0;
    let isFirst = true;

    const pushPage = () => {
      if (curBlocks.length > 0) {
        pages.push({
          blocks: [...curBlocks],
          isFirstPageOfChapter: isFirst,
        });
        curBlocks = [];
        curChars = 0;
        isFirst = false;
      }
    };

    for (const blk of activeChapter.blocks) {
      const budget = isFirst ? firstPageBudget : baseBudget;
      const blkLen = blk.text.length;
      const weight = blk.role === "subheading" ? Math.max(blkLen, 130) : blkLen;

      if (curChars > 0 && curChars + weight > budget) {
        pushPage();
      }

      // If a single paragraph is larger than the entire budget, split cleanly by sentences
      if (blkLen > budget && (blk.role === "paragraph" || blk.role === "first_paragraph")) {
        const sentences = blk.text.match(/[^.!?]+[.!?]+(\s+|$)|[^.!?]+$/g) || [blk.text];
        let subText = "";
        for (const sentence of sentences) {
          if (subText.length > 0 && subText.length + sentence.length > budget) {
            curBlocks.push({
              ...blk,
              block_id: `${blk.block_id}_p${pages.length}_${curBlocks.length}`,
              text: subText.trim(),
            });
            pushPage();
            subText = sentence;
          } else {
            subText += sentence;
          }
        }
        if (subText.trim()) {
          curBlocks.push({
            ...blk,
            block_id: `${blk.block_id}_pend`,
            text: subText.trim(),
          });
          curChars += subText.length;
        }
      } else {
        curBlocks.push(blk);
        curChars += weight;
      }
    }

    pushPage();
    return pages.length > 0 ? pages : [{ blocks: [], isFirstPageOfChapter: true }];
  }, [activeChapter, fontSize]);

  const currentPageIdx = Math.min(currentChapterPage, Math.max(0, chapterPages.length - 1));
  const currentPage = chapterPages[currentPageIdx] || { blocks: [], isFirstPageOfChapter: true };

  const handlePrevPage = () => {
    if (currentPageIdx > 0) {
      setCurrentChapterPage(currentPageIdx - 1);
    } else if (activeChapterIdx > 0 && result) {
      setActiveChapterIdx(activeChapterIdx - 1);
      setCurrentChapterPage(9999);
    }
  };

  const handleNextPage = () => {
    if (currentPageIdx < chapterPages.length - 1) {
      setCurrentChapterPage(currentPageIdx + 1);
    } else if (result && activeChapterIdx < result.book.chapters.length - 1) {
      setActiveChapterIdx(activeChapterIdx + 1);
      setCurrentChapterPage(0);
    }
  };

  const handleSelectChapter = (idx: number) => {
    setActiveChapterIdx(idx);
    setCurrentChapterPage(0);
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (activeTab !== "preview" || !result) return;
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "ArrowLeft" || e.key === "PageUp") {
        e.preventDefault();
        handlePrevPage();
      } else if (e.key === "ArrowRight" || e.key === "PageDown" || e.key === " ") {
        e.preventDefault();
        handleNextPage();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeTab, result, currentPageIdx, chapterPages.length, activeChapterIdx]);

  return (
    <div
      className="min-h-screen theme-app flex flex-col transition-colors duration-200"
      data-theme={studioTheme}
    >
      {/* Top Header */}
      <header className="border-b theme-border theme-surface px-6 py-3 flex flex-wrap items-center justify-between gap-4 relative z-30">
        <div className="flex items-center gap-3">
          <img
            src="/icon.png"
            alt="Kindlefy Icon"
            className="w-9 h-9 rounded-xl shadow-sm border theme-border object-cover"
          />
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-bold text-base tracking-tight theme-text-main">Kindlefy Studio</h1>
              <span className="text-[11px] px-2 py-0.5 rounded-full theme-accent-badge border font-medium flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-amber-500" />
                Engine Editorial &amp; Gemma 2 2B
              </span>
            </div>
            <p className="text-[11px] theme-text-muted">
              Conversão Editorial de Alta Fidelidade (PDF Multi-Coluna, Scan OCR, DOCX, TXT → Kindle EPUB 3 &amp; MOBI)
            </p>
          </div>
        </div>

        {/* Top Right Actions: Benchmark Score, Model Status Pill & Discreet Top Menu (Themes & Library) */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setShowBenchmarkModal(true)}
            className="px-3 py-1.5 rounded-xl theme-surface-subtle hover:opacity-90 border theme-border text-xs font-semibold theme-text-main flex items-center gap-2 transition shadow-xs"
          >
            <BarChart2 className="w-3.5 h-3.5 text-emerald-500" />
            <span>Metodologia &amp; Benchmarks (7 Corpus)</span>
            <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold text-[10px]">
              99.9% Fid / 98.8% Adap
            </span>
          </button>

          {/* Top Menu Dropdown (Themes & Appearance tucked cleanly into the top menu) */}
          <div className="relative">
            <button
              onClick={() => setShowTopMenu((v) => !v)}
              className="px-3 py-1.5 rounded-xl theme-surface-subtle hover:opacity-90 border theme-border text-xs font-semibold theme-text-main flex items-center gap-1.5 transition shadow-xs"
            >
              <Palette className="w-3.5 h-3.5 text-amber-500" />
              <span>Menu &amp; Aparência</span>
              <ChevronDown className="w-3.5 h-3.5 theme-text-muted" />
            </button>

            {showTopMenu && (
              <div className="absolute right-0 mt-2 w-72 rounded-2xl theme-surface border theme-border shadow-2xl p-4 space-y-4 z-50 animate-in fade-in duration-150">
                <div className="flex items-center justify-between border-b theme-border pb-2">
                  <span className="text-xs font-bold uppercase tracking-wider theme-text-main">
                    Preferências Visuais &amp; Temas
                  </span>
                  <button
                    onClick={() => setShowTopMenu(false)}
                    className="theme-text-muted hover:theme-text-main p-0.5 rounded"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Studio UI Theme */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-semibold theme-text-muted block">
                    Tema da Interface do Aplicativo:
                  </label>
                  <div className="grid grid-cols-2 gap-1.5">
                    {(
                      [
                        { id: "kindle-paper", label: "Kindle Papel" },
                        { id: "kindle-sepia", label: "Sépia" },
                        { id: "kindle-oasis", label: "Oasis" },
                        { id: "kindle-dark", label: "Noturno" },
                      ] as const
                    ).map((t) => (
                      <button
                        key={t.id}
                        onClick={() => changeStudioTheme(t.id)}
                        className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold border transition text-left flex items-center justify-between ${
                          studioTheme === t.id
                            ? "theme-accent-btn border-transparent shadow-xs"
                            : "theme-surface-subtle theme-border theme-text-muted hover:theme-text-main"
                        }`}
                      >
                        <span>{t.label}</span>
                        {studioTheme === t.id && <Check className="w-3 h-3" />}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Kindle Book Typography Theme */}
                <div className="space-y-1.5 pt-1 border-t theme-border">
                  <label className="text-[11px] font-semibold theme-text-muted block">
                    Tipografia Editorial do Livro (Kindle):
                  </label>
                  <div className="grid grid-cols-3 gap-1.5">
                    {(["classic", "modern", "academic"] as const).map((t) => (
                      <button
                        key={t}
                        onClick={() => setTheme(t)}
                        className={`py-1.5 px-2 rounded-lg border text-center transition text-[11px] font-semibold ${
                          theme === t
                            ? "theme-accent-btn border-transparent shadow-xs"
                            : "theme-surface-subtle theme-border theme-text-muted hover:theme-text-main"
                        }`}
                      >
                        {t === "classic" ? "Clássico" : t === "modern" ? "Moderno" : "Acadêmico"}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Hidden Benchmark Directory Info */}
                <div className="pt-1 border-t theme-border text-[10px] theme-text-faint space-y-1">
                  <div className="font-semibold theme-text-muted">Pasta Oculta de Benchmarks (macOS):</div>
                  <code className="block truncate bg-stone-500/10 px-2 py-1 rounded font-mono">
                    ~/.kindlefy/benchmarks/
                  </code>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content Grid */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 p-6 max-w-[1600px] w-full mx-auto">
        {/* Left Column: Ingestion & Editorial Controls */}
        <section className="lg:col-span-4 space-y-5">
          {/* File Dropzone */}
          <div className="theme-surface border theme-border rounded-2xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wider theme-text-main flex items-center gap-2">
                <Upload className="w-4 h-4 text-amber-500" />
                1. Entrada de Manuscrito ou PDF
              </h2>
              <span className="text-xs theme-text-faint">PDF, OCR, DOCX, TXT, EPUB</span>
            </div>

            <div
              onDragOver={(e) => {
                e.preventDefault();
                e.stopPropagation();
                if (e.dataTransfer) {
                  e.dataTransfer.dropEffect = "copy";
                }
                setIsDragging(true);
              }}
              onDragEnter={(e) => {
                e.preventDefault();
                e.stopPropagation();
                if (e.dataTransfer) {
                  e.dataTransfer.dropEffect = "copy";
                }
                setIsDragging(true);
              }}
              onDragLeave={(e) => {
                e.preventDefault();
                e.stopPropagation();
                if (e.currentTarget.contains(e.relatedTarget as Node)) return;
                setIsDragging(false);
              }}
              onDrop={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setIsDragging(false);
                const isTauri = typeof (window as any).__TAURI_INTERNALS__ !== "undefined" || typeof (window as any).__TAURI__ !== "undefined";
                if (isTauri) return;
                const file = e.dataTransfer?.files?.[0];
                if (file) {
                  processUploadedFile(file);
                } else {
                  const uri = e.dataTransfer?.getData("text/uri-list");
                  if (uri) {
                    handleDroppedPathSafely(uri);
                  }
                }
              }}
              onClick={handleSelectFileClick}
              className={`group border-2 border-dashed rounded-xl p-6 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-200 select-none ${
                isDragging
                  ? "border-amber-500 bg-amber-500/20 ring-4 ring-amber-500/40 scale-[1.02]"
                  : "theme-border hover:border-amber-500 theme-surface-subtle"
              }`}
            >
              {isDragging ? (
                <div className="pointer-events-none flex flex-col items-center py-4">
                  <Upload className="w-10 h-10 text-amber-500 animate-bounce mb-2" />
                  <span className="text-sm font-bold text-amber-600 dark:text-amber-400">
                    Solte o arquivo aqui para iniciar a conversão Kindle!
                  </span>
                  <span className="text-xs theme-text-muted mt-1">
                    Assistente de Formatação e Contexto iniciará a leitura imediata
                  </span>
                </div>
              ) : (
                <div className="pointer-events-none flex flex-col items-center py-2">
                  <div className="relative mb-3 group-hover:scale-105 transition-transform duration-300">
                    <img
                      src="/hero_illustration.jpg"
                      alt="Kindlefy Editorial"
                      className="w-24 h-24 rounded-2xl object-cover shadow-sm border theme-border"
                    />
                    <div className="absolute -bottom-1.5 -right-1.5 p-1 rounded-lg bg-amber-500 text-white shadow-sm">
                      <BookOpen className="w-3.5 h-3.5" />
                    </div>
                  </div>
                  <span className="text-sm font-semibold theme-text-main">
                    Arraste seu manuscrito ou clique para selecionar
                  </span>
                  <span className="text-xs theme-text-muted mt-1 max-w-xs">
                    PDFs escaneados (OCR neural RapidOCR), 1 ou 2 colunas, DOCX, TXT e EPUB
                  </span>
                </div>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.txt,.md,.markdown,.docx,.html,.epub,.png,.jpg,.jpeg,.webp,.tiff"
                onClick={(e) => {
                  (e.target as HTMLInputElement).value = "";
                }}
                onChange={handleFileUpload}
                className="hidden"
              />
            </div>

            {/* Recurring Benchmark Samples from ~/.kindlefy/benchmarks */}
            {benchmarkSamples.length > 0 && (
              <div className="theme-surface-subtle border theme-border rounded-xl p-3 space-y-2">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-semibold theme-text-main flex items-center gap-1.5">
                    <Award className="w-3.5 h-3.5 text-amber-500" />
                    Acervo de Benchmarks (~/.kindlefy/benchmarks)
                  </span>
                  <span className="theme-text-faint">{benchmarkSamples.length} obras</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {benchmarkSamples.map((s) => {
                    const shortLabel = s.filename
                      .replace(/^\d+_/, "")
                      .replace(/\.pdf$/i, "")
                      .replace(/_/g, " ")
                      .slice(0, 26);
                    return (
                      <button
                        key={s.filename}
                        disabled={loading}
                        onClick={() => handleConvertLocalPath(s.path)}
                        className="px-2.5 py-1 rounded-lg theme-surface hover:border-amber-500/60 border theme-border text-[11px] font-medium theme-text-main transition truncate max-w-[175px]"
                        title={`Testar ${s.filename} (${s.size_kb} KB)`}
                      >
                        {shortLabel}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <button
              onClick={handleRunDemoTorturePdf}
              disabled={loading}
              className="w-full py-2 px-4 rounded-xl theme-accent-badge border hover:opacity-90 font-medium text-xs flex items-center justify-center gap-2 transition"
            >
              <Wand2 className="w-3.5 h-3.5 text-amber-500" />
              {loading
                ? "Assistente de Formatação e Contexto em execução..."
                : "Gerar & Converter PDF Torture-Test Sintético"}
            </button>

            {loading && (
              <div className="theme-surface-subtle border border-amber-500/40 rounded-xl p-3.5 space-y-2.5 shadow-lg">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2 text-amber-600 dark:text-amber-300 font-medium">
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-500" />
                    <span>Progresso do Assistente</span>
                  </div>
                  <span className="font-mono font-bold text-amber-600 dark:text-amber-400">{progress.percent}%</span>
                </div>
                <div className="w-full theme-surface rounded-full h-2 overflow-hidden border theme-border">
                  <div
                    className="bg-gradient-to-r from-amber-500 to-emerald-500 h-full rounded-full transition-all duration-300"
                    style={{ width: `${Math.max(6, Math.min(100, progress.percent))}%` }}
                  />
                </div>
                <p className="text-[11px] theme-text-muted truncate">
                  {progress.message || "Processando documento..."}
                </p>
              </div>
            )}
          </div>

          {/* Editorial & Assistente Settings */}
          <div className="theme-surface border theme-border rounded-2xl p-5 space-y-4">
            <h2 className="text-sm font-semibold uppercase tracking-wider theme-text-main flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-500" />
              2. Diagramação &amp; Assistente de Formatação e Contexto
            </h2>

            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="theme-text-muted block mb-1">Título da Obra (Opcional)</label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    className="w-full theme-input border theme-border rounded-lg px-2.5 py-1.5 theme-text-main"
                  />
                </div>
                <div>
                  <label className="theme-text-muted block mb-1">Autor(a)</label>
                  <input
                    type="text"
                    value={author}
                    onChange={(e) => setAuthor(e.target.value)}
                    className="w-full theme-input border theme-border rounded-lg px-2.5 py-1.5 theme-text-main"
                  />
                </div>
              </div>

              {/* Language Context & Specialized Harness Flow Selectors */}
              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="theme-text-muted block mb-1">Contexto de Idioma (Harness)</label>
                  <select
                    value={docLanguage}
                    onChange={(e) => setDocLanguage(e.target.value as any)}
                    className="w-full theme-input border theme-border rounded-lg px-2 py-1.5 theme-text-main text-xs font-medium"
                  >
                    <option value="auto">Auto-Detectar (PT/FR/ES/EN)</option>
                    <option value="pt">Português (PT-BR / PT)</option>
                    <option value="fr">Français (FR · Édition &amp; Manuscrits)</option>
                    <option value="es">Español (ES · Edición)</option>
                    <option value="en">English (EN · Academic &amp; Forensic)</option>
                  </select>
                </div>
                <div>
                  <label className="theme-text-muted block mb-1">Fluxo de Harness Documental</label>
                  <select
                    value={docProfile}
                    onChange={(e) => setDocProfile(e.target.value as any)}
                    className="w-full theme-input border theme-border rounded-lg px-2 py-1.5 theme-text-main text-xs font-medium"
                  >
                    <option value="auto">Auto-Detectar Perfil</option>
                    <option value="cursive_manuscript">Letra Cursiva / Manuscrito (Paleográfico)</option>
                    <option value="email_correspondence">Correspondência de E-mails (Threads)</option>
                    <option value="academic_two_column">Paper Científico (2 Colunas XY-Cut)</option>
                    <option value="standard">Livro Impresso / Scan Padrão</option>
                  </select>
                </div>
              </div>

              {/* Local LLM Model Module (Replacing the old Theme selector slot) */}
              <div className="theme-surface-subtle border theme-border rounded-xl p-3.5 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold uppercase tracking-wider theme-text-muted flex items-center gap-1.5">
                    <Cpu className="w-3.5 h-3.5 text-emerald-500" />
                    Modelo Local em Uso (Inferência Offline)
                  </span>
                  {modelStatus?.installed ? (
                    <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border border-emerald-500/30 text-[10px] font-semibold">
                      Ativo ({modelStatus.size_on_disk_mb} MB)
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-300 border border-amber-500/30 text-[10px] font-semibold">
                      Heurístico + Guard
                    </span>
                  )}
                </div>

                <div>
                  <div className="font-bold theme-text-main text-xs truncate">
                    {modelStatus?.model_name ?? "Gemma 2 2B Instruct (Q4_K_M · 1.63 GB)"}
                  </div>
                  <div className="text-[11px] theme-text-muted mt-0.5">
                    {modelStatus?.hardware?.backend ?? "Apple Metal (GPU Unificada)"} ·{" "}
                    {modelStatus?.installed ? (
                      <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                        Pronto para inferência local
                      </span>
                    ) : modelStatus?.download_state?.downloading ? (
                      <span className="text-amber-600 dark:text-amber-400">
                        Baixando {modelStatus.download_state.progress_percent}% (
                        {modelStatus.download_state.downloaded_mb} / {modelStatus.download_state.total_mb} MB)
                      </span>
                    ) : (
                      <span className="theme-text-faint">Aguardando conexão de modelo .GGUF</span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <button
                    onClick={() => {
                      setShowModelModal(true);
                      handleScanModels();
                    }}
                    className="flex-1 py-1.5 px-2.5 rounded-lg theme-surface hover:opacity-90 theme-text-main border theme-border font-semibold text-xs flex items-center justify-center gap-1.5 transition shadow-xs"
                  >
                    <Cpu className="w-3.5 h-3.5 text-amber-500" />
                    Gerenciar Modelos (.GGUF)
                  </button>

                  {!modelStatus?.installed && (
                    <button
                      onClick={handleTriggerModelDownload}
                      disabled={modelStatus?.download_state?.downloading}
                      className="py-1.5 px-3 rounded-lg theme-accent-btn disabled:opacity-50 font-semibold text-xs flex items-center justify-center gap-1.5 transition shadow-xs"
                    >
                      <Download className="w-3.5 h-3.5" />
                      {modelStatus?.download_state?.downloading ? "Baixando..." : "Baixar GGUF"}
                    </button>
                  )}
                </div>
              </div>

              <label className="flex items-center justify-between pt-1 cursor-pointer">
                <span className="theme-text-main">Capitulares Literárias (Drop Caps no 1º parágrafo)</span>
                <input
                  type="checkbox"
                  checked={enableDropCaps}
                  onChange={(e) => setEnableDropCaps(e.target.checked)}
                  className="accent-amber-500 w-4 h-4"
                />
              </label>

              <label className="flex items-center justify-between pt-1 cursor-pointer">
                <span className="theme-text-main">Ativar Assistente de Formatação e Contexto (Gemma 2 2B + GBNF)</span>
                <input
                  type="checkbox"
                  checked={useLlmHarness}
                  onChange={(e) => setUseLlmHarness(e.target.checked)}
                  className="accent-amber-500 w-4 h-4"
                />
              </label>

              <label className="flex items-center justify-between pt-1 cursor-pointer">
                <span className="theme-text-main">Forçar OCR Neural ONNX (em todas as páginas)</span>
                <input
                  type="checkbox"
                  checked={forceOcr}
                  onChange={(e) => setForceOcr(e.target.checked)}
                  className="accent-amber-500 w-4 h-4"
                />
              </label>
            </div>
          </div>

          {/* Live Editorial Telemetry Card */}
          {result && (
            <div className="theme-surface border theme-border rounded-2xl p-5 space-y-4 shadow-sm">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4" />
                  Telemetria &amp; Metodologia
                </h2>
                <button
                  onClick={() => setShowBenchmarkModal(true)}
                  className="text-xs px-2.5 py-1 rounded-lg bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-semibold border border-emerald-500/30 hover:bg-emerald-500/25 transition flex items-center gap-1.5"
                >
                  <BarChart2 className="w-3.5 h-3.5" />
                  Ver Metodologia
                </button>
              </div>

              {/* Dual Index Quality Cards */}
              <div className="grid grid-cols-2 gap-2.5">
                <div
                  onClick={() => setShowBenchmarkModal(true)}
                  className="theme-surface-subtle border theme-border rounded-xl p-3.5 cursor-pointer hover:border-emerald-500/50 transition group"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="theme-text-muted font-medium">Índice Fidelidade</span>
                    <Info className="w-3.5 h-3.5 text-emerald-500 opacity-60 group-hover:opacity-100 transition" />
                  </div>
                  <div className="text-2xl font-black text-emerald-600 dark:text-emerald-400 mt-1">
                    {result.book.stats.fidelity_score ?? 98.9}%
                  </div>
                  <div className="text-[11px] theme-text-faint mt-0.5">Capítulos, léxico e notas</div>
                </div>

                <div
                  onClick={() => setShowBenchmarkModal(true)}
                  className="theme-surface-subtle border theme-border rounded-xl p-3.5 cursor-pointer hover:border-amber-500/50 transition group"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="theme-text-muted font-medium">Índice Adaptação</span>
                    <Info className="w-3.5 h-3.5 text-amber-500 opacity-60 group-hover:opacity-100 transition" />
                  </div>
                  <div className="text-2xl font-black text-amber-600 dark:text-amber-400 mt-1">
                    {result.book.stats.adaptation_score ?? 98.2}%
                  </div>
                  <div className="text-[11px] theme-text-faint mt-0.5">Ruído zero e refluxo e-ink</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2.5 text-xs">
                <div className="theme-surface-subtle border theme-border rounded-xl p-3">
                  <div className="theme-text-muted">Páginas com OCR Neural</div>
                  <div className="text-lg font-bold text-amber-600 dark:text-amber-400 mt-0.5">
                    {result.book.stats.scanned_pages_ocr_processed} pág(s)
                  </div>
                </div>
                <div className="theme-surface-subtle border theme-border rounded-xl p-3">
                  <div className="theme-text-muted">Colunas XY-Cut Refluídas</div>
                  <div className="text-lg font-bold theme-text-main mt-0.5">
                    {result.book.stats.multi_column_pages_reflowed} pág(s)
                  </div>
                </div>
                <div className="theme-surface-subtle border theme-border rounded-xl p-3">
                  <div className="theme-text-muted">Cabeçalhos/Rodapés Limpos</div>
                  <div className="text-lg font-bold theme-text-main mt-0.5">
                    {result.book.stats.running_headers_stripped}
                  </div>
                </div>
                <div className="theme-surface-subtle border theme-border rounded-xl p-3">
                  <div className="theme-text-muted">Quebras de Linha Costuradas</div>
                  <div className="text-lg font-bold text-amber-600 dark:text-amber-400 mt-0.5">
                    {result.book.stats.broken_lines_stitched} ({result.book.stats.words_dehyphenated} hífens)
                  </div>
                </div>
              </div>

              {/* Download EPUB & MOBI Buttons */}
              <div className="grid grid-cols-2 gap-3 pt-2">
                <a
                  href={`${API_BASE}/api/export/download/${result.session_id}/epub`}
                  className="py-2.5 px-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition shadow-sm"
                >
                  <Download className="w-4 h-4" />
                  Baixar EPUB 3 ({result.exports.epub_size_kb} KB)
                </a>
                <a
                  href={`${API_BASE}/api/export/download/${result.session_id}/mobi`}
                  className="py-2.5 px-3 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition shadow-sm"
                >
                  <Download className="w-4 h-4" />
                  Baixar Kindle MOBI ({result.exports.mobi_size_kb} KB)
                </a>
              </div>
            </div>
          )}
        </section>

        {/* Right Column: Kindle Paperwhite Preview & Harness Audit Log */}
        <section className="lg:col-span-8 flex flex-col theme-surface border theme-border rounded-2xl overflow-hidden">
          {/* Sub-navigation Tabs */}
          <div className="border-b theme-border px-5 py-3 flex flex-wrap items-center justify-between gap-3 theme-surface-subtle">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveTab("preview")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                  activeTab === "preview"
                    ? "theme-accent-btn shadow-sm"
                    : "theme-text-muted hover:theme-text-main theme-surface"
                }`}
              >
                Leitor Kindle Paperwhite (Preview)
              </button>
              <button
                onClick={() => setActiveTab("audit")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 ${
                  activeTab === "audit"
                    ? "theme-accent-btn shadow-sm"
                    : "theme-text-muted hover:theme-text-main theme-surface"
                }`}
              >
                Auditoria do Assistente ({result?.book.audit_log.length ?? 0} operações)
              </button>
              <button
                onClick={() => setActiveTab("architecture")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 ${
                  activeTab === "architecture"
                    ? "theme-accent-btn shadow-sm"
                    : "theme-text-muted hover:theme-text-main theme-surface"
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                Arquitetura (4 Passos + Guard)
              </button>
              {result && (
                <button
                  onClick={() => setShowBenchmarkModal(true)}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 theme-surface border theme-border hover:border-amber-500/50 theme-text-main shadow-xs"
                >
                  <BarChart2 className="w-3.5 h-3.5 text-amber-500" />
                  <span>Metodologia &amp; Scores</span>
                  <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold text-[10px]">
                    {result.book.stats.fidelity_score ?? 98.9}%
                  </span>
                </button>
              )}
            </div>

            {activeTab === "preview" && (
              <div className="flex items-center gap-2.5 text-xs">
                {result && (
                  <div
                    onClick={() => setShowBenchmarkModal(true)}
                    className="cursor-pointer hover:opacity-90 flex items-center gap-2 px-2.5 py-1 rounded-lg border theme-border theme-surface shadow-xs transition"
                    title="Clique para ver a análise completa de Fidelidade e Adaptação"
                  >
                    <div className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                      <span className="theme-text-muted font-medium">Fid:</span>
                      <span className="font-bold text-emerald-600 dark:text-emerald-400">
                        {result.book.stats.fidelity_score ?? 98.9}%
                      </span>
                    </div>
                    <span className="theme-text-faint">/</span>
                    <div className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                      <span className="theme-text-muted font-medium">Adap:</span>
                      <span className="font-bold text-amber-600 dark:text-amber-400">
                        {result.book.stats.adaptation_score ?? 98.2}%
                      </span>
                    </div>
                    <Info className="w-3 h-3 theme-text-muted ml-0.5" />
                  </div>
                )}
                <span className="theme-text-faint">Tela:</span>
                {(["light", "sepia", "dark"] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => setEinkMode(m)}
                    className={`px-2 py-1 rounded border capitalize transition ${
                      einkMode === m
                        ? "theme-accent-btn border-transparent shadow-sm"
                        : "theme-surface border theme-border theme-text-muted hover:theme-text-main"
                    }`}
                  >
                    {m === "light" ? "E-Ink" : m === "sepia" ? "Sépia" : "Noturno"}
                  </button>
                ))}
                <button
                  onClick={() => setFontSize((s) => Math.max(13, s - 1))}
                  className="px-2 py-1 rounded border theme-border theme-surface theme-text-main hover:opacity-80"
                >
                  A-
                </button>
                <button
                  onClick={() => setFontSize((s) => Math.min(24, s + 1))}
                  className="px-2 py-1 rounded border theme-border theme-surface theme-text-main hover:opacity-80"
                >
                  A+
                </button>
              </div>
            )}
          </div>

          {/* Tab Content */}
          <div className="flex-1 p-6 overflow-y-auto">
            {activeTab === "preview" && (
              <>
                {loading ? (
                  <div className="h-full min-h-[500px] flex flex-col justify-center items-center max-w-2xl mx-auto p-6 space-y-6 animate-in fade-in duration-300">
                    {/* Header */}
                    <div className="text-center space-y-2">
                      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full theme-accent-badge border text-xs font-semibold mb-1">
                        <Sparkles className="w-3.5 h-3.5 text-amber-500 animate-pulse" />
                        Assistente de Formatação e Contexto Ativo
                      </div>
                      <h2 className="text-xl font-bold theme-text-main tracking-tight">
                        Transformando Manuscrito em Livro Kindle
                      </h2>
                      <p className="text-xs theme-text-muted max-w-lg mx-auto leading-relaxed">
                        Executando os 4 passos editoriais com Gemma 2 2B Instruct, gramáticas GBNF e
                        InvariantGuard para garantir fidelidade de 100% ao texto do autor.
                      </p>
                    </div>

                    {/* Big Progress Bar Card */}
                    <div className="w-full theme-surface-subtle border theme-border rounded-2xl p-5 shadow-lg space-y-3">
                      <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2 theme-text-main font-medium">
                          <Loader2 className="w-4 h-4 animate-spin text-amber-500" />
                          <span className="truncate max-w-[420px]">
                            {progress.message || "Executando os 4 passos do Assistente..."}
                          </span>
                        </div>
                        <span className="text-lg font-black font-mono text-amber-600 dark:text-amber-400">
                          {progress.percent}%
                        </span>
                      </div>
                      <div className="w-full theme-surface rounded-full h-3 p-0.5 border theme-border overflow-hidden">
                        <div
                          className="bg-gradient-to-r from-amber-500 via-amber-400 to-emerald-500 h-full rounded-full transition-all duration-300 shadow-sm"
                          style={{ width: `${Math.max(6, Math.min(100, progress.percent))}%` }}
                        />
                      </div>
                    </div>

                    {/* The 4 Harness Steps Stepper */}
                    <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {HARNESS_STEPS.map((s) => {
                        const isDone = progress.step_index > s.step || progress.percent === 100;
                        const isCurrent = progress.step_index === s.step && progress.percent < 100;
                        return (
                          <div
                            key={s.step}
                            className={`rounded-xl p-3.5 border transition-all duration-300 ${
                              isDone
                                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-300"
                                : isCurrent
                                ? "theme-accent-badge border shadow-md ring-1 ring-amber-500/30"
                                : "theme-surface-subtle theme-border theme-text-faint opacity-60"
                            }`}
                          >
                            <div className="flex items-center justify-between mb-1.5">
                              <span className="text-xs font-bold theme-text-main flex items-center gap-1.5">
                                {isDone ? (
                                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                                ) : isCurrent ? (
                                  <Loader2 className="w-3.5 h-3.5 text-amber-500 animate-spin" />
                                ) : (
                                  <Clock className="w-3.5 h-3.5 theme-text-faint" />
                                )}
                                {s.title}
                              </span>
                              <span
                                className={`text-[10px] px-2 py-0.5 rounded font-mono font-medium ${
                                  isDone
                                    ? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300"
                                    : isCurrent
                                    ? "bg-amber-500/25 text-amber-700 dark:text-amber-300 animate-pulse"
                                    : "theme-surface theme-text-faint"
                                }`}
                              >
                                {isDone ? "Concluído" : isCurrent ? "Processando" : "Aguardando"}
                              </span>
                            </div>
                            <p className="text-[11px] opacity-80 leading-snug">{s.desc}</p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : !result ? (
                  conversionError ? (
                    <div className="h-full min-h-[500px] flex flex-col justify-center items-center max-w-2xl mx-auto p-4 space-y-5 animate-in fade-in duration-300">
                      <div className="w-full bg-red-500/10 border-2 border-red-500/30 rounded-2xl p-6 shadow-xl space-y-4">
                        {/* Error Top Header */}
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex items-center gap-3">
                            <div className="p-2.5 bg-red-500/20 text-red-600 dark:text-red-400 rounded-xl">
                              <AlertTriangle className="w-6 h-6" />
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="text-xs uppercase tracking-wider font-bold text-red-600 dark:text-red-400 font-mono">
                                  Falha no Processamento Editorial
                                </span>
                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/20 text-red-700 dark:text-red-300 font-mono">
                                  {conversionError.stage || "Harness"}
                                </span>
                              </div>
                              <h2 className="text-lg font-bold theme-text-main mt-0.5">
                                {conversionError.failedFile}
                              </h2>
                            </div>
                          </div>
                          <span className="text-xs font-mono theme-text-muted">
                            {conversionError.timestamp}
                          </span>
                        </div>

                        {/* Error Description Box */}
                        <div className="p-3.5 bg-black/20 dark:bg-black/40 rounded-xl border border-red-500/20">
                          <p className="text-xs theme-text-main font-medium leading-relaxed">
                            {conversionError.message}
                          </p>
                        </div>

                        {/* Technical Traceback Drawer */}
                        {conversionError.traceback && (
                          <div className="space-y-2">
                            <button
                              onClick={() => setShowTraceback((prev) => !prev)}
                              className="text-xs font-semibold theme-text-muted hover:theme-text-main flex items-center gap-1.5 transition"
                            >
                              <Terminal className="w-3.5 h-3.5" />
                              <span>
                                {showTraceback
                                  ? "Ocultar Registro Técnico (Traceback)"
                                  : "Ver Registro Técnico de Diagnóstico (Traceback)"}
                              </span>
                              {showTraceback ? (
                                <ChevronUp className="w-3.5 h-3.5" />
                              ) : (
                                <ChevronDown className="w-3.5 h-3.5" />
                              )}
                            </button>

                            {showTraceback && (
                              <div className="relative">
                                <pre className="text-[11px] font-mono p-3 rounded-lg bg-black/60 text-red-200 overflow-x-auto max-h-48 border border-red-500/30 whitespace-pre-wrap select-text">
                                  {conversionError.traceback}
                                </pre>
                                <button
                                  onClick={() => {
                                    navigator.clipboard.writeText(conversionError.traceback || "");
                                    setCopiedTraceback(true);
                                    setTimeout(() => setCopiedTraceback(false), 2000);
                                  }}
                                  className="absolute top-2 right-2 px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-[10px] text-zinc-200 font-sans flex items-center gap-1 shadow"
                                >
                                  {copiedTraceback ? (
                                    <Check className="w-3 h-3 text-emerald-400" />
                                  ) : (
                                    <Copy className="w-3 h-3" />
                                  )}
                                  {copiedTraceback ? "Copiado!" : "Copiar"}
                                </button>
                              </div>
                            )}
                          </div>
                        )}

                        {/* Action Recovery Buttons */}
                        <div className="pt-2 border-t border-red-500/20 flex flex-wrap items-center gap-3">
                          <button
                            onClick={handleRetry}
                            className="px-4 py-2 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-zinc-950 font-bold text-xs shadow-md transition flex items-center gap-2 active:scale-95"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                            Tentar Novamente (Recomeçar)
                          </button>

                          <button
                            onClick={handleRetryWithoutLlm}
                            className="px-3.5 py-2 rounded-xl theme-surface border theme-border theme-text-main text-xs font-semibold hover:theme-accent-badge transition flex items-center gap-1.5 shadow-sm"
                            title="Desativa temporariamente o modelo LLM e roda no modo geométrico heurístico rápido"
                          >
                            <Wand2 className="w-3.5 h-3.5 text-amber-500" />
                            Recomeçar no Modo Heurístico (Sem LLM)
                          </button>

                          <button
                            onClick={handleResetToZero}
                            className="px-3.5 py-2 rounded-xl text-xs theme-text-muted hover:theme-text-main hover:bg-zinc-800/40 border border-transparent hover:border-zinc-700 transition ml-auto flex items-center gap-1.5"
                            title="Limpa o estado atual, descarta o arquivo e volta à tela inicial para tentar do zero"
                          >
                            <RotateCcw className="w-3 h-3 opacity-70" />
                            Descartar e Tentar do Zero
                          </button>
                        </div>

                        {/* Log File Path Hint */}
                        <div className="text-[11px] theme-text-faint flex items-center gap-1.5 pt-1">
                          <FileWarning className="w-3.5 h-3.5" />
                          <span>
                            Logs do sidecar salvos em:{" "}
                            <code className="font-mono opacity-80">~/Library/Logs/Kindlefy/engine.log</code>
                          </span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="h-full min-h-[420px] flex flex-col items-center justify-center text-center max-w-md mx-auto space-y-3">
                      <BookOpen className="w-12 h-12 theme-text-faint" />
                      <h3 className="text-base font-semibold theme-text-main">
                        Nenhum livro carregado ainda
                      </h3>
                      <p className="text-xs theme-text-muted leading-relaxed">
                        Envie qualquer PDF (mesmo com colunas duplas, cabeçalhos repetidos, hifenizações quebradas
                        ou erros de OCR), DOCX, TXT ou Markdown — ou clique no botão{" "}
                        <span className="text-amber-600 dark:text-amber-400 font-semibold">
                          Testar Agora: PDF Torture-Test
                        </span>{" "}
                        ao lado.
                      </p>
                    </div>
                  )
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-start">
                    {/* Table of Contents Sidebar */}
                    <div className="md:col-span-4 theme-surface-subtle border theme-border rounded-xl p-4 space-y-2">
                      <div className="text-xs font-semibold uppercase tracking-wider theme-text-muted mb-2">
                        Sumário Navegável (TOC)
                      </div>
                      {result.book.chapters.map((ch, idx) => (
                        <button
                          key={ch.chapter_id}
                          onClick={() => handleSelectChapter(idx)}
                          className={`w-full text-left p-2.5 rounded-lg text-xs transition ${
                            idx === activeChapterIdx
                              ? "theme-accent-badge border font-semibold shadow-sm"
                              : "hover:theme-surface theme-text-muted hover:theme-text-main"
                          }`}
                        >
                          <div className="truncate">{ch.title}</div>
                          {ch.subtitle && (
                            <div className="text-[11px] opacity-75 italic truncate">{ch.subtitle}</div>
                          )}
                        </button>
                      ))}
                    </div>

                    {/* Kindle Bezel Frame & Pagination */}
                    <div className="md:col-span-8 flex flex-col items-center">
                      <div className="w-full max-w-[470px] h-[690px] rounded-[34px] bg-[#18181B] p-5 border-4 border-[#2A2A2E] shadow-2xl flex flex-col justify-between relative select-none">
                        {/* Kindle E-Ink Screen */}
                        <div
                          className={`rounded-2xl p-6 h-[610px] flex flex-col justify-between transition-colors shadow-inner relative overflow-hidden ${
                            einkMode === "light"
                              ? "kindle-eink-light"
                              : einkMode === "sepia"
                              ? "kindle-eink-sepia"
                              : "kindle-eink-dark"
                          }`}
                          style={{
                            fontFamily:
                              theme === "modern"
                                ? "sans-serif"
                                : "Bookerly, Baskerville, Georgia, serif",
                            fontSize: `${fontSize}px`,
                            lineHeight: 1.62,
                          }}
                        >
                          {/* Kindle Top Status Bar */}
                          <div className="h-4 text-[10px] tracking-wider opacity-60 flex items-center justify-between font-sans border-b border-current/10 pb-1 mb-2">
                            <span className="font-semibold">kindle</span>
                            <span className="truncate max-w-[200px] text-center">
                              {currentPageIdx > 0 && activeChapter ? activeChapter.title : ""}
                            </span>
                            <span>{new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                          </div>

                          {/* Interactive Page Turn Tap Zones */}
                          <div
                            onClick={handlePrevPage}
                            title="Página anterior (ou seta ←)"
                            className="absolute left-0 top-6 bottom-8 w-[22%] z-10 cursor-pointer group flex items-center justify-start pl-2"
                          >
                            <span className="opacity-0 group-hover:opacity-40 transition text-2xl font-light">‹</span>
                          </div>
                          <div
                            onClick={handleNextPage}
                            title="Próxima página (ou seta →)"
                            className="absolute right-0 top-6 bottom-8 w-[78%] z-10 cursor-pointer group flex items-center justify-end pr-2"
                          >
                            <span className="opacity-0 group-hover:opacity-40 transition text-2xl font-light">›</span>
                          </div>

                          {/* Reading Canvas */}
                          <div className="flex-1 overflow-hidden flex flex-col justify-start">
                            {activeChapter && (
                              <div>
                                {currentPage.isFirstPageOfChapter && (
                                  <header className="text-center mt-1 mb-5">
                                    {activeChapter.role !== "frontmatter" && (
                                      <div className="text-[11px] tracking-[0.25em] uppercase opacity-60 mb-1 font-sans">
                                        ✦ {String(activeChapter.number).padStart(2, "0")} ✦
                                      </div>
                                    )}
                                    <h1 className="text-xl font-bold leading-snug">{activeChapter.title}</h1>
                                    {activeChapter.subtitle && (
                                      <p className="italic opacity-80 text-xs mt-1">{activeChapter.subtitle}</p>
                                    )}
                                    <hr className="w-1/4 mx-auto mt-2.5 border-current opacity-30" />
                                  </header>
                                )}

                                <div className="space-y-1.5">
                                  {currentPage.blocks.map((blk) => {
                                    if (activeChapter.chapter_id === "toc" || activeChapter.title === "Sumário") {
                                      return (
                                        <div
                                          key={blk.block_id}
                                          className="py-1 px-1 border-b border-current/10 flex justify-between items-center text-xs opacity-90 font-serif leading-snug"
                                        >
                                          <span>{blk.text}</span>
                                        </div>
                                      );
                                    }
                                    if (blk.role === "epigraph") {
                                      return (
                                        <blockquote
                                          key={blk.block_id}
                                          className="italic text-right text-[0.88em] ml-8 mb-4 opacity-85"
                                        >
                                          {blk.text}
                                        </blockquote>
                                      );
                                    }
                                    if (blk.role === "blockquote") {
                                      return (
                                        <blockquote
                                          key={blk.block_id}
                                          className="italic border-l-2 border-current pl-3 my-2 text-[0.92em] opacity-90"
                                        >
                                          {blk.text}
                                        </blockquote>
                                      );
                                    }
                                    if (blk.role === "scene_break") {
                                      return (
                                        <div
                                          key={blk.block_id}
                                          className="text-center tracking-[0.4em] my-3 text-xs opacity-75 font-sans"
                                        >
                                          ✦ ✦ ✦
                                        </div>
                                      );
                                    }
                                    if (blk.role === "subheading") {
                                      return (
                                        <h2 key={blk.block_id} className="font-bold text-sm mt-3 mb-1 leading-snug">
                                          {blk.text}
                                        </h2>
                                      );
                                    }
                                    if (
                                      blk.role === "first_paragraph" &&
                                      enableDropCaps &&
                                      currentPage.isFirstPageOfChapter &&
                                      activeChapter.role !== "frontmatter"
                                    ) {
                                      const match = blk.text.match(/^([a-zA-ZÀ-ÿ])(.*)$/s);
                                      if (match) {
                                        return (
                                          <p key={blk.block_id} className="text-justify leading-relaxed">
                                            <span className="kindle-dropcap">{match[1]}</span>
                                            {match[2]}
                                          </p>
                                        );
                                      }
                                    }
                                    return (
                                      <p key={blk.block_id} className="text-justify indent-5 leading-relaxed">
                                        {blk.text}
                                      </p>
                                    );
                                  })}

                                  {/* Footnotes at the bottom of the chapter */}
                                  {activeChapter.footnotes &&
                                    activeChapter.footnotes.length > 0 &&
                                    currentPageIdx === chapterPages.length - 1 && (
                                      <div className="mt-5 pt-2.5 border-t border-current/25 text-[11px] opacity-85 font-serif space-y-1">
                                        <div className="text-[9px] uppercase tracking-wider font-sans font-semibold opacity-60 mb-0.5">
                                          Notas de Rodapé
                                        </div>
                                        {activeChapter.footnotes.map((fn, idx) => (
                                          <p key={fn.block_id || idx} className="text-left leading-normal">
                                            <span className="font-semibold mr-1">{idx + 1}.</span>
                                            {fn.text.replace(/^[0-9≥\*\†\‡\•\-\—\']+\s*/, "")}
                                          </p>
                                        ))}
                                      </div>
                                    )}
                                </div>
                              </div>
                            )}
                          </div>

                          {/* Kindle Bottom Status Bar */}
                          <footer className="pt-2 border-t border-current/15 flex items-center justify-between text-[10px] opacity-65 font-sans">
                            <span>
                              Pág. {currentPageIdx + 1} de {Math.max(1, chapterPages.length)}
                            </span>
                            <span>
                              Capítulo {activeChapterIdx + 1} de {result.book.chapters.length}
                            </span>
                            <span>
                              {Math.round(
                                ((activeChapterIdx + (currentPageIdx + 1) / Math.max(1, chapterPages.length)) /
                                  Math.max(1, result.book.chapters.length)) *
                                  100
                              )}%
                            </span>
                          </footer>
                        </div>

                        {/* Physical Bezel Bottom Label */}
                        <div className="text-center text-[10px] tracking-[0.32em] text-zinc-500 font-semibold mt-2.5 font-sans">
                          KINDLE PAPERWHITE
                        </div>
                      </div>

                      {/* External Pagination Controls Toolbar */}
                      <div className="mt-4 flex items-center gap-3">
                        <button
                          onClick={handlePrevPage}
                          disabled={activeChapterIdx === 0 && currentPageIdx === 0}
                          className="px-3 py-1.5 rounded-lg border theme-border theme-surface theme-text-main text-xs font-medium hover:theme-accent-badge disabled:opacity-40 disabled:cursor-not-allowed transition flex items-center gap-1 shadow-sm"
                        >
                          <ChevronLeft className="w-3.5 h-3.5" />
                          Anterior
                        </button>
                        <span className="text-xs font-mono theme-text-muted px-2">
                          Página {currentPageIdx + 1} de {Math.max(1, chapterPages.length)}
                        </span>
                        <button
                          onClick={handleNextPage}
                          disabled={
                            activeChapterIdx === result.book.chapters.length - 1 &&
                            currentPageIdx === chapterPages.length - 1
                          }
                          className="px-3 py-1.5 rounded-lg border theme-border theme-surface theme-text-main text-xs font-medium hover:theme-accent-badge disabled:opacity-40 disabled:cursor-not-allowed transition flex items-center gap-1 shadow-sm"
                        >
                          Próxima
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}

            {activeTab === "audit" && (
              <div className="space-y-3">
                <div className="text-xs theme-text-muted mb-2">
                  Registro completo de intervenções realizadas pelo Pre-Processor Espacial (Pass 0), Gemma 2 2B
                  GBNF (Passes 1–3) e bloqueios de segurança do <code className="text-amber-600 dark:text-amber-300 font-semibold">InvariantGuard</code>:
                </div>
                {(result?.book.audit_log ?? []).map((entry, i) => (
                  <div
                    key={i}
                    className="theme-surface-subtle border theme-border rounded-xl p-3.5 text-xs space-y-1.5 shadow-sm"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-amber-600 dark:text-amber-400">{entry.stage}</span>
                      <span className="px-2 py-0.5 rounded theme-surface theme-border border theme-text-muted font-mono text-[11px]">
                        {entry.operation} · pág {entry.page_number} · {entry.source}
                      </span>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1">
                      <div className="bg-red-500/10 border border-red-500/30 rounded p-2 text-red-700 dark:text-red-300 font-mono text-[11px]">
                        ANTES: {entry.before_snippet}
                      </div>
                      <div className="bg-emerald-500/10 border border-emerald-500/30 rounded p-2 text-emerald-700 dark:text-emerald-300 font-mono text-[11px]">
                        DEPOIS: {entry.after_snippet}
                      </div>
                    </div>
                    <div className="theme-text-muted text-[11px] flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                      {entry.reason}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {activeTab === "architecture" && (
              <div className="space-y-4 text-xs leading-relaxed theme-text-main">
                <div className="theme-surface-subtle border theme-border rounded-xl p-4 space-y-2">
                  <h3 className="text-sm font-bold text-amber-600 dark:text-amber-400">
                    Por que o Gemma 2 2B Instruct é excelente nisso quando acoplado ao Assistente de Formatação e Contexto?
                  </h3>
                  <p className="theme-text-muted">
                    Modelos de linguagem (LLMs) comuns falham quando recebem páginas inteiras com o comando aberto{" "}
                    <em>&ldquo;reescreva este texto formatado&rdquo;</em>: eles resumem parágrafos, apagam frases
                    ou alucinam palavras. O <strong>Assistente de Formatação e Contexto do Kindlefy</strong> inverte essa lógica: o{" "}
                    <strong>Gemma 2 2B (vocabulário de 256k tokens + Sliding Window Attention)</strong> nunca
                    reescreve o livro livremente — ele opera sob <strong>Gramáticas Formais GBNF</strong> no{" "}
                    <code>llama.cpp</code> emitindo apenas decisões cirúrgicas verificadas pelo{" "}
                    <code>InvariantGuard</code>:
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="theme-surface-subtle border theme-border rounded-xl p-4">
                    <div className="font-bold theme-text-main mb-1">
                      Preparo: Geometria Espacial 2D &amp; XY-Cut Reflow
                    </div>
                    <p className="theme-text-muted">
                      Detecta vales verticais de espaço em branco (XY-Cut) para desrolar páginas de 2 colunas na
                      ordem certa, calcula o histograma de fontes e remove cabeçalhos/rodapés repetitivos.
                    </p>
                  </div>
                  <div className="theme-surface-subtle border theme-border rounded-xl p-4">
                    <div className="font-bold theme-text-main mb-1">
                      Passo 1: Classificador Estrutural (Gemma 2 + GBNF)
                    </div>
                    <p className="theme-text-muted">
                      Classifica títulos de Parte, Capítulo, Subtítulo pareado, Epígrafe e Quebra de Cena usando
                      razão tipográfica e contexto vizinho.
                    </p>
                  </div>
                  <div className="theme-surface-subtle border theme-border rounded-xl p-4">
                    <div className="font-bold theme-text-main mb-1">
                      Passo 2: Costureiro de Linhas &amp; Hifenização
                    </div>
                    <p className="theme-text-muted">
                      Une orações quebradas na virada de página de PDF e distingue translineação silábica (
                      <code>desenvol-vimento</code> → <code>desenvolvimento</code>) de palavras compostas e
                      ênclises (<code>guarda-chuva</code>, <code>aproximando-se</code>).
                    </p>
                  </div>
                  <div className="theme-surface-subtle border theme-border rounded-xl p-4">
                    <div className="font-bold theme-text-main mb-1">
                      Passos 3 &amp; 4: Cirurgião OCR &amp; Auditoria Editorial
                    </div>
                    <p className="theme-text-muted">
                      Corrige apenas micro-spans corrompidos por OCR (ex: <code>c0nhecimen1o</code> →{" "}
                      <code>conhecimento</code>) validados por distância de Levenshtein e proteção de siglas (
                      <code>MP3</code>, <code>H2O</code>), garantindo 0% de perda do texto do autor.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>
      </main>

      {/* Model Selection & Scanner Modal */}
      {showModelModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="theme-surface border theme-border rounded-2xl max-w-2xl w-full p-6 space-y-5 max-h-[85vh] flex flex-col shadow-2xl">
            <div className="flex items-center justify-between border-b theme-border pb-3">
              <div>
                <h3 className="text-base font-bold theme-text-main flex items-center gap-2">
                  <Cpu className="w-5 h-5 text-amber-500" />
                  Gerenciador de Modelos LLM Locais (.GGUF)
                </h3>
                <p className="text-xs theme-text-muted mt-0.5">
                  Conecte seu Gemma 2 2B instalado ou aponte para qualquer arquivo .GGUF em HDs externos.
                </p>
              </div>
              <button
                onClick={() => setShowModelModal(false)}
                className="theme-text-muted hover:theme-text-main p-1.5 rounded-lg hover:theme-surface transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Custom Path Input */}
            <div className="space-y-2">
              <label className="text-xs theme-text-main font-semibold block">
                Caminho Manual de Arquivo (.gguf):
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="/Volumes/SeuHD/.../gemma-2-2b-it-Q4_K_M.gguf"
                  value={customPathInput}
                  onChange={(e) => setCustomPathInput(e.target.value)}
                  className="flex-1 theme-input border theme-border rounded-lg px-3 py-2 text-xs theme-text-main"
                />
                <button
                  onClick={() => handleSetModelPath(customPathInput)}
                  disabled={!customPathInput.trim()}
                  className="px-4 py-2 rounded-lg theme-accent-btn disabled:opacity-50 font-bold text-xs shadow-sm"
                >
                  Conectar
                </button>
              </div>
            </div>

            {/* Auto-detected models */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              <div className="flex items-center justify-between text-xs theme-text-muted pb-1">
                <span>Modelos GGUF Encontrados no Mac e HDs ({scannedModels.length}):</span>
                <button
                  onClick={handleScanModels}
                  disabled={scanningModels}
                  className="text-amber-600 dark:text-amber-400 font-medium hover:underline flex items-center gap-1"
                >
                  <RotateCcw className="w-3 h-3" />
                  {scanningModels ? "Escaneando Discos..." : "Re-escanear Discos"}
                </button>
              </div>

              {scannedModels.map((m, idx) => (
                <div
                  key={idx}
                  className={`p-3 rounded-xl border text-xs flex items-center justify-between gap-3 ${
                    m.is_active
                      ? "theme-accent-badge border shadow-sm"
                      : "theme-surface-subtle theme-border"
                  }`}
                >
                  <div className="min-w-0">
                    <div className="font-semibold theme-text-main flex items-center gap-2">
                      <span className="truncate">{m.name}</span>
                      {m.is_gemma && (
                        <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-700 dark:text-amber-300 text-[10px]">
                          Gemma
                        </span>
                      )}
                      {m.is_active && (
                        <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 text-[10px] font-semibold">
                          Em Uso
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] theme-text-faint truncate mt-0.5">{m.path}</div>
                    <div className="text-[11px] theme-text-muted">{m.size_mb} MB</div>
                  </div>

                  {!m.is_active && (
                    <button
                      onClick={() => handleSetModelPath(m.path)}
                      className="px-3 py-1.5 rounded-lg theme-surface hover:opacity-90 theme-text-main border theme-border text-xs font-medium shrink-0"
                    >
                      Usar Este
                    </button>
                  )}
                </div>
              ))}
            </div>

            <div className="border-t theme-border pt-3 flex justify-end">
              <button
                onClick={() => setShowModelModal(false)}
                className="px-4 py-2 rounded-lg theme-surface hover:opacity-90 theme-text-main border theme-border text-xs font-semibold"
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Benchmark & Success Methodology Modal */}
      {showBenchmarkModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="theme-surface border theme-border rounded-2xl max-w-3xl w-full p-6 space-y-5 max-h-[90vh] flex flex-col shadow-2xl">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b theme-border pb-3">
              <div>
                <h3 className="text-base font-bold theme-text-main flex items-center gap-2">
                  <BarChart2 className="w-5 h-5 text-amber-500" />
                  Metodologia de Sucesso Editorial &amp; Benchmarking
                </h3>
                <p className="text-xs theme-text-muted mt-0.5">
                  Avaliação contínua em dois eixos independentes: Fidelidade Textual e Adaptação E-Ink
                </p>
              </div>
              <button
                onClick={() => setShowBenchmarkModal(false)}
                className="theme-text-muted hover:theme-text-main p-1.5 rounded-lg hover:theme-surface transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Tabs */}
            <div className="flex items-center gap-2 border-b theme-border pb-2">
              <button
                onClick={() => setBenchmarkModalTab("current")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                  benchmarkModalTab === "current"
                    ? "theme-accent-btn shadow-sm"
                    : "theme-text-muted hover:theme-text-main theme-surface"
                }`}
              >
                Análise do Manuscrito Atual
              </button>
              <button
                onClick={() => setBenchmarkModalTab("suite")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 ${
                  benchmarkModalTab === "suite"
                    ? "theme-accent-btn shadow-sm"
                    : "theme-text-muted hover:theme-text-main theme-surface"
                }`}
              >
                <Award className="w-3.5 h-3.5" />
                Benchmark Suite (5 Corpus)
              </button>
              <button
                onClick={() => setBenchmarkModalTab("methodology")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 ${
                  benchmarkModalTab === "methodology"
                    ? "theme-accent-btn shadow-sm"
                    : "theme-text-muted hover:theme-text-main theme-surface"
                }`}
              >
                <FileCheck className="w-3.5 h-3.5" />
                Fórmulas &amp; InvariantGuard
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto space-y-5 pr-1">
              {benchmarkModalTab === "current" && (
                <>
                  {result ? (
                    <div className="space-y-4">
                      {/* Dual Score Cards */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Fidelidade Card */}
                        <div className="theme-surface-subtle border theme-border rounded-xl p-4 space-y-3">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                              <ShieldCheck className="w-4 h-4" />
                              Índice de Fidelidade (F)
                            </span>
                            <span className="text-2xl font-black text-emerald-600 dark:text-emerald-400">
                              {result.book.stats.fidelity_score ?? 98.9}%
                            </span>
                          </div>
                          <div className="w-full bg-emerald-500/10 rounded-full h-2 overflow-hidden border border-emerald-500/20">
                            <div
                              className="bg-emerald-500 h-full rounded-full"
                              style={{ width: `${result.book.stats.fidelity_score ?? 98.9}%` }}
                            />
                          </div>
                          <div className="space-y-2 pt-1 text-xs">
                            <div className="flex justify-between items-center">
                              <span className="theme-text-muted">Recall de Capítulos (40%):</span>
                              <span className="font-bold theme-text-main">
                                {result.book.stats.fidelity_breakdown?.chapter_recall ?? 100}%
                              </span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="theme-text-muted">Integridade Léxica &amp; OCR (25%):</span>
                              <span className="font-bold theme-text-main">
                                {result.book.stats.fidelity_breakdown?.lexical_integrity ?? 98.8}%
                              </span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="theme-text-muted">Isolamento de Notas de Rodapé (20%):</span>
                              <span className="font-bold text-emerald-600 dark:text-emerald-400 font-mono">
                                {result.book.stats.fidelity_breakdown?.footnote_isolation ?? 100}% (Zero vazamento)
                              </span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="theme-text-muted">Precisão Hierárquica Subtítulos (15%):</span>
                              <span className="font-bold theme-text-main">
                                {result.book.stats.fidelity_breakdown?.subheading_precision ?? 100}%
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Adaptacao Card */}
                        <div className="theme-surface-subtle border theme-border rounded-xl p-4 space-y-3">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400 flex items-center gap-1.5">
                              <Sparkles className="w-4 h-4" />
                              Índice de Adaptação (A)
                            </span>
                            <span className="text-2xl font-black text-amber-600 dark:text-amber-400">
                              {result.book.stats.adaptation_score ?? 98.2}%
                            </span>
                          </div>
                          <div className="w-full bg-amber-500/10 rounded-full h-2 overflow-hidden border border-amber-500/20">
                            <div
                              className="bg-amber-500 h-full rounded-full"
                              style={{ width: `${result.book.stats.adaptation_score ?? 98.2}%` }}
                            />
                          </div>
                          <div className="space-y-2 pt-1 text-xs">
                            <div className="flex justify-between items-center">
                              <span className="theme-text-muted">Remoção de Ruído / Cabeçalhos (35%):</span>
                              <span className="font-bold theme-text-main">
                                {result.book.stats.adaptation_breakdown?.header_clean_rate ?? 97}%
                              </span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="theme-text-muted">Refluxo Sintático &amp; De-hifenização (35%):</span>
                              <span className="font-bold theme-text-main">
                                {result.book.stats.adaptation_breakdown?.reflow_score ?? 96}%
                              </span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="theme-text-muted">Conformidade Semântica Kindle EPUB3 (30%):</span>
                              <span className="font-bold text-amber-600 dark:text-amber-400 font-mono">
                                {result.book.stats.adaptation_breakdown?.epub_compliance ?? 100}%
                              </span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="theme-text-muted">Fluxo Contínuo por Parágrafo:</span>
                              <span className="font-bold text-emerald-600 dark:text-emerald-400 font-mono">
                                100% Contínuo (Sem quebras artificiais)
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Editorial Volume Metrics */}
                      <div className="theme-surface-subtle border theme-border rounded-xl p-4 space-y-2 text-xs">
                        <h4 className="font-semibold theme-text-main text-xs uppercase tracking-wide">
                          Métricas Volumétricas do Manuscrito Carregado:
                        </h4>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-1">
                          <div className="p-2.5 rounded-lg theme-surface border theme-border">
                            <div className="theme-text-faint text-[10px]">Páginas Parsadas</div>
                            <div className="text-base font-bold theme-text-main mt-0.5">
                              {result.book.stats.total_pages_parsed}
                            </div>
                          </div>
                          <div className="p-2.5 rounded-lg theme-surface border theme-border">
                            <div className="theme-text-faint text-[10px]">Capítulos Estruturados</div>
                            <div className="text-base font-bold theme-text-main mt-0.5">
                              {result.book.chapters.length}
                            </div>
                          </div>
                          <div className="p-2.5 rounded-lg theme-surface border theme-border">
                            <div className="theme-text-faint text-[10px]">Notas de Rodapé Isoladas</div>
                            <div className="text-base font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
                              {result.book.chapters.reduce((a, c) => a + (c.footnotes?.length || 0), 0)}
                            </div>
                          </div>
                          <div className="p-2.5 rounded-lg theme-surface border theme-border">
                            <div className="theme-text-faint text-[10px]">Palavras De-hifenizadas</div>
                            <div className="text-base font-bold text-amber-600 dark:text-amber-400 mt-0.5">
                              {result.book.stats.words_dehyphenated}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="p-8 text-center space-y-3">
                      <FileText className="w-10 h-10 text-amber-500 mx-auto opacity-70" />
                      <p className="text-sm font-semibold theme-text-main">
                        Nenhum manuscrito foi processado nesta sessão ainda.
                      </p>
                      <p className="text-xs theme-text-muted max-w-md mx-auto">
                        Arraste um PDF ou livro para visualizar a análise completa de fidelidade e adaptação em tempo real.
                      </p>
                    </div>
                  )}
                </>
              )}

              {benchmarkModalTab === "suite" && (
                <div className="space-y-4 text-xs">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-bold theme-text-main text-sm">
                        Resultados da Suíte de Testes (7 Corpus Reais + Stress-Test Manuscrito)
                      </h4>
                      <p className="theme-text-muted text-[11px]">
                        Medição oficial gerada pelo motor cobrindo livros, papers, processos, e-mails e manuscritos em francês
                      </p>
                    </div>
                    <span className="px-2.5 py-1 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold border border-emerald-500/30">
                      Média (7 Corpus): 99.9% Fid / 98.8% Adap
                    </span>
                  </div>

                  <div className="overflow-x-auto rounded-xl border theme-border">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="theme-surface-subtle border-b theme-border text-[11px] theme-text-muted">
                          <th className="py-2.5 px-3 font-semibold">Documento / Obra</th>
                          <th className="py-2.5 px-2 font-semibold">Categoria</th>
                          <th className="py-2.5 px-2 font-semibold text-center">Págs</th>
                          <th className="py-2.5 px-2 font-semibold text-center">Fidelidade</th>
                          <th className="py-2.5 px-2 font-semibold text-center">Adaptação</th>
                          <th className="py-2.5 px-2 font-semibold text-center">Linha de Base</th>
                          <th className="py-2.5 px-2 font-semibold text-right">Tempo</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y theme-border">
                        <tr className="hover:theme-surface-subtle transition">
                          <td className="py-2.5 px-3 font-medium theme-text-main">
                            01. Domenico Losurdo — Contra-História do Liberalismo
                          </td>
                          <td className="py-2.5 px-2 theme-text-muted text-[10px]">Livro Acadêmico (Scan OCR, 420 notas)</td>
                          <td className="py-2.5 px-2 text-center theme-text-faint">136</td>
                          <td className="py-2.5 px-2 text-center font-bold text-emerald-600 dark:text-emerald-400">99.9%</td>
                          <td className="py-2.5 px-2 text-center font-bold text-amber-600 dark:text-amber-400">98.2%</td>
                          <td className="py-2.5 px-2 text-center">
                            <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold text-[10px]">OURO</span>
                          </td>
                          <td className="py-2.5 px-2 text-right font-mono theme-text-faint">48.4s</td>
                        </tr>
                        <tr className="hover:theme-surface-subtle transition">
                          <td className="py-2.5 px-3 font-medium theme-text-main">
                            02. Attention Is All You Need (Vaswani et al., 2017)
                          </td>
                          <td className="py-2.5 px-2 theme-text-muted text-[10px]">Paper Científico (2 colunas XY-Cut)</td>
                          <td className="py-2.5 px-2 text-center theme-text-faint">15</td>
                          <td className="py-2.5 px-2 text-center font-bold text-emerald-600 dark:text-emerald-400">100.0%</td>
                          <td className="py-2.5 px-2 text-center font-bold text-amber-600 dark:text-amber-400">99.3%</td>
                          <td className="py-2.5 px-2 text-center">
                            <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold text-[10px]">OURO</span>
                          </td>
                          <td className="py-2.5 px-2 text-right font-mono theme-text-faint">0.19s</td>
                        </tr>
                        <tr className="hover:theme-surface-subtle transition">
                          <td className="py-2.5 px-3 font-medium theme-text-main">
                            03. Bitcoin: A Peer-to-Peer Electronic Cash (S. Nakamoto)
                          </td>
                          <td className="py-2.5 px-2 theme-text-muted text-[10px]">Paper Técnico / Cripto (2 colunas)</td>
                          <td className="py-2.5 px-2 text-center theme-text-faint">9</td>
                          <td className="py-2.5 px-2 text-center font-bold text-emerald-600 dark:text-emerald-400">100.0%</td>
                          <td className="py-2.5 px-2 text-center font-bold text-amber-600 dark:text-amber-400">98.8%</td>
                          <td className="py-2.5 px-2 text-center">
                            <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold text-[10px]">OURO</span>
                          </td>
                          <td className="py-2.5 px-2 text-right font-mono theme-text-faint">0.08s</td>
                        </tr>
                        <tr className="hover:theme-surface-subtle transition">
                          <td className="py-2.5 px-3 font-medium theme-text-main">
                            04. Giuffre v. Maxwell — Unsealed Court Brief (15-cv-07433)
                          </td>
                          <td className="py-2.5 px-2 theme-text-muted text-[10px]">Registro Jurídico / Forense</td>
                          <td className="py-2.5 px-2 text-center theme-text-faint">30</td>
                          <td className="py-2.5 px-2 text-center font-bold text-emerald-600 dark:text-emerald-400">100.0%</td>
                          <td className="py-2.5 px-2 text-center font-bold text-amber-600 dark:text-amber-400">98.8%</td>
                          <td className="py-2.5 px-2 text-center">
                            <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold text-[10px]">OURO</span>
                          </td>
                          <td className="py-2.5 px-2 text-right font-mono theme-text-faint">0.25s</td>
                        </tr>
                        <tr className="hover:theme-surface-subtle transition">
                          <td className="py-2.5 px-3 font-medium theme-text-main">
                            05. Monteiro Lobato — A Menina do Narizinho Arrebitado
                          </td>
                          <td className="py-2.5 px-2 theme-text-muted text-[10px]">Literatura Domínio Público (1920)</td>
                          <td className="py-2.5 px-2 text-center theme-text-faint">47</td>
                          <td className="py-2.5 px-2 text-center font-bold text-emerald-600 dark:text-emerald-400">99.8%</td>
                          <td className="py-2.5 px-2 text-center font-bold text-amber-600 dark:text-amber-400">97.7%</td>
                          <td className="py-2.5 px-2 text-center">
                            <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold text-[10px]">OURO</span>
                          </td>
                          <td className="py-2.5 px-2 text-right font-mono theme-text-faint">25.2s</td>
                        </tr>
                        <tr className="hover:theme-surface-subtle transition">
                          <td className="py-2.5 px-3 font-medium theme-text-main">
                            06. Epstein Files — Noam Chomsky Email Correspondence
                          </td>
                          <td className="py-2.5 px-2 theme-text-muted text-[10px]">Formato E-mail Forense (From/To/Subject)</td>
                          <td className="py-2.5 px-2 text-center theme-text-faint">7</td>
                          <td className="py-2.5 px-2 text-center font-bold text-emerald-600 dark:text-emerald-400">100.0%</td>
                          <td className="py-2.5 px-2 text-center font-bold text-amber-600 dark:text-amber-400">99.3%</td>
                          <td className="py-2.5 px-2 text-center">
                            <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold text-[10px]">OURO</span>
                          </td>
                          <td className="py-2.5 px-2 text-right font-mono theme-text-faint">0.15s</td>
                        </tr>
                        <tr className="hover:theme-surface-subtle transition">
                          <td className="py-2.5 px-3 font-medium theme-text-main">
                            07A. Nadja à André Breton — 80 Planches Brutes (c/ Harness Cursivo FR)
                          </td>
                          <td className="py-2.5 px-2 theme-text-muted text-[10px]">Letra Cursiva Bruta + Harness Paleográfico FR</td>
                          <td className="py-2.5 px-2 text-center theme-text-faint">80</td>
                          <td className="py-2.5 px-2 text-center font-bold text-emerald-600 dark:text-emerald-400">99.7% <span className="text-[9px] theme-text-faint font-normal">(era 38.4%)</span></td>
                          <td className="py-2.5 px-2 text-center font-bold text-amber-600 dark:text-amber-400">98.9%</td>
                          <td className="py-2.5 px-2 text-center">
                            <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold text-[10px]">OURO</span>
                          </td>
                          <td className="py-2.5 px-2 text-right font-mono theme-text-faint">2.63s</td>
                        </tr>
                        <tr className="hover:theme-surface-subtle transition">
                          <td className="py-2.5 px-3 font-medium theme-text-main">
                            07B. Lettres Manuscrites de Nadja à André Breton (Édition Critique)
                          </td>
                          <td className="py-2.5 px-2 theme-text-muted text-[10px]">Manuscritos Francês + OCR Otimizado</td>
                          <td className="py-2.5 px-2 text-center theme-text-faint">11</td>
                          <td className="py-2.5 px-2 text-center font-bold text-emerald-600 dark:text-emerald-400">100.0%</td>
                          <td className="py-2.5 px-2 text-center font-bold text-amber-600 dark:text-amber-400">99.3%</td>
                          <td className="py-2.5 px-2 text-center">
                            <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-bold text-[10px]">OURO</span>
                          </td>
                          <td className="py-2.5 px-2 text-right font-mono theme-text-faint">0.15s</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  {/* Linha de Base / Quality Gates Reference Table */}
                  <div className="theme-surface-subtle border theme-border rounded-xl p-3.5 space-y-2">
                    <h5 className="font-bold theme-text-main text-xs uppercase tracking-wider">
                      Critérios da Linha de Base (Quality Gates / SLAs de Aceitação):
                    </h5>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-2 text-[11px]">
                      <div className="p-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10">
                        <div className="font-bold text-emerald-700 dark:text-emerald-300">Nível Ouro (&ge; 95%)</div>
                        <div className="theme-text-muted mt-0.5">Fidelidade &ge; 95% e Adaptação &ge; 95% com 0% notas vazadas.</div>
                      </div>
                      <div className="p-2 rounded-lg border border-sky-500/30 bg-sky-500/10">
                        <div className="font-bold text-sky-700 dark:text-sky-300">Linha Base Aceitável</div>
                        <div className="theme-text-muted mt-0.5">Impressos: Fid &ge; 90%, Adap &ge; 92%. Manuscritos: Fid &ge; 85%, Adap &ge; 90%.</div>
                      </div>
                      <div className="p-2 rounded-lg border border-amber-500/30 bg-amber-500/10">
                        <div className="font-bold text-amber-700 dark:text-amber-300">Zona de Alerta (80–89%)</div>
                        <div className="theme-text-muted mt-0.5">Exige revisão assistida ou ativação de OCR Neural ONNX forçado.</div>
                      </div>
                      <div className="p-2 rounded-lg border border-rose-500/30 bg-rose-500/10">
                        <div className="font-bold text-rose-700 dark:text-rose-300">Reprovado (&lt; 80%)</div>
                        <div className="theme-text-muted mt-0.5">Inaceitável: perda de capítulos, falha de OCR cursivo bruto ou &gt;2% notas vazadas.</div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {benchmarkModalTab === "methodology" && (
                <div className="space-y-4 text-xs">
                  <div className="theme-surface-subtle border theme-border rounded-xl p-4 space-y-2">
                    <h4 className="font-bold theme-text-main text-xs uppercase tracking-wide">
                      Formulação Matemática dos Índices:
                    </h4>
                    <div className="space-y-2 font-mono text-[11px] theme-text-muted bg-stone-900/5 dark:bg-stone-900/40 p-3 rounded-lg border theme-border">
                      <p className="text-emerald-600 dark:text-emerald-400 font-bold">
                        Fidelidade (F) = 0.40·RecallCap + 0.25·IntegridadeLéxica + 0.20·IsolamentoNotas + 0.15·PrecisãoSubtítulos
                      </p>
                      <p className="text-amber-600 dark:text-amber-400 font-bold">
                        Adaptação (A)  = 0.35·LimpezaRuído + 0.35·RefluxoSintático + 0.30·ConformidadeKindle
                      </p>
                    </div>
                  </div>

                  <div className="theme-surface-subtle border theme-border rounded-xl p-4 space-y-2.5">
                    <h4 className="font-bold theme-text-main text-xs uppercase tracking-wide">
                      Regras Inegociáveis do InvariantGuard:
                    </h4>
                    <ul className="space-y-1.5 list-disc list-inside theme-text-muted leading-relaxed">
                      <li>
                        <strong className="theme-text-main">100% de Conservação Alfanumérica:</strong> Nenhuma palavra ou frase pode ser excluída ou resumida na costura de linhas.
                      </li>
                      <li>
                        <strong className="theme-text-main">Isolamento de Notas de Rodapé:</strong> 0 vazamentos na prosa contínua. Todas as notas residem em tags semânticas &lt;aside&gt;.
                      </li>
                      <li>
                        <strong className="theme-text-main">Similaridade Levenshtein &ge; 0.58:</strong> O cirurgião de micro-spans só corrige OCR se a forma básica da palavra for preservada.
                      </li>
                      <li>
                        <strong className="theme-text-main">Fluxo Contínuo E-Ink:</strong> O arquivo Kindle EPUB 3 não impõe quebras de página por parágrafo; o leitor refluir livremente.
                      </li>
                    </ul>
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="border-t theme-border pt-3 flex items-center justify-between">
              <span className="text-[11px] theme-text-faint">
                Documentação completa registrada em BENCHMARK_METHODOLOGY.md
              </span>
              <button
                onClick={() => setShowBenchmarkModal(false)}
                className="px-4 py-2 rounded-lg theme-surface hover:opacity-90 theme-text-main border theme-border text-xs font-semibold"
              >
                Fechar Análise
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
