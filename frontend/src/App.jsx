import { useState, useEffect, useRef } from "react";

import "./App.css";
import { computeSinglePageLayout, computeMultiPageLayout, formatEducationItem, cleanBulletText } from "./utils/resumeLayoutEngine";
import { ResumeSectionErrorBoundary } from "./ErrorBoundary";
import { ResumeCopilotChat } from "./components/ResumeCopilotChat";
import { EditableResumeText } from "./components/EditableResumeText";
import {
  findResumeTargetForNode,
  isRangeInsideContainer,
  resolveActiveResumeSelection,
  applyFontSizeDeltaToRange,
  applyFontFamilyToRange
} from "./utils/selectionFormatting";

// Safe array helper to prevent any unhandled render crashes or blank spaces
const safeArray = (val) => {
  if (!val) return [];
  if (Array.isArray(val)) {
    return val
      .map((item) => (typeof item === "string" ? item.replace(/[\r\n]+/g, " ").trim() : item))
      .filter((item) => item !== null && item !== undefined && item !== "");
  }
  if (typeof val === "string") return val.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
  if (typeof val === "object") {
    try {
      return Object.values(val)
        .flat()
        .map((item) => (typeof item === "string" ? item.replace(/[\r\n]+/g, " ").trim() : item))
        .filter((item) => item !== null && item !== undefined && item !== "");
    } catch {
      return [];
    }
  }
  return [];
};

// Candidate name normalization: collapses duplicate whitespace & enforces executive uppercase serif formatting
const formatCandidateName = (name) => {
  if (!name) return "CANDIDATE NAME";
  try {
    const s = String(name).replace(/\s+/g, " ").trim();
    if (!s) return "CANDIDATE NAME";
    return s.toUpperCase();
  } catch {
    return String(name || "CANDIDATE NAME").toUpperCase();
  }
};

// Phone number formatting (standard clean grouping e.g. +91 92849 75854)
const formatPhoneDisplay = (phone) => {
  if (!phone) return "";
  try {
    const s = String(phone).trim();
    const digits = s.replace(/\D/g, "");
    if (digits.length === 10) {
      return `+91 ${digits.slice(0, 5)} ${digits.slice(5)}`;
    }
    if (digits.length === 12 && digits.startsWith("91")) {
      return `+91 ${digits.slice(2, 7)} ${digits.slice(7)}`;
    }
    if (s.startsWith("+") && digits.length === 11 && digits.startsWith("9")) {
      return `+91 ${digits.slice(1, 6)} ${digits.slice(6)}`;
    }
    return s;
  } catch {
    return String(phone || "");
  }
};

// Normalized contact parser that handles both objects and raw delimited strings
const getNormalizedContact = (rawContact) => {
  if (!rawContact) return { email: "", phone: "", location: "", linkedin: "", github: "" };
  try {
    if (typeof rawContact === "object") {
      return {
        email: String(rawContact.email || "").trim(),
        phone: String(rawContact.phone || "").trim(),
        location: String(rawContact.location || "").trim(),
        linkedin: String(rawContact.linkedin || "").trim(),
        github: String(rawContact.github || "").trim()
      };
    }
    if (typeof rawContact === "string") {
      const parts = rawContact.split(/[|•,\n]/).map((s) => s.trim()).filter(Boolean);
      const out = { email: "", phone: "", location: "", linkedin: "", github: "" };
      for (const part of parts) {
        if (part.includes("@")) {
          out.email = part;
        } else if (/\b(linkedin\.com|linkedin)\b/i.test(part)) {
          out.linkedin = part;
        } else if (/\b(github\.com|github)\b/i.test(part)) {
          out.github = part;
        } else if (/\d{5,}/.test(part)) {
          out.phone = part;
        } else if (/pune|mumbai|delhi|bangalore|hyderabad|chennai|noida|gurgaon|maharashtra|india/i.test(part)) {
          out.location = part;
        } else if (!out.location) {
          out.location = part;
        }
      }
      return out;
    }
  } catch (err) {
    console.warn("getNormalizedContact safe fallback:", err);
  }
  return { email: "", phone: "", location: "", linkedin: "", github: "" };
};
const CLOUD_API_BASE = "https://ai-resume-nset.onrender.com/api";
const rawEnvUrl = (import.meta.env.VITE_API_BASE_URL || "").trim();
const hasRealEnvUrl = rawEnvUrl && !rawEnvUrl.includes("YOUR-RENDER-URL") && rawEnvUrl.startsWith("http");
const isLocalhost = typeof window !== "undefined" && 

  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1");
const API_BASE = hasRealEnvUrl 

  ? rawEnvUrl 

  : (isLocalhost ? `http://${window.location.hostname}:8001/api` : CLOUD_API_BASE);
const QUICK_PROMPTS = [

  "Fit strictly onto 1 page (A4) matching single-page format",

  "Keep authentic internship names, tailor descriptions",

  "Switch project database to MongoDB & Redis",

  "Emphasize Python and FastAPI microservices in bullets",

  "Add AWS Solutions Architect certification",

  "Make experience bullet points more metrics-driven"

];

const SINGLE_PAGE_QUICK_PROMPTS = [
  "Ensure 3 crisp bullet points per internship & project",
  "Make professional summary at least 3 lines",
  "Sync all sections cleanly from multi-page resume above",
  "Switch project database to MongoDB & Redis",
  "Emphasize Python and FastAPI microservices in bullets",
  "Add AWS Solutions Architect certification"
];

function App() {

  // Input states

  const [jdMethod, setJdMethod] = useState("text");
  const [jdText, setJdText] = useState("");
  const [jdLink, setJdLink] = useState("");
  const [resume, setResume] = useState(null);

  // Candidate & project photos state (supports multiple photos, upload & clipboard paste Ctrl+V)
  const [candidatePhoto, setCandidatePhoto] = useState(null);
  const [additionalPhotos, setAdditionalPhotos] = useState([]); // [ { id, dataUrl, name, size } ]

  const [photoPasteNotice, setPhotoPasteNotice] = useState("");

  // Workflow states

  // 'idle' | 'uploading' | 'processing_jd' | 'extracting_resume' | 'ai_analysis' | 'generating' | 'completed' | 'error'

  const [appState, setAppState] = useState("idle");
  const [statusMessage, setStatusMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  // Extracted raw texts

  const [extractedJd, setExtractedJd] = useState("");
  const [extractedResume, setExtractedResume] = useState("");

  // Output data

  const [analysisData, setAnalysisData] = useState(null);
  const [tailoredResume, setTailoredResume] = useState(null);
  const [matchScore, setMatchScore] = useState(0);

  // AI Chatbox Copilot state (Multi-Page Resume + dedicated 1-Page Resume Copilot)
  const [chatMessages, setChatMessages] = useState([
    {
      id: "welcome",
      sender: "ai",
      text: "👋 Hi! I'm your AI Resume Copilot. After generating your resume, type any problem or upload / paste a screenshot (e.g. 'Add this certificate', 'Change projects to match this screenshot', 'Make summary more executive', 'Use this photo as my profile picture') and I will update your resume below in real time!",
      time: "Ready",
      changes: []
    }
  ]);
  const [chatInput, setChatInput] = useState("");
  const [chatAttachedImages, setChatAttachedImages] = useState([]);
  const [isChatDragging, setIsChatDragging] = useState(false);
  const [isChatSubmitting, setIsChatSubmitting] = useState(false);

  const [singlePageChatMessages, setSinglePageChatMessages] = useState([
    {
      id: "sp-welcome",
      sender: "ai",
      text: "👋 Hi! I'm your 1-Page Resume Copilot. Type any change or upload / paste (Ctrl+V) a screenshot (e.g. 'Ensure 3 points per internship', 'Make summary at least 3 lines', 'Add AWS certification', 'Sync all details from above resume') and I will update your 1-Page Resume below in real time!",
      time: "Ready",
      changes: []
    }
  ]);
  const [singlePageChatInput, setSinglePageChatInput] = useState("");
  const [singlePageChatAttachedImages, setSinglePageChatAttachedImages] = useState([]);
  const [isSinglePageChatDragging, setIsSinglePageChatDragging] = useState(false);
  const [isSinglePageChatSubmitting, setIsSinglePageChatSubmitting] = useState(false);

  const [lightboxImage, setLightboxImage] = useState(null);

  const formatFileSize = (bytes) => {
    if (!bytes) return "";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  const attachImagesToState = (files, setImages) => {
    if (!files || files.length === 0) return;
    Array.from(files).forEach((file) => {
      if (!file.type || !file.type.startsWith("image/")) return;
      const reader = new FileReader();
      reader.onload = (event) => {
        setImages((prev) => [
          ...prev,
          {
            id: Date.now() + "_" + Math.random().toString(36).substring(2, 9),
            dataUrl: event.target.result,
            name: file.name || "Screenshot",
            size: formatFileSize(file.size)
          }
        ]);
      };
      reader.readAsDataURL(file);
    });
  };

  const removeImageFromState = (idToRemove, setImages) => {
    setImages((prev) => prev.filter((img) => img.id !== idToRemove));
  };

  const createChatPasteHandler = (setImages) => (e) => {
    if (e.clipboardData && e.clipboardData.items) {
      const imgFiles = [];
      for (let i = 0; i < e.clipboardData.items.length; i++) {
        const item = e.clipboardData.items[i];
        if (item.type && item.type.startsWith("image/")) {
          const file = item.getAsFile();
          if (file) imgFiles.push(file);
        }
      }
      if (imgFiles.length > 0) {
        e.preventDefault();
        e.stopPropagation();
        attachImagesToState(imgFiles, setImages);
      }
    }
  };

  // Direct Project Photo upload & remove handlers

  const handleProjectPhotoUpload = (e, projectIndex) => {
    const file = e.target.files && e.target.files[0];

    if (file && file.type.startsWith("image/")) {
      const reader = new FileReader();

      reader.onload = (event) => {

        setTailoredResume((prev) => {

          if (!prev || !prev.projects) return prev;
          const newProjects = [...prev.projects];

          newProjects[projectIndex] = {

            ...newProjects[projectIndex],

            image: event.target.result

          };
          return { ...prev, projects: newProjects };
        });
      };

      reader.readAsDataURL(file);
    }
  };
  const handleRemoveProjectPhoto = (projectIndex) => {

    setTailoredResume((prev) => {

      if (!prev || !prev.projects) return prev;
      const newProjects = [...prev.projects];
      const updatedProj = { ...newProjects[projectIndex] };

      delete updatedProj.image;

      delete updatedProj.photo;

      newProjects[projectIndex] = updatedProj;
      return { ...prev, projects: newProjects };
    });
  };



  // Global Clipboard Paste (Ctrl+V) handler for Candidate Photo

  useEffect(() => {
    const handlePaste = (e) => {

      if (e.clipboardData && e.clipboardData.items) {

        for (let i = 0; i < e.clipboardData.items.length; i++) {
          const item = e.clipboardData.items[i];

          if (item.type.startsWith("image/")) {
            const blob = item.getAsFile();

            if (blob) {
              const reader = new FileReader();

              reader.onload = (event) => {

                setCandidatePhoto(event.target.result);

                setPhotoPasteNotice("✓ Image pasted from clipboard!");

                setTimeout(() => setPhotoPasteNotice(""), 3500);
              };

              reader.readAsDataURL(blob);
            }

            break;
          }
        }
      }
    };

    window.addEventListener("paste", handlePaste);
    return () => window.removeEventListener("paste", handlePaste);
  }, []);

  // Photo File Upload Handler

  const handlePhotoFileChange = (e) => {
    const file = e.target.files && e.target.files[0];

    if (file && file.type.startsWith("image/")) {
      const reader = new FileReader();

      reader.onload = (event) => {

        setCandidatePhoto(event.target.result);

        setPhotoPasteNotice("✓ Photo uploaded successfully!");

        setTimeout(() => setPhotoPasteNotice(""), 3500);
      };

      reader.readAsDataURL(file);
    }
  };

  // Download & Refresh states

  const [isDownloading, setIsDownloading] = useState(false);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Resume page measurement state & ref

  const resumeRef = useRef(null);
  const [estimatedPages, setEstimatedPages] = useState(1);
  const [pageBreaks, setPageBreaks] = useState([]);

  // Microsoft Word Direct Editing Mode state & handlers

  const [isWordMode, setIsWordMode] = useState(true);
  const [saveIndicator, setSaveIndicator] = useState("");
  const [resumeFont, setResumeFont] = useState("");

  // Single-Page Resume states & refs
  const [singlePageResume, setSinglePageResume] = useState(null);
  const [singlePageResumeHistory, setSinglePageResumeHistory] = useState([]);
  const [singlePageResumeFuture, setSinglePageResumeFuture] = useState([]);
  const [singlePageAdvice, setSinglePageAdvice] = useState("");
  const [singlePageDensity, setSinglePageDensity] = useState("normal");
  const [singlePageWordMode, setSinglePageWordMode] = useState(true);
  const [singlePageSaveIndicator, setSinglePageSaveIndicator] = useState("");
  const [isSinglePageDownloading, setIsSinglePageDownloading] = useState(false);
  const [isSinglePageDownloadingPdf, setIsSinglePageDownloadingPdf] = useState(false);
  const [isSinglePageRefreshing, setIsSinglePageRefreshing] = useState(false);
  const [autoBalanceLayout, setAutoBalanceLayout] = useState(true);
  const [singlePageLayoutMetrics, setSinglePageLayoutMetrics] = useState({
    utilizationPct: 100, fitStatus: "balanced", overflowPx: 0
  });
  const singlePageResumeRef = useRef(null);
  const lastActiveResumeRef = useRef("multi"); // "multi" | "single"
  const savedSelectionsRef = useRef({ multi: null, single: null });

  useEffect(() => {
    const handleSelectionChange = () => {
      const sel = window.getSelection();
      if (!sel || sel.rangeCount === 0) {
        if (!document.activeElement?.closest?.(".word-format-banner")) {
          savedSelectionsRef.current = { multi: null, single: null };
        }
        return;
      }
      const range = sel.getRangeAt(0);
      const target = findResumeTargetForNode(
        range.commonAncestorContainer,
        resumeRef,
        singlePageResumeRef
      );
      if (!target) {
        if (range.collapsed && !document.activeElement?.closest?.(".word-format-banner")) {
          savedSelectionsRef.current = { multi: null, single: null };
        }
        return;
      }
      if (isRangeInsideContainer(range, target.container)) {
        savedSelectionsRef.current[target.mode] = range.cloneRange();
        lastActiveResumeRef.current = target.mode;
      } else if (range.collapsed) {
        savedSelectionsRef.current[target.mode] = null;
      }
    };
    document.addEventListener("selectionchange", handleSelectionChange);
    return () => document.removeEventListener("selectionchange", handleSelectionChange);
  }, []);

  const triggerSinglePageSaveIndicator = (msg = "✓ Auto-Saved to Document") => {
    setSinglePageSaveIndicator(msg);
    setTimeout(() => setSinglePageSaveIndicator(""), 2500);
  };

  const setSinglePageResumeWithHistory = (updater) => {
    setSinglePageResume((prev) => {
      const next = typeof updater === "function" ? updater(prev) : updater;
      if (prev) {
        setSinglePageResumeHistory((h) => [...h.slice(-19), prev]);
        setSinglePageResumeFuture([]);
      }
      return next;
    });
  };

  const undoSinglePageResume = () => {
    if (singlePageResumeHistory.length === 0) return;
    const prev = singlePageResumeHistory[singlePageResumeHistory.length - 1];
    setSinglePageResumeHistory((h) => h.slice(0, -1));
    if (singlePageResume) {
      setSinglePageResumeFuture((f) => [singlePageResume, ...f.slice(0, 19)]);
    }
    setSinglePageResume(prev);
    triggerSinglePageSaveIndicator("↶ Undone");
  };

  const redoSinglePageResume = () => {
    if (singlePageResumeFuture.length === 0) return;
    const next = singlePageResumeFuture[0];
    setSinglePageResumeFuture((f) => f.slice(1));
    if (singlePageResume) {
      setSinglePageResumeHistory((h) => [...h.slice(-19), singlePageResume]);
    }
    setSinglePageResume(next);
    triggerSinglePageSaveIndicator("↷ Redone");
  };

  const updateSinglePageContactField = (field, val) => {
    setSinglePageResumeWithHistory((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        contact: { ...(prev.contact || {}), [field]: val }
      };
    });
    triggerSinglePageSaveIndicator("✓ Saved Contact Info");
  };

  const updateSinglePageSummary = (val) => {
    setSinglePageResumeWithHistory((prev) => {
      if (!prev) return prev;
      return { ...prev, summary: val };
    });
    triggerSinglePageSaveIndicator("✓ Saved Summary");
  };

  const updateSinglePageSkillCategory = (cat, val) => {
    setSinglePageResumeWithHistory((prev) => {
      if (!prev || !prev.skills) return prev;
      let items = typeof val === "string" ? val.split(",").map((s) => s.trim()).filter(Boolean) : val;
      return {
        ...prev,
        skills: {
          ...prev.skills,
          [cat]: items
        }
      };
    });
    triggerSinglePageSaveIndicator("✓ Saved Skills");
  };

  const updateSinglePageExpRole = (index, val) => {
    setSinglePageResumeWithHistory((prev) => {
      if (!prev || !prev.experience) return prev;
      const exp = [...prev.experience];
      if (exp[index]) exp[index] = { ...exp[index], role: val };
      return { ...prev, experience: exp };
    });
    triggerSinglePageSaveIndicator("✓ Saved Experience Role");
  };

  const updateSinglePageExpCompany = (index, val) => {
    setSinglePageResumeWithHistory((prev) => {
      if (!prev || !prev.experience) return prev;
      const exp = [...prev.experience];
      if (exp[index]) exp[index] = { ...exp[index], company: val };
      return { ...prev, experience: exp };
    });
    triggerSinglePageSaveIndicator("✓ Saved Company");
  };

  const updateSinglePageExpDuration = (index, val) => {
    setSinglePageResumeWithHistory((prev) => {
      if (!prev || !prev.experience) return prev;
      const exp = [...prev.experience];
      if (exp[index]) exp[index] = { ...exp[index], duration: val };
      return { ...prev, experience: exp };
    });
    triggerSinglePageSaveIndicator("✓ Saved Duration");
  };

  const updateSinglePageExpBullet = (jobIndex, bulletIndex, val) => {
    setSinglePageResumeWithHistory((prev) => {
      if (!prev || !prev.experience) return prev;
      const exp = [...prev.experience];
      if (exp[jobIndex]) {
        const bullets = [...(exp[jobIndex].bullets || [])];
        bullets[bulletIndex] = val;
        exp[jobIndex] = { ...exp[jobIndex], bullets };
      }
      return { ...prev, experience: exp };
    });
    triggerSinglePageSaveIndicator("✓ Saved Experience Bullet");
  };

  const deleteSinglePageExpBullet = (jobIndex, bulletIndex) => {
    setSinglePageResumeWithHistory((prev) => {
      if (!prev || !prev.experience) return prev;
      const exp = [...prev.experience];
      if (exp[jobIndex]) {
        const bullets = (exp[jobIndex].bullets || []).filter((_, idx) => idx !== bulletIndex);
        exp[jobIndex] = { ...exp[jobIndex], bullets };
      }
      return { ...prev, experience: exp };
    });
    triggerSinglePageSaveIndicator("✓ Bullet Removed");
  };

  const updateSinglePageProjectName = (index, val) => {
    setSinglePageResumeWithHistory((prev) => {
      if (!prev || !prev.projects) return prev;
      const projs = [...prev.projects];
      if (projs[index]) projs[index] = { ...projs[index], name: val };
      return { ...prev, projects: projs };
    });
    triggerSinglePageSaveIndicator("✓ Saved Project Name");
  };

  const updateSinglePageProjectTech = (index, val) => {
    setSinglePageResumeWithHistory((prev) => {
      if (!prev || !prev.projects) return prev;
      const projs = [...prev.projects];
      if (projs[index]) projs[index] = { ...projs[index], technologies: val };
      return { ...prev, projects: projs };
    });
    triggerSinglePageSaveIndicator("✓ Saved Project Tech");
  };

  const updateSinglePageProjectBullet = (projIndex, bulletIndex, val) => {
    setSinglePageResumeWithHistory((prev) => {
      if (!prev || !prev.projects) return prev;
      const projs = [...prev.projects];
      if (projs[projIndex]) {
        const bullets = [...(projs[projIndex].bullets || [])];
        bullets[bulletIndex] = val;
        projs[projIndex] = { ...projs[projIndex], bullets };
      }
      return { ...prev, projects: projs };
    });
    triggerSinglePageSaveIndicator("✓ Saved Project Bullet");
  };

  const deleteSinglePageProjBullet = (projIndex, bulletIndex) => {
    setSinglePageResumeWithHistory((prev) => {
      if (!prev || !prev.projects) return prev;
      const projs = [...prev.projects];
      if (projs[projIndex]) {
        const bullets = (projs[projIndex].bullets || []).filter((_, idx) => idx !== bulletIndex);
        projs[projIndex] = { ...projs[projIndex], bullets };
      }
      return { ...prev, projects: projs };
    });
    triggerSinglePageSaveIndicator("✓ Bullet Removed");
  };

  const updateSinglePageEduInstitution = (index, val) => {
    setSinglePageResumeWithHistory((prev) => {
      if (!prev || !prev.education) return prev;
      const edu = [...prev.education];
      if (edu[index]) {
        if (typeof edu[index] === "object") {
          edu[index] = { ...edu[index], institution: val };
        } else {
          edu[index] = val;
        }
      }
      return { ...prev, education: edu };
    });
    triggerSinglePageSaveIndicator("✓ Saved Education Institution");
  };

  const updateSinglePageEduYear = (index, val) => {
    setSinglePageResumeWithHistory((prev) => {
      if (!prev || !prev.education) return prev;
      const edu = [...prev.education];
      if (edu[index] && typeof edu[index] === "object") {
        edu[index] = { ...edu[index], year: val, duration: val };
      }
      return { ...prev, education: edu };
    });
    triggerSinglePageSaveIndicator("✓ Saved Education Year");
  };

  const updateSinglePageEduDegree = (index, val) => {
    setSinglePageResumeWithHistory((prev) => {
      if (!prev || !prev.education) return prev;
      const edu = [...prev.education];
      if (edu[index] && typeof edu[index] === "object") {
        edu[index] = { ...edu[index], degree: val };
      }
      return { ...prev, education: edu };
    });
    triggerSinglePageSaveIndicator("✓ Saved Degree");
  };

  const updateSinglePageCert = (index, val) => {
    setSinglePageResumeWithHistory((prev) => {
      if (!prev || !prev.certifications) return prev;
      const certs = [...prev.certifications];
      certs[index] = val;
      return { ...prev, certifications: certs };
    });
    triggerSinglePageSaveIndicator("✓ Saved Certification");
  };

  const deleteSinglePageCert = (index) => {
    setSinglePageResumeWithHistory((prev) => {
      if (!prev || !prev.certifications) return prev;
      const certs = prev.certifications.filter((_, idx) => idx !== index);
      return { ...prev, certifications: certs };
    });
    triggerSinglePageSaveIndicator("✓ Certification Removed");
  };

  const handleSinglePageRefresh = async () => {
    if (!singlePageResume && !tailoredResume) return;
    setIsSinglePageRefreshing(true);
    triggerSinglePageSaveIndicator("⟳ Regenerating Single-Page Resume...");
    try {
      const safeJd = (extractedJd || jdText || "Software Engineer target role requirements").trim();
      const safeResume = (extractedResume || JSON.stringify(singlePageResume || tailoredResume || {})).trim();
      const response = await fetch(`${API_BASE}/analyze-single-page`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          jd_text: safeJd,
          resume_text: safeResume,
          resume_filename: resume ? resume.name : "Master_Resume",
          base_tailored_resume: tailoredResume || singlePageResume
        })
      });
      const data = await response.json();
      const refreshed = data.single_page_tailored_content || data.single_page_resume;
      if (response.ok && refreshed) {
        setSinglePageResumeWithHistory(refreshed);
        if (data.single_page_advice || data.advice) {
          setSinglePageAdvice(data.single_page_advice || data.advice);
        }
        triggerSinglePageSaveIndicator("✓ Single-Page Resume Refreshed!");
        setSinglePageChatMessages((prev) => [
          ...prev,
          {
            id: Date.now(),
            sender: "ai",
            text: "🔄 Your 1-Page Resume has been freshly regenerated with strict A4 density and updated bullet points!",
            time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            changes: []
          }
        ]);
      } else {
        throw new Error(data.detail || "Refresh failed");
      }
    } catch (err) {
      console.error("Single page refresh failed:", err);
      triggerSinglePageSaveIndicator("⚠️ Refresh failed, keeping current");
    } finally {
      setIsSinglePageRefreshing(false);
    }
  };

  const handleDownloadSinglePageDocx = async () => {
    if (!singlePageResume) return;
    setIsSinglePageDownloading(true);
    triggerSinglePageSaveIndicator("📥 Preparing Single-Page DOCX...");
    try {
      const response = await fetch(`${API_BASE}/download-single-page-docx`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tailored_content: {
            ...singlePageResume,
            photo: candidatePhoto,
            font_family: resumeFont || ""
          }
        })
      });
      if (!response.ok) throw new Error("Download failed");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const rawName = singlePageResume.name || singlePageResume.contact?.name || "Tailored";
      const candidateName = String(rawName).trim().replace(/[^a-zA-Z0-9_-]+/g, "_");
      a.download = `${candidateName}_Single_Page_Resume.docx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      triggerSinglePageSaveIndicator("✓ Single-Page DOCX Downloaded!");
    } catch (err) {
      console.error("Single-page DOCX download error:", err);
      triggerSinglePageSaveIndicator("⚠️ DOCX download error");
    } finally {
      setIsSinglePageDownloading(false);
    }
  };

  const handleDownloadSinglePagePdf = async () => {
    if (!singlePageResume) return;
    setIsSinglePageDownloadingPdf(true);
    triggerSinglePageSaveIndicator("📄 Generating Single-Page PDF...");
    try {
      const response = await fetch(`${API_BASE}/download-single-page-pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tailored_content: {
            ...singlePageResume,
            photo: candidatePhoto,
            font_family: resumeFont || ""
          }
        })
      });
      if (!response.ok) throw new Error("PDF download failed");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const rawName = singlePageResume.name || singlePageResume.contact?.name || "Tailored";
      const candidateName = String(rawName).trim().replace(/[^a-zA-Z0-9_-]+/g, "_");
      a.download = `${candidateName}_Single_Page_Resume.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      triggerSinglePageSaveIndicator("✓ Single-Page PDF Downloaded!");
    } catch (err) {
      console.error("Single-page PDF download error:", err);
      triggerSinglePageSaveIndicator("⚠️ PDF download error");
    } finally {
      setIsSinglePageDownloadingPdf(false);
    }
  };

  // Auto-balance single-page layout when content changes
  useEffect(() => {
    if (autoBalanceLayout && singlePageResumeRef.current && singlePageResume) {
      try {
        const metrics = computeSinglePageLayout(singlePageResumeRef.current, { targetHeight: 1123 });
        if (metrics) {
          setSinglePageLayoutMetrics(metrics);
        }
      } catch (err) {
        console.warn("Auto-balance layout safe fallback:", err);
      }
    }
  }, [singlePageResume, autoBalanceLayout, singlePageDensity]);
  const triggerSaveIndicator = (msg = "✓ Auto-Saved to Document") => {

    setSaveIndicator(msg);

    setTimeout(() => setSaveIndicator(""), 2500);
  };
  const notifyTargetBanner = (mode, msg) => {
    if (mode === "single") {
      triggerSinglePageSaveIndicator(msg);
    } else {
      triggerSaveIndicator(msg);
    }
  };

  const handleSelectionSizeAdjust = (delta, preferredMode = null) => {
    const resolved = resolveActiveResumeSelection({
      multiRef: resumeRef,
      singleRef: singlePageResumeRef,
      savedSelectionsRef,
      preferredMode: preferredMode || lastActiveResumeRef.current
    });

    if (!resolved) {
      notifyTargetBanner(
        preferredMode || lastActiveResumeRef.current,
        "💡 Select text in the resume first to resize"
      );
      return;
    }

    try {
      const result = applyFontSizeDeltaToRange(
        resolved.range,
        delta,
        resolved.container,
        resolved.selection
      );
      if (!result) {
        notifyTargetBanner(resolved.mode, "💡 Select text in the resume first to resize");
        return;
      }
      if (result.nextRange) {
        savedSelectionsRef.current[resolved.mode] = result.nextRange.cloneRange();
      }
      notifyTargetBanner(resolved.mode, `✓ Selected Text: ${result.metric}px`);
    } catch (err) {
      console.warn("Selection size adjust fallback:", err);
      notifyTargetBanner(resolved.mode, "💡 Could not resize selection");
    }
  };

  const handleSelectionFontChange = (fontFamily, preferredMode = null) => {
    const targetMode = preferredMode || lastActiveResumeRef.current;
    const resolved = resolveActiveResumeSelection({
      multiRef: resumeRef,
      singleRef: singlePageResumeRef,
      savedSelectionsRef,
      preferredMode: targetMode
    });

    if (resolved) {
      try {
        const result = applyFontFamilyToRange(
          resolved.range,
          fontFamily,
          resolved.container,
          resolved.selection
        );
        if (result) {
          if (result.nextRange) {
            savedSelectionsRef.current[resolved.mode] = result.nextRange.cloneRange();
          }
          const fontName = fontFamily
            ? fontFamily.split(",")[0].replace(/['"]/g, "")
            : "Default";
          notifyTargetBanner(resolved.mode, `✓ Selected Font: ${fontName}`);
          return;
        }
      } catch (err) {
        console.warn("Font selection change error:", err);
      }
    }

    if (!fontFamily) {
      setResumeFont("");
      notifyTargetBanner(targetMode, "✓ Document Font: Default");
      return;
    }

    setResumeFont(fontFamily);
    const fontName = fontFamily.split(",")[0].replace(/['"]/g, "");
    notifyTargetBanner(targetMode, `✓ Document Font: ${fontName}`);
  };
  const updateField = (field, value) => {

    setTailoredResume((prev) => {

      if (!prev) return prev;
      return { ...prev, [field]: value };
    });

    triggerSaveIndicator();
  };
  const updateContactField = (field, value) => {

    setTailoredResume((prev) => {

      if (!prev) return prev;
      const contactObj = typeof prev.contact === "object" ? { ...prev.contact } : {};

      contactObj[field] = value;
      return { ...prev, contact: contactObj };
    });

    triggerSaveIndicator();
  };
  const updateSkillCategory = (category, valueString) => {

    setTailoredResume((prev) => {

      if (!prev) return prev;
      const skillsObj = typeof prev.skills === "object" && !Array.isArray(prev.skills) ? { ...prev.skills } : {};
      const tokens = valueString.split(",").map((s) => s.trim()).filter(Boolean);

      skillsObj[category] = tokens;
      return { ...prev, skills: skillsObj };
    });

    triggerSaveIndicator();
  };
  const updateExpField = (expIdx, field, value) => {

    setTailoredResume((prev) => {

      if (!prev || !prev.experience) return prev;
      const newExp = [...prev.experience];

      if (newExp[expIdx]) {

        newExp[expIdx] = { ...newExp[expIdx], [field]: value };
      }
      return { ...prev, experience: newExp };
    });

    triggerSaveIndicator();
  };
  const updateExpBullet = (expIdx, bIdx, value) => {

    setTailoredResume((prev) => {

      if (!prev || !prev.experience) return prev;
      const newExp = [...prev.experience];

      if (newExp[expIdx] && newExp[expIdx].bullets) {
        const newBullets = [...newExp[expIdx].bullets];

        newBullets[bIdx] = value;

        newExp[expIdx] = { ...newExp[expIdx], bullets: newBullets };
      }
      return { ...prev, experience: newExp };
    });

    triggerSaveIndicator();
  };
  const addExpBullet = (expIdx) => {

    setTailoredResume((prev) => {

      if (!prev || !prev.experience) return prev;
      const newExp = [...prev.experience];

      if (newExp[expIdx]) {
        const newBullets = [...(newExp[expIdx].bullets || []), "Engineered and optimized core backend systems, increasing operational throughput by 30%."];

        newExp[expIdx] = { ...newExp[expIdx], bullets: newBullets };
      }
      return { ...prev, experience: newExp };
    });

    triggerSaveIndicator("✓ Bullet Added");
  };
  const deleteExpBullet = (expIdx, bIdx) => {

    setTailoredResume((prev) => {

      if (!prev || !prev.experience) return prev;
      const newExp = [...prev.experience];

      if (newExp[expIdx] && newExp[expIdx].bullets) {
        const newBullets = newExp[expIdx].bullets.filter((_, i) => i !== bIdx);

        newExp[expIdx] = { ...newExp[expIdx], bullets: newBullets };
      }
      return { ...prev, experience: newExp };
    });

    triggerSaveIndicator("✓ Bullet Removed");
  };
  const updateProjField = (projIdx, field, value) => {

    setTailoredResume((prev) => {

      if (!prev || !prev.projects) return prev;
      const newProj = [...prev.projects];

      if (newProj[projIdx]) {

        newProj[projIdx] = { ...newProj[projIdx], [field]: value };
      }
      return { ...prev, projects: newProj };
    });

    triggerSaveIndicator();
  };
  const updateProjBullet = (projIdx, bIdx, value) => {

    setTailoredResume((prev) => {

      if (!prev || !prev.projects) return prev;
      const newProj = [...prev.projects];

      if (newProj[projIdx] && newProj[projIdx].bullets) {
        const newBullets = [...newProj[projIdx].bullets];

        newBullets[bIdx] = value;

        newProj[projIdx] = { ...newProj[projIdx], bullets: newBullets };
      }
      return { ...prev, projects: newProj };
    });

    triggerSaveIndicator();
  };
  const addProjBullet = (projIdx) => {

    setTailoredResume((prev) => {

      if (!prev || !prev.projects) return prev;
      const newProj = [...prev.projects];

      if (newProj[projIdx]) {
        const newBullets = [...(newProj[projIdx].bullets || []), "Implemented scalable microservices and database queries, delivering 30% performance gain."];

        newProj[projIdx] = { ...newProj[projIdx], bullets: newBullets };
      }
      return { ...prev, projects: newProj };
    });

    triggerSaveIndicator("✓ Project Bullet Added");
  };
  const deleteProjBullet = (projIdx, bIdx) => {

    setTailoredResume((prev) => {

      if (!prev || !prev.projects) return prev;
      const newProj = [...prev.projects];

      if (newProj[projIdx] && newProj[projIdx].bullets) {
        const newBullets = newProj[projIdx].bullets.filter((_, i) => i !== bIdx);

        newProj[projIdx] = { ...newProj[projIdx], bullets: newBullets };
      }
      return { ...prev, projects: newProj };
    });

    triggerSaveIndicator("✓ Project Bullet Removed");
  };
  const updateEduField = (eduIdx, field, value) => {

    setTailoredResume((prev) => {

      if (!prev || !prev.education) return prev;
      const newEdu = [...prev.education];

      if (newEdu[eduIdx]) {

        newEdu[eduIdx] = { ...newEdu[eduIdx], [field]: value };
      }
      return { ...prev, education: newEdu };
    });

    triggerSaveIndicator();
  };
  const updateCert = (certIdx, value) => {

    setTailoredResume((prev) => {

      if (!prev || !prev.certifications) return prev;
      const newCerts = [...prev.certifications];

      newCerts[certIdx] = value;
      return { ...prev, certifications: newCerts };
    });

    triggerSaveIndicator();
  };
  const addCert = () => {

    setTailoredResume((prev) => {

      if (!prev) return prev;
      const newCerts = [...(prev.certifications || []), "AWS Certified Solutions Architect - Associate"];
      return { ...prev, certifications: newCerts };
    });

    triggerSaveIndicator("✓ Certification Added");
  };

  useEffect(() => {

    if (tailoredResume) {
      const updatePageLayout = () => {

        if (!resumeRef.current) return;
        const paper = resumeRef.current;

        paper.querySelectorAll(".page-break-target").forEach((el) => {

          el.classList.remove("page-break-target");
        });
        const scrollH = paper.scrollHeight;
        const count = Math.max(1, Math.ceil(scrollH / 1120));

        setEstimatedPages(count);

        if (count <= 1) {

          setPageBreaks([]);
          return;
        }
        const paperRect = paper.getBoundingClientRect();
        const pageThreshold = 1060;
        const PAGE_HEIGHT = 1120;
        const BREAK_GAP = 60;
        const candidates = Array.from(

          paper.querySelectorAll(

            ".resume-paper-block, .resume-exp-item, .exp-bullets > li, .resume-proj-item, .proj-bullets > li, .resume-edu-item, .cert-list > li"

          )
        );
        const breaks = [];
        let accumulatedShift = 0;

        for (let p = 1; p < count; p++) {
          const currentThreshold =

            (p - 1) * PAGE_HEIGHT + pageThreshold + accumulatedShift;
          let targetEl = null;

          for (let i = 0; i < candidates.length; i++) {
            const el = candidates[i];
            const elTop = el.getBoundingClientRect().top - paperRect.top;

            if (elTop >= currentThreshold) {

              targetEl = el;

              break;
            }
          }

          if (targetEl) {

            if (targetEl.tagName.toLowerCase() === "li") {
              const parentBlock = targetEl.closest(

                ".resume-exp-item, .resume-proj-item"

              );

              if (parentBlock) {
                const parentTop =

                  parentBlock.getBoundingClientRect().top - paperRect.top;

                if (currentThreshold - parentTop < 90) {

                  targetEl = parentBlock;
                }
              }
            }

            targetEl.classList.add("page-break-target");

            accumulatedShift += BREAK_GAP;
            const currentPaperRect = paper.getBoundingClientRect();
            const elRelTop =

              targetEl.getBoundingClientRect().top - currentPaperRect.top;
            const guideTop = Math.round(elRelTop - BREAK_GAP / 2);

            breaks.push({

              page: p,

              top: guideTop,

              label: `✂ Page ${p} End / Page ${p + 1} Start`

            });
          } else {

            breaks.push({

              page: p,

              top: Math.round(p * PAGE_HEIGHT + accumulatedShift),

              label: `✂ Page ${p} End / Page ${p + 1} Start`

            });
          }
        }

        setPageBreaks(breaks);
      };
      const timer = setTimeout(updatePageLayout, 150);

      window.addEventListener("resize", updatePageLayout);
      return () => {

        clearTimeout(timer);

        window.removeEventListener("resize", updatePageLayout);
      };
    }
  }, [tailoredResume, candidatePhoto]);

  // Ollama health state

  const [health, setHealth] = useState({

    loading: true,

    ollama: false,

    model: "llama3.2:3b",

    model_found: false,

    error: null

  });
  const checkHealth = async () => {

    try {

      setHealth((prev) => ({ ...prev, loading: true }));
      const res = await fetch(`${API_BASE}/health`);

      if (res.ok) {
        const data = await res.json();

        setHealth({

          loading: false,

          ollama: data.ollama,

          provider: data.provider || "ollama",

          model: data.model || "Cloud AI",

          model_found: data.model_found,

          error: data.error

        });
      } else {

        setHealth({

          loading: false,

          ollama: false,

          provider: "offline",

          model: "AI Offline",

          model_found: false,

          error: "Backend responded with an error."

        });
      }
    } catch {

      setHealth({

        loading: false,

        ollama: false,

        provider: "offline",

        model: "AI Offline",

        model_found: false,

        error: "Cannot connect to backend server. Please verify your backend is running."

      });
    }
  };

  useEffect(() => {

    checkHealth();
  }, []);
  const handleGenerate = async () => {

    setErrorMessage("");

    if (jdMethod === "text" && !jdText.trim()) {

      setErrorMessage("Please paste the Job Description text.");
      return;
    }

    if (jdMethod === "link" && !jdLink.trim()) {

      setErrorMessage("Please enter the Job Description URL.");
      return;
    }

    if (!resume) {

      setErrorMessage("Please upload your Master Resume (.pdf or .docx).");
      return;
    }

    try {

      setAppState("uploading");

      setStatusMessage("Uploading Master Resume...");
      const formData = new FormData();

      formData.append("jd_method", jdMethod);

      if (jdMethod === "text") {

        formData.append("jd_text", jdText);
      } else {

        formData.append("jd_link", jdLink);
      }

      formData.append("resume", resume);

      setAppState("processing_jd");

      setStatusMessage("Parsing Job Description requirements...");
      const uploadRes = await fetch(`${API_BASE}/upload`, {

        method: "POST",

        body: formData

      });
      const uploadData = await uploadRes.json();

      if (!uploadRes.ok) {

        throw new Error(uploadData.detail || "Failed to process JD and Resume");
      }

      setAppState("extracting_resume");

      setStatusMessage("Master Resume text extracted. Initializing AI transformation...");
      const rawJd = uploadData.jd_text;
      const rawResume = uploadData.resume_text;

      setExtractedJd(rawJd);

      setExtractedResume(rawResume);

      setAppState("ai_analysis");

      setStatusMessage(

        "AI analyzing JD: Adapting projects to target tech & database, aligning certifications..."

      );
      const analyzeRes = await fetch(`${API_BASE}/analyze`, {

        method: "POST",

        headers: { "Content-Type": "application/json" },

        body: JSON.stringify({

          jd_text: rawJd,

          resume_text: rawResume,

          resume_filename: uploadData.resume_filename || (resume ? resume.name : "")
        })
      });
      const analyzeData = await analyzeRes.json();

      if (!analyzeRes.ok) {

        throw new Error(analyzeData.detail || "AI analysis failed.");
      }

      setAppState("generating");

      setStatusMessage("Finalizing tailored resume format...");
      const finalTailored = analyzeData.tailored_content;

      if (candidatePhoto) {

        finalTailored.photo = candidatePhoto;
      }

      if (additionalPhotos.length > 0 && finalTailored.projects) {

        additionalPhotos.forEach((ap, idx) => {

          if (idx < finalTailored.projects.length && !finalTailored.projects[idx].image) {

            finalTailored.projects[idx].image = ap.dataUrl;
          }
        });
      }

      setAnalysisData(analyzeData.analysis);

      setTailoredResume(finalTailored);

      if (analyzeData.single_page_tailored_content) {
        let sp = { ...analyzeData.single_page_tailored_content };
        if ((!sp.experience || sp.experience.length === 0) && finalTailored.experience?.length > 0) {
          sp.experience = finalTailored.experience.slice(0, 3);
        }
        if ((!sp.projects || sp.projects.length === 0) && finalTailored.projects?.length > 0) {
          sp.projects = finalTailored.projects.slice(0, 3);
        }
        if ((!sp.skills || Object.keys(sp.skills).length === 0) && finalTailored.skills) {
          sp.skills = finalTailored.skills;
        }
        setSinglePageResume(sp);
        setSinglePageAdvice(analyzeData.single_page_advice || "");
      } else if (finalTailored) {
        setSinglePageResume({ ...finalTailored });
      }

      setMatchScore(analyzeData.match_score || 50);

      setAppState("completed");

      setStatusMessage("Tailored Resume ready!");
      const roleTitle = analyzeData.analysis?.job_title || "Target Role";

      const genTime = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      setChatMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          sender: "ai",
          text: `🎉 Your tailored resume for "${roleTitle}" is ready! All projects are adapted to the target stack & database, industry certifications aligned, and keywords integrated. You can type in the box below to modify any part!`,
          time: genTime
        }
      ]);
      setSinglePageChatMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 2,
          sender: "ai",
          text: `🎉 Your 1-Page Resume for "${roleTitle}" is ready! You can type in the box below or paste screenshots to tailor your 1-page resume independently in real time!`,
          time: genTime
        }
      ]);
    } catch (err) {

      console.error(err);

      setAppState("error");

      setErrorMessage(err.message || "An unexpected error occurred.");
    }
  };

  // Quick Refresh & Re-Tailor Resume function

  const handleRefreshResume = async () => {

    if (isRefreshing) return;

    if (extractedJd && extractedResume) {

      try {

        setIsRefreshing(true);

        triggerSaveIndicator("🔄 Refreshing AI Resume...");
        const analyzeRes = await fetch(`${API_BASE}/analyze`, {

          method: "POST",

          headers: { "Content-Type": "application/json" },

          body: JSON.stringify({

            jd_text: extractedJd,

            resume_text: extractedResume,

            resume_filename: resume ? resume.name : "Master_Resume"

          })
        });
        const analyzeData = await analyzeRes.json();

        if (!analyzeRes.ok) {

          throw new Error(analyzeData.detail || "AI Refresh failed.");
        }
        const finalTailored = analyzeData.tailored_content;

        if (candidatePhoto) {

          finalTailored.photo = candidatePhoto;
        }

        if (additionalPhotos.length > 0 && finalTailored.projects) {

          additionalPhotos.forEach((ap, idx) => {

            if (idx < finalTailored.projects.length && !finalTailored.projects[idx].image) {

              finalTailored.projects[idx].image = ap.dataUrl;
            }
          });
        }

        setAnalysisData(analyzeData.analysis);

        setTailoredResume(finalTailored);

        setMatchScore(analyzeData.match_score || 50);

        triggerSaveIndicator("✓ Resume Refreshed Successfully!");

        setChatMessages((prev) => [

          ...prev,
          {

            id: Date.now(),

            sender: "ai",

            text: "🔄 Your resume has been freshly re-tailored with fresh AI bullet points, updated skill alignments, and metrics!",

            time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
          }
        ]);
      } catch (err) {

        console.error(err);

        triggerSaveIndicator("⚠️ Refresh failed");

        alert("Failed to refresh resume: " + (err.message || "Unknown error"));
      } finally {

        setIsRefreshing(false);
      }
    } else {

      handleGenerate();
    }
  };

  // Shared helper for Copilot Chat submission (Multi-Page and Single-Page)
  const executeCopilotChatRequest = async ({
    queryText,
    inputValue,
    setInputValue,
    attachedImagesList,
    setAttachedImagesList,
    isSubmittingState,
    setIsSubmittingState,
    setMessagesState,
    targetResume,
    endpoint,
    extraPayload = {},
    emptyNotice,
    successText,
    onApplyUpdate
  }) => {
    const query = (queryText || inputValue).trim();
    const imagesToSend = [...attachedImagesList];

    if ((!query && imagesToSend.length === 0) || isSubmittingState) return;
    const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const userMsg = {
      id: Date.now(),
      sender: "user",
      text: query || (imagesToSend.length > 0 ? `📷 Attached ${imagesToSend.length} photo(s) for resume update` : ""),
      images: imagesToSend.map((img) => img.dataUrl),
      imagesMeta: imagesToSend,
      time: timeStr
    };

    setMessagesState((prev) => [...prev, userMsg]);
    setInputValue("");
    setAttachedImagesList([]);

    if (!targetResume) {
      setTimeout(() => {
        setMessagesState((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            sender: "ai",
            text: emptyNotice,
            time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            isNotice: true
          }
        ]);
      }, 300);
      return;
    }

    setIsSubmittingState(true);

    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resume_content: { ...targetResume, photo: candidatePhoto },
          instruction: query,
          image_data: imagesToSend[0]?.dataUrl || null,
          images_data: imagesToSend.map((img) => img.dataUrl),
          original_resume_text: extractedResume,
          jd_text: extractedJd,
          ...extraPayload
        })
      });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Failed to update resume.");
      }

      if (data.updated_content) {
        const updated = data.updated_content;
        if (updated.photo) {
          setCandidatePhoto(updated.photo);
        } else if (candidatePhoto && !query.toLowerCase().includes("remove photo")) {
          updated.photo = candidatePhoto;
        }
        onApplyUpdate(updated);
      }

      const appliedChanges = data.changes || [
        `Updated resume according to: "${query || "attached image(s)"}"`
      ];

      setMessagesState((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: "ai",
          text: successText,
          changes: appliedChanges,
          extractedText: data.image_extracted_text || null,
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
        }
      ]);
    } catch (err) {
      console.error(err);
      setMessagesState((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: "ai",
          text: `Update failed: ${err.message}`,
          isError: true,
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
        }
      ]);
    } finally {
      setIsSubmittingState(false);
    }
  };

  // Multi-Page Copilot Chat Submit
  const handleChatSubmit = (queryText) =>
    executeCopilotChatRequest({
      queryText,
      inputValue: chatInput,
      setInputValue: setChatInput,
      attachedImagesList: chatAttachedImages,
      setAttachedImagesList: setChatAttachedImages,
      isSubmittingState: isChatSubmitting,
      setIsSubmittingState: setIsChatSubmitting,
      setMessagesState: setChatMessages,
      targetResume: tailoredResume,
      endpoint: "/edit-resume",
      emptyNotice:
        "Please generate your initial tailored resume above first. Then whatever problem you type or screenshot you upload/paste here will directly update your resume in real time!",
      successText: "✓ Resume updated successfully based on your problem & photo(s)!",
      onApplyUpdate: (updated) => {
        setTailoredResume(updated);
        setSinglePageResume((prev) => prev || updated);
      }
    });

  // 1-Page Resume Copilot Chat Submit
  const handleSinglePageChatSubmit = (queryText) =>
    executeCopilotChatRequest({
      queryText,
      inputValue: singlePageChatInput,
      setInputValue: setSinglePageChatInput,
      attachedImagesList: singlePageChatAttachedImages,
      setAttachedImagesList: setSinglePageChatAttachedImages,
      isSubmittingState: isSinglePageChatSubmitting,
      setIsSubmittingState: setIsSinglePageChatSubmitting,
      setMessagesState: setSinglePageChatMessages,
      targetResume: singlePageResume || tailoredResume,
      endpoint: "/edit-single-page-resume",
      extraPayload: { base_tailored_resume: tailoredResume },
      emptyNotice:
        "Please generate your 1-page resume first. Then whatever problem you type or screenshot you upload/paste here will directly update your 1-page resume in real time!",
      successText: "✓ 1-Page Resume updated successfully based on your query & photo(s)!",
      onApplyUpdate: (updated) => {
        setSinglePageResumeWithHistory(updated);
      }
    });

  // Toggle 1-Page Fit mode for Tailored Resume (Section 02)
  const handleToggleTailoredSinglePage = async () => {

    if (!tailoredResume) return;
    const isCurrently1Page = Boolean(tailoredResume.single_page || tailoredResume.compact_layout);

    if (isCurrently1Page) {

      setTailoredResume({

        ...tailoredResume,

        single_page: false,

        compact_layout: false

      });

      triggerSaveIndicator("Switched to Multi-Page View");
    } else {

      triggerSaveIndicator("⏳ AI condensing content to fit 1 page...");

      try {
        const res = await fetch(`${API_BASE}/edit-tailored-resume`, {

          method: "POST",

          headers: { "Content-Type": "application/json" },

          body: JSON.stringify({

            resume_content: tailoredResume,

            instruction: "Condense and fit resume strictly onto 1 page A4 (matching single-page resume layout)",

            original_resume_text: extractedResume,

            jd_text: extractedJd

          })
        });
        const data = await res.json();

        if (res.ok && data.updated_resume) {

          setTailoredResume({

            ...data.updated_resume,

            single_page: true,

            compact_layout: true

          });

          triggerSaveIndicator("✓ Fitted to Standard A4 • 1 Page!");

          setChatMessages((prev) => [

            ...prev,
            {

              id: Date.now(),

              sender: "ai",

              text: "📄 Successfully optimized your resume to fit strictly on 1 Standard A4 page! All internship titles and companies are preserved intact with concise high-impact bullets.",

              time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),

              changes: ["Enforced strict 1-page A4 density", "Preserved authentic internship companies & roles"]

            }
          ]);
        } else {

          setTailoredResume({

            ...tailoredResume,

            single_page: true,

            compact_layout: true

          });

          triggerSaveIndicator("✓ 1-Page Fit Mode Enabled");
        }
      } catch {

        setTailoredResume({

          ...tailoredResume,

          single_page: true,

          compact_layout: true

        });

        triggerSaveIndicator("✓ 1-Page Fit Mode Enabled");
      }
    }
  };
  const handleDownload = async () => {

    if (!tailoredResume) return;

    setIsDownloading(true);

    try {
      const payload = {

        ...tailoredResume,

        photo: candidatePhoto,

        font_family: resumeFont || "",

        single_page: Boolean(tailoredResume?.single_page || tailoredResume?.compact_layout),

        compact_layout: Boolean(tailoredResume?.single_page || tailoredResume?.compact_layout)
      };
      const res = await fetch(`${API_BASE}/download-docx`, {

        method: "POST",

        headers: { "Content-Type": "application/json" },

        body: JSON.stringify({

          tailored_content: payload

        })
      });

      if (!res.ok) {
        const errorData = await res.json();

        throw new Error(errorData.detail || "Download failed.");
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");

      a.href = url;
      const safeName = (tailoredResume.name || "Tailored_Resume").replace(

        /[^a-zA-Z0-9_-]/g,

        "_"

      );

      a.download = `${safeName}_Tailored_Resume.docx`;

      document.body.appendChild(a);

      a.click();

      window.URL.revokeObjectURL(url);

      document.body.removeChild(a);
    } catch (err) {

      alert(`Download failed: ${err.message}`);
    } finally {

      setIsDownloading(false);
    }
  };
  const handleDownloadPdf = async () => {

    if (!tailoredResume) return;

    setIsDownloadingPdf(true);

    try {
      const payload = {

        ...tailoredResume,

        photo: candidatePhoto,

        font_family: resumeFont || "",

        single_page: Boolean(tailoredResume?.single_page || tailoredResume?.compact_layout),

        compact_layout: Boolean(tailoredResume?.single_page || tailoredResume?.compact_layout)
      };
      const res = await fetch(`${API_BASE}/download-pdf`, {

        method: "POST",

        headers: { "Content-Type": "application/json" },

        body: JSON.stringify({

          tailored_content: payload

        })
      });

      if (!res.ok) {
        const errorData = await res.json();

        throw new Error(errorData.detail || "PDF download failed.");
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");

      a.href = url;
      const safeName = (tailoredResume.name || "Tailored_Resume").replace(

        /[^a-zA-Z0-9_-]/g,

        "_"

      );

      a.download = `${safeName}_Tailored_Resume.pdf`;

      document.body.appendChild(a);

      a.click();

      window.URL.revokeObjectURL(url);

      document.body.removeChild(a);
    } catch (err) {

      alert(`PDF download failed: ${err.message}`);
    } finally {

      setIsDownloadingPdf(false);
    }
  };
  const isProcessing = [

    "uploading",

    "processing_jd",

    "extracting_resume",

    "ai_analysis",

    "generating"

  ].includes(appState);
  return (
    <div className="app-root">
      {/* Header */}
      <header className="app-header">
        <div className="header-content">
          <div className="logo-section">
            <span className="logo-icon">✨</span>
            <div>
              <h1 className="app-title">AI Resume Tailor</h1>
              <p className="app-subtitle">

                Production-Ready Tech Stack Adaptation, Certification Aligner & ATS Optimizer

              </p>
            </div>
          </div>
          <div className="header-meta">
            <div className="model-badge">
              <span

                className={`status-dot ${

                  health.ollama && health.model_found ? "online" : "offline"

                }`}

              />
              <span className="model-name">
                {health.loading

                  ? "Checking AI status..."

                  : health.ollama

                  ? `${health.provider === "groq" ? "Cloud AI" : "AI"}: ${health.model}`

                  : "AI Backend Offline"}
              </span>
            </div>
            <span className="secure-badge">
              {health.provider === "groq" ? "⚡ Cloud AI Powered" : "🔒 Private & Secure"}
            </span>
          </div>
        </div>
      </header>
      {/* Warning banner if AI backend is offline */}
      {!health.loading && (!health.ollama || !health.model_found) && (
        <div className="warning-banner">
          <div className="warning-content">
            <span className="warning-icon">⚠️</span>
            <div>
              <strong>Backend Service Disconnected</strong>
              <p>
                {health.error || "Cannot connect to backend API."}{" "}

                If running on Vercel, make sure <code>VITE_API_BASE_URL</code> is set to your Render URL.

              </p>
            </div>
          </div>
          <button className="recheck-btn" onClick={checkHealth}>

            Check Again

          </button>
        </div>
      )}
      <main className="container">
        {/* Step 1: Input Panel */}
        <div className="input-grid">
          {/* Job Description Card */}
          <div className="upload-card jd-card">
            <div className="card-header">
              <span className="card-step">1</span>
              <h2>Job Description</h2>
            </div>
            <p className="card-desc">

              Paste the target job description or provide the posting URL.

            </p>
            {/* JD Tabs */}
            <div className="jd-tabs">
              <button

                className={`tab-button ${jdMethod === "text" ? "active" : ""}`}

                onClick={() => {

                  setJdMethod("text");

                  setErrorMessage("");
                }}

                disabled={isProcessing}

              >

                Paste JD

              </button>
              <button

                className={`tab-button ${jdMethod === "link" ? "active" : ""}`}

                onClick={() => {

                  setJdMethod("link");

                  setErrorMessage("");
                }}

                disabled={isProcessing}

              >

                JD Link

              </button>
            </div>
            {/* Paste JD Text */}
            {jdMethod === "text" && (
              <div className="jd-input-section">
                <label htmlFor="jd-textarea">Target Job Description</label>
                <textarea

                  id="jd-textarea"

                  className="jd-textarea"

                  placeholder="Paste the job description (roles, responsibilities, required languages, databases, certifications)..."

                  value={jdText}

                  onChange={(e) => setJdText(e.target.value)}

                  disabled={isProcessing}

                />
                <div className="character-count">{jdText.length} characters</div>
              </div>
            )}
            {/* JD Link Input */}
            {jdMethod === "link" && (
              <div className="jd-input-section">
                <label htmlFor="jd-link-input">Job Posting URL</label>
                <input

                  id="jd-link-input"

                  type="url"

                  className="jd-link-input"

                  placeholder="https://jobs.example.com/posting/12345"

                  value={jdLink}

                  onChange={(e) => setJdLink(e.target.value)}

                  disabled={isProcessing}

                />
                <small>Webpage text will be extracted automatically.</small>
              </div>
            )}
          </div>
          {/* Master Resume & Photo Card */}
          <div className="upload-card resume-card">
            <div className="card-header">
              <span className="card-step">2</span>
              <h2>Master Resume & Photo</h2>
            </div>
            <p className="card-desc">

              Upload your Master Resume document and optional candidate photo.

            </p>
            {/* Resume File Dropzone */}
            <div className="file-dropzone">
              <input

                id="resume-file-input"

                type="file"

                accept=".pdf,.docx"

                onChange={(e) => {

                  if (e.target.files && e.target.files[0]) {

                    setResume(e.target.files[0]);

                    setErrorMessage("");
                  }
                }}

                disabled={isProcessing}

              />
              <div className="file-info-box">
                {resume ? (
                  <div className="file-selected">
                    <span className="file-icon">📄</span>
                    <div className="file-details">
                      <span className="file-name">{resume.name}</span>
                      <span className="file-size">
                        {(resume.size / 1024).toFixed(1)} KB

                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="file-empty">
                    <span className="file-icon">📁</span>
                    <p>Select PDF or DOCX Resume</p>
                  </div>
                )}
              </div>
            </div>
            {/* Candidate & Multiple Photos Uploader */}
            <div className="photo-upload-container">
              <div className="photo-header-row">
                <span className="photo-badge-icon">📷</span>
                <div>
                  <strong>Candidate & Project Photos (Multiple Photos Supported)</strong>
                  <p className="photo-hint-text">

                    Add candidate photo and screenshots for projects • Upload files or press <strong>Ctrl+V</strong> to paste from clipboard

                  </p>
                </div>
              </div>
              {photoPasteNotice && (
                <div className="photo-notice-tag">{photoPasteNotice}</div>
              )}
              {/* Profile Photo */}
              <div className="photo-subheading-label">Candidate Profile Photo</div>
              {candidatePhoto ? (
                <div className="photo-attached-card">
                  <img

                    src={candidatePhoto}

                    alt="Candidate Thumbnail"

                    className="photo-thumb-img"

                  />
                  <div className="photo-meta-info">
                    <span className="photo-status-text">✓ Profile photo set</span>
                    <div className="photo-btn-row">
                      <label className="photo-action-btn replace-btn">
                        <span>Change Photo</span>
                        <input

                          type="file"

                          accept="image/*"

                          onChange={handlePhotoFileChange}

                          style={{ display: "none" }}

                        />
                      </label>
                      <button

                        type="button"

                        className="photo-action-btn remove-btn"

                        onClick={() => setCandidatePhoto(null)}

                      >

                        Remove

                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <label className="photo-dropzone-box">
                  <input

                    type="file"

                    accept="image/*"

                    onChange={handlePhotoFileChange}

                    style={{ display: "none" }}

                  />
                  <div className="photo-empty-content">
                    <span className="photo-box-icon">🖼️</span>
                    <span className="photo-cta-text">

                      Choose profile photo or <strong>press Ctrl+V</strong> to paste

                    </span>
                    <span className="photo-format-hint">PNG, JPG, WebP</span>
                  </div>
                </label>
              )}
              {/* Additional Project Photos */}
              <div className="additional-photos-block">
                <div className="additional-photos-header">
                  <span>🖼️ Project Screenshots / Proofs ({additionalPhotos.length})</span>
                  <label className="photo-add-multi-btn">
                    <span>+ Add Project Photos</span>
                    <input

                      type="file"

                      accept="image/*"

                      multiple

                      onChange={(e) => {

                        if (e.target.files) {

                          Array.from(e.target.files).forEach((f) => {

                            if (f.type && f.type.startsWith("image/")) {
                              const r = new FileReader();

                              r.onload = (ev) => {

                                setAdditionalPhotos((prev) => [

                                  ...prev,
                                  { id: Date.now() + Math.random(), dataUrl: ev.target.result, name: f.name }
                                ]);
                              };

                              r.readAsDataURL(f);
                            }
                          });

                          e.target.value = "";
                        }
                      }}

                      style={{ display: "none" }}

                    />
                  </label>
                </div>
                {additionalPhotos.length > 0 && (
                  <div className="additional-photos-grid">
                    {additionalPhotos.map((ap) => (
                      <div key={ap.id} className="additional-photo-card">
                        <img

                          src={ap.dataUrl}

                          alt={ap.name}

                          className="additional-photo-thumb"

                          onClick={() => setLightboxImage(ap.dataUrl)}

                          title="Click to zoom image"

                        />
                        <button

                          type="button"

                          className="additional-photo-del"

                          onClick={() => setAdditionalPhotos((prev) => prev.filter((p) => p.id !== ap.id))}

                          title="Remove this photo"

                        >

                          ✕

                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <div className="resume-notice">
              <small>

                ✓ Supports PDF & DOCX • Real-life project transformation • Photo integration

              </small>
            </div>
          </div>
        </div>
        {/* Generate Button & Progress State */}
        <div className="action-area">
          <button

            className={`generate-button ${isProcessing ? "processing" : ""}`}

            onClick={handleGenerate}

            disabled={isProcessing}

          >
            {isProcessing ? (
              <span className="btn-spinner-content">
                <span className="spinner" />
                {statusMessage}
              </span>
            ) : appState === "completed" ? (

              "Regenerate Tailored Resume"

            ) : (

              "Generate Tailored Resume"

            )}
          </button>
          {/* Stepper Progress bar when processing */}
          {isProcessing && (
            <div className="progress-stepper">
              <div

                className={`step-item ${

                  [

                    "uploading",

                    "processing_jd",

                    "extracting_resume",

                    "ai_analysis",

                    "generating"

                  ].includes(appState)

                    ? "active"

                    : ""

                }`}

              >

                1. Upload

              </div>
              <div

                className={`step-item ${

                  [

                    "processing_jd",

                    "extracting_resume",

                    "ai_analysis",

                    "generating"

                  ].includes(appState)

                    ? "active"

                    : ""

                }`}

              >

                2. Parse JD

              </div>
              <div

                className={`step-item ${

                  [

                    "extracting_resume",

                    "ai_analysis",

                    "generating"

                  ].includes(appState)

                    ? "active"

                    : ""

                }`}

              >

                3. Extract Resume

              </div>
              <div

                className={`step-item ${

                  ["ai_analysis", "generating"].includes(appState)

                    ? "active"

                    : ""

                }`}

              >

                4. Adapt Projects & Databases

              </div>
              <div

                className={`step-item ${

                  appState === "generating" ? "active" : ""

                }`}

              >

                5. Align Certifications

              </div>
            </div>
          )}
          {/* Error Message */}
          {errorMessage && (
            <div className="error-banner">
              <span className="error-icon">✕</span>
              <span>{errorMessage}</span>
            </div>
          )}
        </div>
        {/* ======================================================== */}
        {/* RESULTS DASHBOARD (Visible when appState === 'completed') */}
        {/* ======================================================== */}
        {appState === "completed" && analysisData && tailoredResume && (
          <div className="results-dashboard">
            {/* Top Toolbar: Quick Download & Summary */}
            <div className="results-header-bar">
              <div>
                <h2 className="dashboard-title">Tailoring Results & Analysis</h2>
                <p className="dashboard-subtitle">

                  Tailored specifically for:{" "}
                  <strong>{analysisData.job_title || "Target Role"}</strong>
                </p>
              </div>
              <div className="header-download-group">
                <button

                  className="download-top-btn"

                  onClick={handleDownload}

                  disabled={isDownloading}

                  title="Download in Microsoft Word (.docx) format"

                >
                  {isDownloading ? "Generating DOCX..." : "📥 Word (.docx)"}
                </button>
                <button

                  className="download-top-btn download-top-pdf-btn"

                  onClick={handleDownloadPdf}

                  disabled={isDownloadingPdf}

                  title="Download in ATS-Friendly PDF format"

                >
                  {isDownloadingPdf ? "Generating PDF..." : "📄 PDF (.pdf)"}
                </button>
              </div>
            </div>
            {/* SECTION 1: JOB ANALYSIS */}
            <section className="dashboard-section job-analysis-section">
              <div className="section-title-wrap">
                <span className="section-num">01</span>
                <h3>Target Job Analysis</h3>
              </div>
              <div className="job-analysis-grid">
                <div className="info-block">
                  <h4>Target Role Title</h4>
                  <p className="job-title-tag">
                    {analysisData.job_title || "Target Position"}
                  </p>
                </div>
                <div className="info-block">
                  <h4>Target Tech Stack & Frameworks</h4>
                  <div className="chip-group">
                    {analysisData.target_tech_stack?.length > 0 ? (

                      analysisData.target_tech_stack.map((tech, idx) => (
                        <span key={idx} className="chip chip-req">

                          ⚡ {tech}
                        </span>
                      ))
                    ) : (
                      <span className="muted-text">None specified</span>
                    )}
                  </div>
                </div>
                <div className="info-block">
                  <h4>Target Database(s)</h4>
                  <div className="chip-group">
                    {analysisData.target_database?.length > 0 ? (

                      analysisData.target_database.map((db, idx) => (
                        <span key={idx} className="chip chip-db">

                          🗄️ {db}
                        </span>
                      ))
                    ) : (
                      <span className="muted-text">PostgreSQL, Redis</span>
                    )}
                  </div>
                </div>
                <div className="info-block">
                  <h4>Recommended Industry Certifications</h4>
                  <div className="chip-group">
                    {analysisData.certifications_recommended?.length > 0 ? (

                      analysisData.certifications_recommended.map((c, idx) => (
                        <span key={idx} className="chip chip-cert">

                          📜 {c}
                        </span>
                      ))
                    ) : (
                      <span className="muted-text">Cloud & Tech Certifications</span>
                    )}
                  </div>
                </div>
                <div className="info-block full-width">
                  <h4>Crucial ATS Keywords Extracted</h4>
                  <div className="chip-group">
                    {(analysisData.important_keywords || analysisData.keywords)?.map(

                      (kw, idx) => (
                        <span key={idx} className="chip chip-kw">

                          #{kw}
                        </span>
                      )
                    )}
                  </div>
                </div>
              </div>
            </section>
            {/* SECTION 2: WHAT CHANGED (AI TAILORING CHANGELOG) */}
            <section className="dashboard-section changelog-section">
              <div className="section-title-wrap changelog-header-wrap">
                <div className="section-title-left">
                  <span className="section-num">02</span>
                  <h3>What Changed in Your Resume (AI Changelog)</h3>
                </div>
                <span className="changelog-status-pill">

                  ✨ Real-Life Production Transformations

                </span>
              </div>
              <p className="section-intro-text">

                Overview of transformations applied to match the target job requirements:

              </p>
              <div className="changelog-grid">
                {/* 1. Transformed Projects Breakdown */}
                <div className="changelog-card projects-changelog-card">
                  <div className="card-top-header">
                    <span className="card-icon">🚀</span>
                    <h4>Transformed Projects (Target Tech & Databases)</h4>
                  </div>
                  <div className="transforms-list">
                    {tailoredResume.projects?.map((proj, pIdx) => (
                      <div key={pIdx} className="project-transform-item">
                        <div className="proj-title-row">
                          <span className="proj-num">#{pIdx + 1}</span>
                          <strong>{proj.name || proj.title}</strong>
                        </div>
                        {/* Stack Migration Pill */}
                        <div className="migration-pill">
                          <span className="pill-from">
                            {proj.original_tech || "Java / Legacy Stack"}
                          </span>
                          <span className="pill-arrow">➔</span>
                          <span className="pill-to">

                            ⚡ {proj.technologies}
                          </span>
                        </div>
                        {/* Database & Notes */}
                        <div className="proj-details-box">
                          {proj.database_used && (
                            <div className="db-line">
                              <strong>Database:</strong>{" "}
                              <span className="db-badge">

                                🗄️ {Array.isArray(proj.database_used) ? proj.database_used.join(", ") : proj.database_used}
                              </span>
                            </div>
                          )}
                          <p className="proj-transform-desc">

                            💡{" "}
                            {proj.transformation_note ||

                              "Adapted architecture, API contracts, and database query optimization to match JD requirements."}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                {/* 2. Certifications & Summary Changes */}
                <div className="changelog-card side-changelog-card">
                  {/* Certifications Aligned */}
                  <div className="side-block">
                    <div className="card-top-header">
                      <span className="card-icon">📜</span>
                      <h4>Certifications Aligned with JD</h4>
                    </div>
                    <ul className="certs-aligned-list">
                      {tailoredResume.certifications?.map((cert, cIdx) => (
                        <li key={cIdx}>
                          <span className="check-icon">✓</span>
                          <span>{cert}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  {/* Summary of AI Adjustments */}
                  <div className="side-block">
                    <div className="card-top-header">
                      <span className="card-icon">📝</span>
                      <h4>Modifications Applied</h4>
                    </div>
                    <ul className="changes-bullets-list">
                      {(

                        analysisData.tailoring_changelog ||

                        tailoredResume.tailoring_metadata?.changes_applied || [

                          "Transformed projects to target language and database",

                          "Added production-level API and database optimization bullets",

                          "Aligned credentials with JD certification requirements",

                          "Infused high-priority ATS keywords throughout"

                        ]

                      ).map((item, chIdx) => (
                        <li key={chIdx}>{item}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            </section>
            {/* SECTION 3: RESUME MATCH SCORE */}
            <section className="dashboard-section resume-match-section">
              <div className="section-title-wrap">
                <span className="section-num">03</span>
                <h3>Resume Match Score</h3>
              </div>
              <div className="match-overview">
                {/* Match Score Gauge */}
                <div className="match-gauge-card">
                  <div className="gauge-circle">
                    <span className="gauge-number">{matchScore}%</span>
                    <span className="gauge-label">Match Score</span>
                  </div>
                  <p className="gauge-caption">

                    Based on verified matching criteria.

                  </p>
                  <small className="ats-disclaimer">

                    Calculated from target competencies matched against the JD requirements.

                  </small>
                </div>
                {/* Matching vs Missing Skills Breakdown */}
                <div className="match-details">
                  <div className="match-column">
                    <div className="column-header matched-header">
                      <span className="badge-icon">✓</span>
                      <h4>

                        Matching Skills ({analysisData.matching_skills?.length || 0})
                      </h4>
                    </div>
                    <p className="column-desc">

                      Skills explicitly aligned with JD criteria:

                    </p>
                    <div className="chip-group">
                      {analysisData.matching_skills?.map((skill, idx) => (
                        <span key={idx} className="chip chip-match">

                          ✓ {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="match-column">
                    <div className="column-header missing-header">
                      <span className="badge-icon">!</span>
                      <h4>

                        Remaining Preferred Skills ({analysisData.missing_skills?.length || 0})
                      </h4>
                    </div>
                    <p className="column-desc">

                      Additional nice-to-have criteria from the job posting:

                    </p>
                    <div className="chip-group">
                      {analysisData.missing_skills?.map((skill, idx) => (
                        <span key={idx} className="chip chip-missing">
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </section>
            {/* SECTION 4: AI CHATBOX COPILOT (MULTI-PAGE RESUME) */}
            <ResumeCopilotChat
              title="AI Resume Copilot Chat"
              subtitle="Type your problem, upload, or paste (Ctrl+V) any screenshot / photo like ChatGPT — the AI extracts the details and updates the resume below in real time!"
              statusLabel="Live Resume Synced"
              messages={chatMessages}
              input={chatInput}
              onInputChange={setChatInput}
              attachedImages={chatAttachedImages}
              onClearImages={() => setChatAttachedImages([])}
              onAttachImages={(files) => attachImagesToState(files, setChatAttachedImages)}
              onRemoveImage={(id) => removeImageFromState(id, setChatAttachedImages)}
              onPaste={createChatPasteHandler(setChatAttachedImages)}
              isDragging={isChatDragging}
              onDragStateChange={setIsChatDragging}
              isSubmitting={isChatSubmitting}
              suggestions={QUICK_PROMPTS}
              onSubmit={handleChatSubmit}
              onZoomImage={setLightboxImage}
              submitLabel="Update Resume"
            />
            {/* SECTION 2: AI TAILORED RESUME PREVIEW — MULTI-PAGE RESUME */}
            <section className="dashboard-section resume-preview-section">
              <div className="section-title-wrap resume-preview-header-wrap">
                <div className="section-title-left">
                  <span className="section-num">02</span>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                    <h3 style={{ margin: 0 }}>AI Tailored Resume Preview — Multi-Page Resume</h3>
                    <span className="mode-badge-pill" style={{ background: "#eff6ff", color: "#1d4ed8", borderColor: "#bfdbfe" }}>
                      📄 MULTI-PAGE
                    </span>
                  </div>
                </div>
                <div className="preview-controls-right">
                  {candidatePhoto && (
                    <span className="photo-active-badge">

                      📷 Candidate Photo Included

                    </span>
                  )}
                  {/* Page count indicator */}
                  <div

                    className={`page-indicator-badge ${

                      (estimatedPages === 1 || tailoredResume?.single_page || tailoredResume?.compact_layout)

                        ? "badge-single"

                        : "badge-multi"

                    }`}

                  >
                    <span className="page-badge-dot"></span>
                    <span className="page-badge-text">
                      {(estimatedPages === 1 || tailoredResume?.single_page || tailoredResume?.compact_layout)

                        ? "Standard A4 • 1 Page"

                        : `Standard A4 • ${estimatedPages} Pages`}
                    </span>
                  </div>
                </div>
              </div>
              {/* MICROSOFT WORD INTERACTIVE EDITING TOOLBAR */}
              <div className="word-format-banner">
                <div className="word-banner-left">
                  <div className="word-badge-group">
                    <span className="word-doc-icon">📄</span>
                    <div>
                      <div className="word-title-main">Microsoft Word Document Format</div>
                      <div className="word-subtitle">
                        {isWordMode

                          ? "Interactive Direct Editing Active — Click any text or bullet below to edit manually!"

                          : "Preview Mode — Enable Manual Edit Mode to type directly into the document"}
                      </div>
                    </div>
                  </div>
                  <button

                    type="button"

                    className={`btn-word-toggle ${isWordMode ? "active" : ""}`}

                    onClick={() => setIsWordMode(!isWordMode)}

                    title="Toggle Word Direct Editing Mode"

                  >
                    {isWordMode ? "✏️ Word Edit Mode: ON" : "👁 Read Only (Click to Edit)"}
                  </button>
                  <button

                    type="button"

                    className={`btn-word-toggle ${(tailoredResume?.single_page || tailoredResume?.compact_layout) ? "active" : ""}`}

                    onClick={handleToggleTailoredSinglePage}

                    title="Fit content strictly to 1 page A4 matching single-page resume layout"

                    style={(tailoredResume?.single_page || tailoredResume?.compact_layout) ? { background: "#166534", color: "#ffffff", borderColor: "#166534" } : {}}

                  >
                    {(tailoredResume?.single_page || tailoredResume?.compact_layout) ? "✓ 1-Page Fit: ON" : "📄 Fit to 1 Page"}
                  </button>
                  {saveIndicator && (
                    <span className="word-save-pill animate-fade">
                      {saveIndicator}
                    </span>
                  )}
                </div>
                <div className="word-banner-right">
                  <button

                    type="button"

                    className={`btn-word-download-fast btn-refresh-resume ${isRefreshing ? "spinning" : ""}`}

                    onClick={handleRefreshResume}

                    disabled={isRefreshing}

                    title="Refresh and re-tailor resume with fresh AI optimization"

                  >
                    <span className="refresh-icon">🔄</span>
                    <span>{isRefreshing ? "Refreshing..." : "Refresh Resume"}</span>
                  </button>
                  <select

                    className="btn-word-download-fast banner-font-btn"

                    value={resumeFont}

                    onChange={(e) => handleSelectionFontChange(e.target.value, "multi")}

                    title="Change Font of Selected Text (or Whole Document)"

                  >
                    <option value="">🔤 Font: Default</option>
                    <option value="Calibri, sans-serif">Calibri</option>
                    <option value="'Times New Roman', serif">Times New Roman</option>
                    <option value="Arial, sans-serif">Arial</option>
                    <option value="Georgia, serif">Georgia</option>
                    <option value="Garamond, serif">Garamond</option>
                    <option value="'Inter', sans-serif">Inter</option>
                    <option value="'Roboto', sans-serif">Roboto</option>
                    <option value="Cambria, serif">Cambria</option>
                    <option value="'Trebuchet MS', sans-serif">Trebuchet MS</option>
                    <option value="Verdana, sans-serif">Verdana</option>
                  </select>
                  <div className="banner-size-btn-group" title="Highlight any text in resume to increase/decrease its size">
                    <button

                      type="button"

                      className="btn-word-download-fast btn-size-adjust"

                      onMouseDown={(e) => e.preventDefault()}

                      onClick={() => handleSelectionSizeAdjust(-1, "multi")}

                      title="Decrease font size of selected text (A−)"

                    >

                      A−

                    </button>
                    <span className="banner-size-indicator" title="Highlight any text in the resume to resize">

                      Size

                    </span>
                    <button

                      type="button"

                      className="btn-word-download-fast btn-size-adjust"

                      onMouseDown={(e) => e.preventDefault()}

                      onClick={() => handleSelectionSizeAdjust(1, "multi")}

                      title="Increase font size of selected text (A+)"

                    >

                      A+

                    </button>
                  </div>
                  <button

                    type="button"

                    className="btn-word-download-fast"

                    onClick={handleDownload}

                    disabled={isDownloading}

                    title="Export clean formatted Microsoft Word (.docx) file"

                  >
                    {isDownloading ? "Generating DOCX..." : "📥 Word (.docx)"}
                  </button>
                  <button

                    type="button"

                    className="btn-word-download-fast btn-pdf-download-fast"

                    onClick={handleDownloadPdf}

                    disabled={isDownloadingPdf}

                    title="Export clean formatted PDF file"

                  >
                    {isDownloadingPdf ? "Generating PDF..." : "📄 PDF (.pdf)"}
                  </button>
                </div>
              </div>
              <div className="resume-viewport">
                <ResumeSectionErrorBoundary>
                <div

                  className={`resume-paper ${

                    tailoredResume?.compact_layout || tailoredResume?.single_page

                      ? "compact-1page"

                      : ""

                  } ${isWordMode ? "word-mode-active" : ""}`}

                  ref={resumeRef}

                  onMouseDown={() => {
                    lastActiveResumeRef.current = "multi";
                  }}

                  style={{

                    ...(resumeFont ? { fontFamily: resumeFont } : {})
                  }}

                >
                  {/* Page boundary indicators */}
                  {pageBreaks.map((pb) => (
                    <div

                      key={pb.page}

                      className="page-boundary-guide"

                      style={{ top: `${pb.top}px` }}

                    >
                      <span className="page-boundary-tag">{pb.label}</span>
                    </div>
                  ))}
                  {/* Header: Clean Classic Layout with Optional Photo */}
                  <div className={`resume-paper-header ${candidatePhoto ? "has-photo" : ""}`}>
                    {candidatePhoto && (
                      <div className="candidate-photo-wrapper">
                        <img

                          src={candidatePhoto}

                          alt={tailoredResume.name || "Candidate Photo"}

                          className="candidate-header-avatar"

                        />
                      </div>
                    )}
                    <div className="candidate-header-info">
                      <EditableResumeText
                        as="h2"
                        className={`candidate-name ${isWordMode ? "word-editable" : ""}`}
                        value={formatCandidateName(tailoredResume.name)}
                        editable={isWordMode}
                        onCommit={(val) => updateField("name", val)}
                        title={isWordMode ? "Click to edit candidate name" : ""}
                      />
                      <div className="candidate-contact">
                        {(() => {
                          const contactObj = getNormalizedContact(tailoredResume.contact);
                          const items = [];
                          if (contactObj.email) {
                            items.push(
                              <span key="email" className="contact-field-item">
                                <span className="contact-icon">✉</span>
                                <EditableResumeText
                                  as="span"
                                  className={`contact-val ${isWordMode ? "word-editable" : ""}`}
                                  value={contactObj.email}
                                  editable={isWordMode}
                                  onCommit={(val) => updateContactField("email", val)}
                                  title={isWordMode ? "Click to edit email" : ""}
                                />
                              </span>
                            );
                          }
                          if (contactObj.phone) {
                            items.push(
                              <span key="phone" className="contact-field-item">
                                <span className="contact-icon">📱</span>
                                <EditableResumeText
                                  as="span"
                                  className={`contact-val ${isWordMode ? "word-editable" : ""}`}
                                  value={formatPhoneDisplay(contactObj.phone)}
                                  editable={isWordMode}
                                  onCommit={(val) => updateContactField("phone", val)}
                                  title={isWordMode ? "Click to edit phone" : ""}
                                />
                              </span>
                            );
                          }
                          if (contactObj.location) {
                            items.push(
                              <span key="location" className="contact-field-item">
                                <span className="contact-icon">📍</span>
                                <EditableResumeText
                                  as="span"
                                  className={`contact-val ${isWordMode ? "word-editable" : ""}`}
                                  value={contactObj.location}
                                  editable={isWordMode}
                                  onCommit={(val) => updateContactField("location", val)}
                                  title={isWordMode ? "Click to edit location" : ""}
                                />
                              </span>
                            );
                          }
                          if (contactObj.linkedin) {
                            items.push(
                              <a
                                key="linkedin"
                                href={contactObj.linkedin.startsWith("http") ? contactObj.linkedin : `https://${contactObj.linkedin.replace(/^https?:\/\//, "")}`}
                                target="_blank"
                                rel="noreferrer"
                                className="contact-link"
                                title="Open LinkedIn Profile"
                              >
                                <span className="contact-icon">🔗</span>
                                <EditableResumeText as="span" className="contact-val" value="LinkedIn" editable={false} />
                              </a>
                            );
                          }
                          if (contactObj.github) {
                            items.push(
                              <a
                                key="github"
                                href={contactObj.github.startsWith("http") ? contactObj.github : `https://${contactObj.github.replace(/^https?:\/\//, "")}`}
                                target="_blank"
                                rel="noreferrer"
                                className="contact-link"
                                title="Open GitHub Profile"
                              >
                                <span className="contact-icon">💻</span>
                                <EditableResumeText as="span" className="contact-val" value="GitHub" editable={false} />
                              </a>
                            );
                          }
                          return items.map((item, idx) => (
                            <span key={idx} style={{ display: "inline-flex", alignItems: "center" }}>
                              {idx > 0 && <EditableResumeText as="span" className="contact-sep" value="|" editable={false} />}
                              {item}
                            </span>
                          ));
                        })()}
                      </div>
                    </div>
                  </div>
                  {/* Professional Summary */}
                  <div className="resume-paper-block">
                    <EditableResumeText as="h4" className="resume-sec-title" value="SUMMARY" editable={false} />
                    <EditableResumeText
                      as="p"
                      className={`resume-summary-text ${isWordMode ? "word-editable" : ""}`}
                      value={tailoredResume.summary}
                      editable={isWordMode}
                      onCommit={(val) => updateField("summary", val)}
                      title={isWordMode ? "Click to edit summary directly" : ""}
                    />
                  </div>
                  {/* Core Skills */}
                  <div className="resume-paper-block">
                    <EditableResumeText as="h4" className="resume-sec-title" value="CORE SKILLS & TECHNOLOGIES" editable={false} />
                    <div className="resume-skills-block">
                      {Array.isArray(tailoredResume.skills) ? (
                        <div className="resume-skill-row">
                          <EditableResumeText as="strong" value="Technical Competencies: " editable={false} />
                          <EditableResumeText
                            as="span"
                            className={isWordMode ? "word-editable" : ""}
                            value={tailoredResume.skills.join(", ")}
                            editable={isWordMode}
                            onCommit={(val) => updateField("skills", val.split(",").map((s) => s.trim()).filter(Boolean))}
                            title={isWordMode ? "Click to edit skills list" : ""}
                          />
                        </div>
                      ) : tailoredResume.skills && typeof tailoredResume.skills === "object" ? (
                        Object.entries(tailoredResume.skills).map(([cat, list]) => {
                          if (
                            cat === "missing_from_resume" ||
                            !list ||
                            list.length === 0
                          )
                            return null;
                          const label =
                            cat === "matching_with_jd"
                              ? "Targeted Expertise"
                              : cat.replace("_", " ").toUpperCase();
                          return (
                            <div key={cat} className="resume-skill-row">
                              <EditableResumeText as="strong" value={`${label}: `} editable={false} />
                              <EditableResumeText
                                as="span"
                                className={isWordMode ? "word-editable" : ""}
                                value={Array.isArray(list) ? list.join(", ") : String(list)}
                                editable={isWordMode}
                                onCommit={(val) => updateSkillCategory(cat, val)}
                                title={isWordMode ? `Click to edit ${label}` : ""}
                              />
                            </div>
                          );
                        })
                      ) : (
                        <EditableResumeText as="p" value={String(tailoredResume.skills || "")} editable={false} />
                      )}
                    </div>
                  </div>
                  {/* Professional Experience */}
                  {safeArray(tailoredResume.experience).length > 0 && (
                    <div className="resume-paper-block">
                      <EditableResumeText as="h4" className="resume-sec-title" value="EXPERIENCE" editable={false} />
                      {safeArray(tailoredResume.experience).map((job, idx) => (
                        <div key={idx} className="resume-exp-item">
                          <div className="exp-line-header">
                            <div className="exp-title-company-wrap">
                              <EditableResumeText
                                as="span"
                                className={`exp-role ${isWordMode ? "word-editable" : ""}`}
                                value={job.role || job.title}
                                editable={isWordMode}
                                onCommit={(val) => updateExpField(idx, "role", val)}
                                title={isWordMode ? "Click to edit job role" : ""}
                              />
                              {job.company && (
                                <>
                                  <EditableResumeText as="span" className="exp-pipe-sep" value="|" editable={false} />
                                  <EditableResumeText
                                    as="span"
                                    className={`exp-company exp-company-highlight ${isWordMode ? "word-editable" : ""}`}
                                    value={job.company}
                                    editable={isWordMode}
                                    onCommit={(val) => updateExpField(idx, "company", val)}
                                    title={isWordMode ? "Click to edit company name" : ""}
                                  />
                                </>
                              )}
                              {job.location && (
                                <EditableResumeText
                                  as="span"
                                  className="exp-location-inline"
                                  value={` • ${job.location}`}
                                  editable={false}
                                />
                              )}
                            </div>
                            <EditableResumeText
                              as="span"
                              className={`exp-duration ${isWordMode ? "word-editable" : ""}`}
                              value={job.duration || job.dates}
                              editable={isWordMode}
                              onCommit={(val) => updateExpField(idx, "duration", val)}
                              title={isWordMode ? "Click to edit duration" : ""}
                            />
                          </div>
                          <ul className="exp-bullets">
                            {safeArray(job.bullets)
                              .filter((b) => b && (typeof b === "string" ? cleanBulletText(b).length > 0 : true))
                              .map((b, bIdx) => (
                              <li key={bIdx} className="word-bullet-item">
                                <EditableResumeText
                                  as="span"
                                  className={`bullet-text ${isWordMode ? "word-editable" : ""}`}
                                  value={cleanBulletText(b)}
                                  editable={isWordMode}
                                  onCommit={(val) => updateExpBullet(idx, bIdx, val)}
                                  title={isWordMode ? "Click to edit bullet" : ""}
                                />
                                {isWordMode && (
                                  <button
                                    type="button"
                                    className="btn-delete-bullet"
                                    onClick={() => deleteExpBullet(idx, bIdx)}
                                    title="Delete this bullet point"
                                  >
                                    ✕
                                  </button>
                                )}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  )}
                  {/* Key Projects */}
                  {safeArray(tailoredResume.projects).length > 0 && (
                    <div className="resume-paper-block">
                      <EditableResumeText as="h4" className="resume-sec-title" value="KEY PROJECTS" editable={false} />
                      {safeArray(tailoredResume.projects).map((proj, idx) => (
                        <div key={idx} className="resume-proj-item">
                          <div className="proj-line-header">
                            <EditableResumeText
                              as="span"
                              className={`proj-name ${isWordMode ? "word-editable" : ""}`}
                              value={proj.name || proj.title}
                              editable={isWordMode}
                              onCommit={(val) => updateProjField(idx, "name", val)}
                              title={isWordMode ? "Click to edit project name" : ""}
                            />
                            {proj.technologies && (
                              <span className="proj-tech">
                                <EditableResumeText as="span" value="(" editable={false} />
                                <EditableResumeText
                                  as="span"
                                  className={isWordMode ? "word-editable" : ""}
                                  value={proj.technologies}
                                  editable={isWordMode}
                                  onCommit={(val) => updateProjField(idx, "technologies", val)}
                                  title={isWordMode ? "Click to edit tech stack" : ""}
                                />
                                <EditableResumeText as="span" value=")" editable={false} />
                              </span>
                            )}
                          </div>
                          {/* Project screenshot / photo thumbnail if present */}
                          {(proj.image || proj.photo) && (
                            <div className="proj-screenshot-wrapper">
                              <div
                                className="proj-screenshot-thumb"
                                onClick={() => setLightboxImage(proj.image || proj.photo)}
                                title="Click to view full-resolution screenshot"
                              >
                                <img
                                  src={proj.image || proj.photo}
                                  alt={proj.name || "Project Screenshot"}
                                  className="proj-screenshot-img"
                                />
                                <span className="proj-zoom-pill">🔍 Zoom Screenshot</span>
                              </div>
                              <button
                                type="button"
                                className="proj-remove-photo-pill"
                                onClick={() => handleRemoveProjectPhoto(idx)}
                                title="Remove photo from this project"
                              >
                                ✕ Remove Photo
                              </button>
                            </div>
                          )}
                          <ul className="proj-bullets">
                            {safeArray(proj.bullets)
                              .filter((b) => b && (typeof b === "string" ? cleanBulletText(b).length > 0 : true))
                              .map((b, bIdx) => (
                              <li key={bIdx} className="word-bullet-item">
                                <EditableResumeText
                                  as="span"
                                  className={`bullet-text ${isWordMode ? "word-editable" : ""}`}
                                  value={cleanBulletText(b)}
                                  editable={isWordMode}
                                  onCommit={(val) => updateProjBullet(idx, bIdx, val)}
                                  title={isWordMode ? "Click to edit project bullet" : ""}
                                />
                                {isWordMode && (
                                  <button
                                    type="button"
                                    className="btn-delete-bullet"
                                    onClick={() => deleteProjBullet(idx, bIdx)}
                                    title="Delete this bullet point"
                                  >
                                    ✕
                                  </button>
                                )}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  )}
                  {/* Education */}
                  {safeArray(tailoredResume.education).length > 0 && (
                    <div className="resume-paper-block">
                      <EditableResumeText as="h4" className="resume-sec-title" value="EDUCATION" editable={false} />
                      {safeArray(tailoredResume.education).map((rawEdu, idx) => {
                        const edu = formatEducationItem(rawEdu);
                        return (
                          <div key={idx} className="resume-edu-item">
                            <div className="edu-line-header">
                              <EditableResumeText
                                as="span"
                                className={`edu-inst ${isWordMode ? "word-editable" : ""}`}
                                value={edu.instLine}
                                editable={isWordMode}
                                onCommit={(val) => updateEduField(idx, "institution", val)}
                                title={isWordMode ? "Click to edit institution" : ""}
                              />
                              {edu.year && (
                                <EditableResumeText
                                  as="span"
                                  className={`edu-duration ${isWordMode ? "word-editable" : ""}`}
                                  value={edu.year}
                                  editable={isWordMode}
                                  onCommit={(val) => updateEduField(idx, "year", val)}
                                  title={isWordMode ? "Click to edit year" : ""}
                                />
                              )}
                            </div>
                            <div className="edu-line-sub">
                              <EditableResumeText
                                as="span"
                                className={`edu-degree ${isWordMode ? "word-editable" : ""}`}
                                value={edu.degreeLine}
                                editable={isWordMode}
                                onCommit={(val) => updateEduField(idx, "degree", val)}
                                title={isWordMode ? "Click to edit degree" : ""}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                  {/* Certifications */}
                  {safeArray(tailoredResume.certifications).length > 0 && (
                    <div className="resume-paper-block">
                      <EditableResumeText as="h4" className="resume-sec-title" value="CERTIFICATIONS" editable={false} />
                      <ul className="cert-list">
                        {safeArray(tailoredResume.certifications).map((cert, idx) => (
                          <li key={idx} className="word-bullet-item">
                            <EditableResumeText
                              as="span"
                              className={`bullet-text ${isWordMode ? "word-editable" : ""}`}
                              value={cert}
                              editable={isWordMode}
                              onCommit={(val) => updateCert(idx, val)}
                              title={isWordMode ? "Click to edit certification" : ""}
                            />
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
                </ResumeSectionErrorBoundary>
              </div>
            </section>
            {/* SECTION 5: DOWNLOAD */}
            <section className="dashboard-section download-section">
              <div className="section-title-wrap">
                <span className="section-num">05</span>
                <h3>Download Clean Document</h3>
              </div>
              <div className="download-box">
                <div className="download-info">
                  <h4>Ready for Job Application</h4>
                  <p>

                    Download your tailored resume in Microsoft Word (.docx) or PDF (.pdf) format. Clean, professionally formatted, and 100% ATS-compliant with photo ready to submit to recruiters!

                  </p>
                </div>
                <div className="download-buttons-wrapper">
                  <button

                    className="download-cta-btn download-docx-cta-btn"

                    onClick={handleDownload}

                    disabled={isDownloading}

                    title="Download Microsoft Word .docx format"

                  >
                    {isDownloading ? (
                      <span className="btn-spinner-content">
                        <span className="spinner" /> Generating DOCX...

                      </span>
                    ) : (
                      <>
                        <span className="btn-icon">📥</span>
                        <span>Download Tailored Resume (.docx)</span>
                      </>
                    )}
                  </button>
                  <button

                    className="download-cta-btn download-pdf-cta-btn"

                    onClick={handleDownloadPdf}

                    disabled={isDownloadingPdf}

                    title="Download ATS-friendly PDF format"

                  >
                    {isDownloadingPdf ? (
                      <span className="btn-spinner-content">
                        <span className="spinner" /> Generating PDF...

                      </span>
                    ) : (
                      <>
                        <span className="btn-icon">📄</span>
                        <span>Download Tailored Resume (.pdf)</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </section>

            {/* AI CHATBOX COPILOT FOR 1-PAGE RESUME */}
            <ResumeCopilotChat
              title="AI Resume Copilot Chat"
              subtitle="Type your problem, upload, or paste (Ctrl+V) any screenshot / photo like ChatGPT — the AI extracts the details and updates the 1-Page Resume below in real time!"
              statusLabel="1-Page Resume Synced"
              messages={singlePageChatMessages}
              input={singlePageChatInput}
              onInputChange={setSinglePageChatInput}
              attachedImages={singlePageChatAttachedImages}
              onClearImages={() => setSinglePageChatAttachedImages([])}
              onAttachImages={(files) => attachImagesToState(files, setSinglePageChatAttachedImages)}
              onRemoveImage={(id) => removeImageFromState(id, setSinglePageChatAttachedImages)}
              onPaste={createChatPasteHandler(setSinglePageChatAttachedImages)}
              isDragging={isSinglePageChatDragging}
              onDragStateChange={setIsSinglePageChatDragging}
              isSubmitting={isSinglePageChatSubmitting}
              suggestions={SINGLE_PAGE_QUICK_PROMPTS}
              onSubmit={handleSinglePageChatSubmit}
              onZoomImage={setLightboxImage}
              placeholder="Type anything to change in your 1-page resume or paste screenshot (Ctrl+V)..."
              submitLabel="Update Resume"
              typingText="Analyzing your problem & screenshot, extracting details, and updating 1-page resume in real time..."
            />

            {/* SECTION 4: AI TAILORED RESUME PREVIEW — SINGLE-PAGE RESUME */}
            <section className="dashboard-section resume-preview-section">
              <div className="section-title-wrap resume-preview-header-wrap">
                <div className="section-title-left">
                  <span className="section-num" style={{ background: "#166534", color: "#ffffff" }}>04</span>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                    <h3 style={{ margin: 0 }}>AI Tailored Resume Preview — Single-Page Resume</h3>
                    <span className="mode-badge-pill" style={{ background: "#dcfce7", color: "#166534", borderColor: "#86efac" }}>
                      ✓ 1-Page Fit Active
                    </span>
                  </div>
                </div>

                <div className="preview-controls-right" style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                  {candidatePhoto && (
                    <span className="photo-active-badge">
                      📷 Candidate Photo Included
                    </span>
                  )}
                  {autoBalanceLayout && singlePageLayoutMetrics.fitStatus === "expanded" && (
                    <span className="layout-engine-badge" title="Content distributed evenly across A4 height to eliminate bottom whitespace">
                      📐 ATS Space Balanced • 100% Page Fill
                    </span>
                  )}
                  {autoBalanceLayout && singlePageLayoutMetrics.fitStatus === "balanced" && (
                    <span className="layout-engine-badge" title="Content naturally fills the page">
                      ✓ Balanced A4 Density ({singlePageLayoutMetrics.utilizationPct}%)
                    </span>
                  )}
                  {autoBalanceLayout && singlePageLayoutMetrics.fitStatus === "compacted" && (
                    <span className="layout-engine-badge" style={{ background: "#f0f9ff", color: "#0369a1", borderColor: "#bae6fd" }} title="Spacing micro-compacted to guarantee single page fit">
                      ⚡ Auto-Compacted • 1 Page Fit
                    </span>
                  )}
                  <div className="page-indicator-badge badge-single">
                    <span className="page-badge-dot"></span>
                    <span className="page-badge-text">Standard A4 • 1 Page</span>
                  </div>
                </div>
              </div>

              {/* MICROSOFT WORD INTERACTIVE EDITING TOOLBAR */}
              <div className="word-format-banner">
                <div className="word-banner-left">
                  <div className="word-badge-group">
                    <span className="word-doc-icon">📄</span>
                    <div>
                      <div className="word-title-main">Microsoft Word Document Format</div>
                      <div className="word-subtitle">
                        {singlePageWordMode
                          ? "Interactive Direct Editing Active — Click any text or bullet below to edit manually!"
                          : "Preview Mode — Enable Manual Edit Mode to type directly into the document"}
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    className={`btn-word-toggle ${singlePageWordMode ? "active" : ""}`}
                    onClick={() => setSinglePageWordMode(!singlePageWordMode)}
                    title="Toggle Word Direct Editing Mode"
                  >
                    {singlePageWordMode ? "✏️ Word Edit Mode: ON" : "👁 Read Only (Click to Edit)"}
                  </button>
                  {singlePageSaveIndicator && (
                    <span className="word-save-pill animate-fade">
                      {singlePageSaveIndicator}
                    </span>
                  )}
                </div>
                <div className="word-banner-right">
                  {/* UNDO / REDO BUTTON GROUP */}
                  <div className="undo-redo-btn-group" title="Undo (Ctrl+Z) / Redo (Ctrl+Y)">
                    <button
                      type="button"
                      className="btn-undo-redo"
                      onClick={undoSinglePageResume}
                      disabled={singlePageResumeHistory.length === 0}
                      title="Undo last change"
                    >
                      ↶ Undo
                    </button>
                    <button
                      type="button"
                      className="btn-undo-redo"
                      onClick={redoSinglePageResume}
                      disabled={singlePageResumeFuture.length === 0}
                      title="Redo next change"
                    >
                      ↷ Redo
                    </button>
                  </div>

                  <button
                    type="button"
                    className="btn-refresh-resume"
                    onClick={handleSinglePageRefresh}
                    disabled={isSinglePageRefreshing}
                    title="Regenerate single-page resume with optimized density"
                  >
                    {isSinglePageRefreshing ? (
                      <span className="refresh-spinner animate-spin">⟳</span>
                    ) : (
                      <span>🔄</span>
                    )}
                    <span>{isSinglePageRefreshing ? "Refreshing..." : "Refresh Resume"}</span>
                  </button>

                  {/* FONT SELECTOR */}
                  <select
                    className="resume-font-select"
                    value={resumeFont}
                    onChange={(e) => handleSelectionFontChange(e.target.value, "single")}
                    title="Change resume typography font family"
                  >
                    <option value="">🔤 Font: Default</option>
                    <option value="'Calibri', 'Carlito', sans-serif">Calibri</option>
                    <option value="'Times New Roman', 'Liberation Serif', serif">Times New Roman</option>
                    <option value="'Arial', sans-serif">Arial</option>
                    <option value="Georgia, serif">Georgia</option>
                    <option value="Garamond, serif">Garamond</option>
                    <option value="'Inter', sans-serif">Inter</option>
                    <option value="'Roboto', sans-serif">Roboto</option>
                    <option value="Cambria, serif">Cambria</option>
                    <option value="'Trebuchet MS', sans-serif">Trebuchet MS</option>
                    <option value="Verdana, sans-serif">Verdana</option>
                  </select>

                  <div className="banner-size-btn-group" title="Highlight any text in resume to increase/decrease its size">
                    <button
                      type="button"
                      className="btn-word-download-fast btn-size-adjust"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => handleSelectionSizeAdjust(-1, "single")}
                      title="Decrease font size of selected text (A−)"
                    >
                      A−
                    </button>
                    <span className="banner-size-indicator" title="Highlight any text in the resume to resize">
                      Size
                    </span>
                    <button
                      type="button"
                      className="btn-word-download-fast btn-size-adjust"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => handleSelectionSizeAdjust(1, "single")}
                      title="Increase font size of selected text (A+)"
                    >
                      A+
                    </button>
                  </div>

                  <button
                    type="button"
                    className="btn-word-download-fast"
                    onClick={handleDownloadSinglePageDocx}
                    disabled={isSinglePageDownloading}
                    title="Export clean formatted Microsoft Word (.docx) file"
                  >
                    {isSinglePageDownloading ? "Generating DOCX..." : "📥 Word (.docx)"}
                  </button>

                  <button
                    type="button"
                    className="btn-word-download-fast btn-pdf-download-fast"
                    onClick={handleDownloadSinglePagePdf}
                    disabled={isSinglePageDownloadingPdf}
                    title="Export clean formatted PDF file"
                  >
                    {isSinglePageDownloadingPdf ? "Generating PDF..." : "📄 PDF (.pdf)"}
                  </button>
                </div>
              </div>

              {/* Single-Page Resume Paper Container */}
              <div className="fresher-preview-container">
                <ResumeSectionErrorBoundary>
                {singlePageResume ? (
                  <div
                    ref={singlePageResumeRef}
                    className={`single-page-resume-paper density-${singlePageDensity}`}
                    onMouseDown={() => {
                      lastActiveResumeRef.current = "single";
                    }}
                    style={{
                      ...(resumeFont ? { fontFamily: resumeFont } : {})
                    }}
                  >
                    {/* 1. Header: Clean Classic Layout Matching Resume 1 */}
                    <div className="resume-paper-header">
                      <div className="candidate-header-info">
                        <EditableResumeText
                          as="h2"
                          className={`candidate-name ${singlePageWordMode ? "word-editable" : ""}`}
                          value={formatCandidateName(singlePageResume.name)}
                          editable={singlePageWordMode}
                          onCommit={(val) => {
                            setSinglePageResumeWithHistory((prev) => (prev ? { ...prev, name: val } : prev));
                            triggerSinglePageSaveIndicator();
                          }}
                          title={singlePageWordMode ? "Click to edit candidate name" : ""}
                        />
                        <div className="candidate-contact">
                          {(() => {
                            const contactObj = getNormalizedContact(singlePageResume.contact);
                            const items = [];
                            if (contactObj.email) {
                              items.push(
                                <span key="email" className="contact-field-item">
                                  <span className="contact-icon">✉</span>
                                  <EditableResumeText
                                    as="span"
                                    className={`contact-val ${singlePageWordMode ? "word-editable" : ""}`}
                                    value={contactObj.email}
                                    editable={singlePageWordMode}
                                    onCommit={(val) => updateSinglePageContactField("email", val)}
                                    title={singlePageWordMode ? "Click to edit email" : ""}
                                  />
                                </span>
                              );
                            }
                            if (contactObj.phone) {
                              items.push(
                                <span key="phone" className="contact-field-item">
                                  <span className="contact-icon">📱</span>
                                  <EditableResumeText
                                    as="span"
                                    className={`contact-val ${singlePageWordMode ? "word-editable" : ""}`}
                                    value={formatPhoneDisplay(contactObj.phone)}
                                    editable={singlePageWordMode}
                                    onCommit={(val) => updateSinglePageContactField("phone", val)}
                                    title={singlePageWordMode ? "Click to edit phone" : ""}
                                  />
                                </span>
                              );
                            }
                            if (contactObj.location) {
                              items.push(
                                <span key="location" className="contact-field-item">
                                  <span className="contact-icon">📍</span>
                                  <EditableResumeText
                                    as="span"
                                    className={`contact-val ${singlePageWordMode ? "word-editable" : ""}`}
                                    value={contactObj.location}
                                    editable={singlePageWordMode}
                                    onCommit={(val) => updateSinglePageContactField("location", val)}
                                    title={singlePageWordMode ? "Click to edit location" : ""}
                                  />
                                </span>
                              );
                            }
                            if (contactObj.linkedin) {
                              items.push(
                                <a
                                  key="linkedin"
                                  href={contactObj.linkedin.startsWith("http") ? contactObj.linkedin : `https://${contactObj.linkedin.replace(/^https?:\/\//, "")}`}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="contact-link"
                                  title="Open LinkedIn Profile"
                                >
                                  <span className="contact-icon">🔗</span>
                                  <EditableResumeText as="span" className="contact-val" value="LinkedIn" editable={false} />
                                </a>
                              );
                            }
                            if (contactObj.github) {
                              items.push(
                                <a
                                  key="github"
                                  href={contactObj.github.startsWith("http") ? contactObj.github : `https://${contactObj.github.replace(/^https?:\/\//, "")}`}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="contact-link"
                                  title="Open GitHub Profile"
                                >
                                  <span className="contact-icon">💻</span>
                                  <EditableResumeText as="span" className="contact-val" value="GitHub" editable={false} />
                                </a>
                              );
                            }
                            return items.map((item, idx) => (
                              <span key={idx} style={{ display: "inline-flex", alignItems: "center" }}>
                                {idx > 0 && <EditableResumeText as="span" className="contact-sep" value="|" editable={false} />}
                                {item}
                              </span>
                            ));
                          })()}
                        </div>
                      </div>
                      {candidatePhoto && (
                        <div className="candidate-header-photo-wrap">
                          <img
                            src={candidatePhoto}
                            alt="Candidate"
                            className="candidate-header-photo"
                          />
                        </div>
                      )}
                    </div>

                    {/* 2. Summary */}
                    {singlePageResume.summary && (
                      <div className="resume-paper-block">
                        <EditableResumeText as="h4" className="resume-sec-title" value="SUMMARY" editable={false} />
                        <EditableResumeText
                          as="p"
                          className={`resume-summary-text ${singlePageWordMode ? "word-editable" : ""}`}
                          value={singlePageResume.summary}
                          editable={singlePageWordMode}
                          onCommit={(val) => updateSinglePageSummary(val)}
                          title={singlePageWordMode ? "Click to edit summary directly" : ""}
                        />
                      </div>
                    )}

                    {/* 3. Core Skills */}
                    {singlePageResume.skills && (
                      <div className="resume-paper-block">
                        <EditableResumeText as="h4" className="resume-sec-title" value="CORE SKILLS & TECHNOLOGIES" editable={false} />
                        <div className="resume-skills-block">
                          {Array.isArray(singlePageResume.skills) ? (
                            <div className="resume-skill-row">
                              <EditableResumeText as="strong" value="Technical Competencies: " editable={false} />
                              <EditableResumeText
                                as="span"
                                className={singlePageWordMode ? "word-editable" : ""}
                                value={singlePageResume.skills.join(", ")}
                                editable={singlePageWordMode}
                                onCommit={(val) => {
                                  const newArr = val.split(",").map((s) => s.trim()).filter(Boolean);
                                  setSinglePageResumeWithHistory((prev) => (prev ? { ...prev, skills: newArr } : prev));
                                  triggerSinglePageSaveIndicator();
                                }}
                                title={singlePageWordMode ? "Click to edit skills list" : ""}
                              />
                            </div>
                          ) : singlePageResume.skills && typeof singlePageResume.skills === "object" ? (
                            Object.entries(singlePageResume.skills).map(([cat, list]) => {
                              if (cat === "missing_from_resume" || !list || (Array.isArray(list) && list.length === 0)) return null;
                              const label =
                                cat === "matching_with_jd" || cat === "targeted_jd_stack" || cat === "Targeted JD Stack"
                                  ? "TARGETED JD STACK"
                                  : cat.replace(/_/g, " ").toUpperCase();
                              const valStr = Array.isArray(list) ? list.join(", ") : String(list);
                              if (!valStr.trim()) return null;
                              return (
                                <div key={cat} className="resume-skill-row">
                                  <EditableResumeText as="strong" value={`${label}: `} editable={false} />
                                  <EditableResumeText
                                    as="span"
                                    className={singlePageWordMode ? "word-editable" : ""}
                                    value={valStr}
                                    editable={singlePageWordMode}
                                    onCommit={(val) => updateSinglePageSkillCategory(cat, val)}
                                    title={singlePageWordMode ? `Click to edit ${label}` : ""}
                                  />
                                </div>
                              );
                            })
                          ) : (
                            <EditableResumeText as="p" value={String(singlePageResume.skills || "")} editable={false} />
                          )}
                        </div>
                      </div>
                    )}

                    {/* 4. Experience (Strictly 3 bullets per internship) */}
                    {safeArray(singlePageResume.experience).length > 0 && (
                      <div className="resume-paper-block">
                        <EditableResumeText as="h4" className="resume-sec-title" value="EXPERIENCE" editable={false} />
                        {safeArray(singlePageResume.experience).map((job, idx) => (
                          <div key={idx} className="resume-exp-item">
                            <div className="exp-line-header">
                              <div className="exp-title-company-wrap">
                                <EditableResumeText
                                  as="span"
                                  className={`exp-role ${singlePageWordMode ? "word-editable" : ""}`}
                                  value={job.role || job.title}
                                  editable={singlePageWordMode}
                                  onCommit={(val) => updateSinglePageExpRole(idx, val)}
                                  title={singlePageWordMode ? "Click to edit job role" : ""}
                                />
                                {job.company && (
                                  <>
                                    <EditableResumeText as="span" className="exp-pipe-sep" value="|" editable={false} />
                                    <EditableResumeText
                                      as="span"
                                      className={`exp-company exp-company-highlight ${singlePageWordMode ? "word-editable" : ""}`}
                                      value={job.company}
                                      editable={singlePageWordMode}
                                      onCommit={(val) => updateSinglePageExpCompany(idx, val)}
                                      title={singlePageWordMode ? "Click to edit company name" : ""}
                                    />
                                  </>
                                )}
                                {job.location && (
                                  <EditableResumeText
                                    as="span"
                                    className="exp-location-inline"
                                    value={` • ${job.location}`}
                                    editable={false}
                                  />
                                )}
                              </div>
                              <EditableResumeText
                                as="span"
                                className={`exp-duration ${singlePageWordMode ? "word-editable" : ""}`}
                                value={job.duration || job.dates}
                                editable={singlePageWordMode}
                                onCommit={(val) => updateSinglePageExpDuration(idx, val)}
                                title={singlePageWordMode ? "Click to edit duration" : ""}
                              />
                            </div>
                            <ul className="exp-bullets">
                              {safeArray(job.bullets)
                                .filter((b) => b && (typeof b === "string" ? cleanBulletText(b).length > 0 : true))
                                .map((b, bIdx) => (
                                  <li key={bIdx} className="word-bullet-item">
                                    <EditableResumeText
                                      as="span"
                                      className={`bullet-text ${singlePageWordMode ? "word-editable" : ""}`}
                                      value={cleanBulletText(b)}
                                      editable={singlePageWordMode}
                                      onCommit={(val) => updateSinglePageExpBullet(idx, bIdx, val)}
                                      title={singlePageWordMode ? "Click to edit bullet" : ""}
                                    />
                                    {singlePageWordMode && (
                                      <button
                                        type="button"
                                        className="btn-delete-bullet"
                                        onClick={() => deleteSinglePageExpBullet(idx, bIdx)}
                                        title="Delete bullet point"
                                      >
                                        ✕
                                      </button>
                                    )}
                                  </li>
                                ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* 5. Key Projects */}
                    {safeArray(singlePageResume.projects).length > 0 && (
                      <div className="resume-paper-block">
                        <EditableResumeText as="h4" className="resume-sec-title" value="KEY PROJECTS" editable={false} />
                        {safeArray(singlePageResume.projects).map((proj, idx) => (
                          <div key={idx} className="resume-proj-item">
                            <div className="proj-line-header">
                              <EditableResumeText
                                as="span"
                                className={`proj-name ${singlePageWordMode ? "word-editable" : ""}`}
                                value={proj.name || proj.title}
                                editable={singlePageWordMode}
                                onCommit={(val) => updateSinglePageProjectName(idx, val)}
                                title={singlePageWordMode ? "Click to edit project name" : ""}
                              />
                              {proj.technologies && (
                                <span className="proj-tech">
                                  <EditableResumeText as="span" value="(" editable={false} />
                                  <EditableResumeText
                                    as="span"
                                    className={singlePageWordMode ? "word-editable" : ""}
                                    value={proj.technologies}
                                    editable={singlePageWordMode}
                                    onCommit={(val) => updateSinglePageProjectTech(idx, val)}
                                    title={singlePageWordMode ? "Click to edit tech stack" : ""}
                                  />
                                  <EditableResumeText as="span" value=")" editable={false} />
                                </span>
                              )}
                            </div>
                            <ul className="proj-bullets">
                              {safeArray(proj.bullets)
                                .filter((b) => b && (typeof b === "string" ? cleanBulletText(b).length > 0 : true))
                                .map((b, bIdx) => (
                                  <li key={bIdx} className="word-bullet-item">
                                    <EditableResumeText
                                      as="span"
                                      className={`bullet-text ${singlePageWordMode ? "word-editable" : ""}`}
                                      value={cleanBulletText(b)}
                                      editable={singlePageWordMode}
                                      onCommit={(val) => updateSinglePageProjectBullet(idx, bIdx, val)}
                                      title={singlePageWordMode ? "Click to edit project bullet" : ""}
                                    />
                                    {singlePageWordMode && (
                                      <button
                                        type="button"
                                        className="btn-delete-bullet"
                                        onClick={() => deleteSinglePageProjBullet(idx, bIdx)}
                                        title="Delete project bullet"
                                      >
                                        ✕
                                      </button>
                                    )}
                                  </li>
                                ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* 6. Education */}
                    {safeArray(singlePageResume.education).length > 0 && (
                      <div className="resume-paper-block">
                        <EditableResumeText as="h4" className="resume-sec-title" value="EDUCATION" editable={false} />
                        {safeArray(singlePageResume.education).map((rawEdu, idx) => {
                          const edu = formatEducationItem(rawEdu);
                          return (
                            <div key={idx} className="resume-edu-item">
                              <div className="edu-line-header">
                                <EditableResumeText
                                  as="span"
                                  className={`edu-inst ${singlePageWordMode ? "word-editable" : ""}`}
                                  value={edu.instLine}
                                  editable={singlePageWordMode}
                                  onCommit={(val) => updateSinglePageEduInstitution(idx, val)}
                                  title={singlePageWordMode ? "Click to edit institution" : ""}
                                />
                                {edu.year && (
                                  <EditableResumeText
                                    as="span"
                                    className={`edu-duration ${singlePageWordMode ? "word-editable" : ""}`}
                                    value={edu.year}
                                    editable={singlePageWordMode}
                                    onCommit={(val) => updateSinglePageEduYear(idx, val)}
                                    title={singlePageWordMode ? "Click to edit year" : ""}
                                  />
                                )}
                              </div>
                              <div className="edu-line-sub">
                                <EditableResumeText
                                  as="span"
                                  className={`edu-degree ${singlePageWordMode ? "word-editable" : ""}`}
                                  value={edu.degreeLine}
                                  editable={singlePageWordMode}
                                  onCommit={(val) => updateSinglePageEduDegree(idx, val)}
                                  title={singlePageWordMode ? "Click to edit degree" : ""}
                                />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {/* 7. Certifications */}
                    {safeArray(singlePageResume.certifications).length > 0 && (
                      <div className="resume-paper-block">
                        <EditableResumeText as="h4" className="resume-sec-title" value="CERTIFICATIONS" editable={false} />
                        <ul className="cert-list">
                          {safeArray(singlePageResume.certifications).map((cert, idx) => (
                            <li key={idx} className="word-bullet-item">
                              <EditableResumeText
                                as="span"
                                className={`bullet-text ${singlePageWordMode ? "word-editable" : ""}`}
                                value={cert}
                                editable={singlePageWordMode}
                                onCommit={(val) => updateSinglePageCert(idx, val)}
                                title={singlePageWordMode ? "Click to edit certification" : ""}
                              />
                              {singlePageWordMode && (
                                <button
                                  type="button"
                                  className="btn-delete-bullet"
                                  onClick={() => deleteSinglePageCert(idx)}
                                  title="Delete certification"
                                >
                                  ✕
                                </button>
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ textAlign: "center", padding: "40px", color: "#64748b" }}>
                    Single-page fresher resume will appear here once generated.
                  </div>
                )}
                </ResumeSectionErrorBoundary>
              </div>
            </section>
          </div>
        )}
      </main>
      {/* Lightbox Modal for Enlarged Screenshot Preview */}
      {lightboxImage && (
        <div className="lightbox-overlay" onClick={() => setLightboxImage(null)}>
          <div className="lightbox-modal" onClick={(e) => e.stopPropagation()}>
            <div className="lightbox-header">
              <span className="lightbox-title">📷 Attached Screenshot Preview</span>
              <button

                type="button"

                className="lightbox-close-btn"

                onClick={() => setLightboxImage(null)}

              >

                ✕ Close

              </button>
            </div>
            <div className="lightbox-body">
              <img src={lightboxImage} alt="Enlarged Screenshot" className="lightbox-img" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;

