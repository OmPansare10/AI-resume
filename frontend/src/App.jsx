import { useState, useEffect, useRef } from "react";
import "./App.css";

const API_BASE = "http://127.0.0.1:8001/api";

const QUICK_PROMPTS = [
  "Switch project database to MongoDB & Redis",
  "Emphasize Python and FastAPI microservices in bullets",
  "Add AWS Solutions Architect certification",
  "Make experience bullet points more metrics-driven",
  "Shorten project descriptions for conciseness"
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

  // AI Chatbox Copilot state & ref
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
  const [chatAttachedImages, setChatAttachedImages] = useState([]); // array of { id, dataUrl, name, size }
  const [lightboxImage, setLightboxImage] = useState(null);
  const [isChatDragging, setIsChatDragging] = useState(false);
  const [isChatSubmitting, setIsChatSubmitting] = useState(false);
  const chatEndRef = useRef(null);
  const chatFileInputRef = useRef(null);

  const formatFileSize = (bytes) => {
    if (!bytes) return "";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  const handleAttachChatImages = (files) => {
    if (!files || files.length === 0) return;
    const fileList = Array.from(files);
    fileList.forEach((file) => {
      if (!file.type || !file.type.startsWith("image/")) return;
      const reader = new FileReader();
      reader.onload = (event) => {
        setChatAttachedImages((prev) => [
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

  const handleRemoveChatImage = (idToRemove) => {
    setChatAttachedImages((prev) => prev.filter((img) => img.id !== idToRemove));
  };

  const handleChatPaste = (e) => {
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
        handleAttachChatImages(imgFiles);
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

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatMessages, isChatSubmitting]);

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

  const triggerSaveIndicator = (msg = "✓ Auto-Saved to Document") => {
    setSaveIndicator(msg);
    setTimeout(() => setSaveIndicator(""), 2500);
  };

  const handleSelectionSizeAdjust = (delta) => {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) {
      triggerSaveIndicator("💡 Highlight text in resume to resize");
      return;
    }

    const range = sel.getRangeAt(0);

    // Ensure selection or focus is inside the resume paper
    if (!resumeRef.current || !resumeRef.current.contains(range.commonAncestorContainer)) {
      triggerSaveIndicator("💡 Highlight text in resume to resize");
      return;
    }

    if (range.collapsed) {
      // Cursor is placed inside an element without highlighting
      let el = range.commonAncestorContainer;
      if (el.nodeType === Node.TEXT_NODE) el = el.parentElement;
      if (el && el !== resumeRef.current && resumeRef.current.contains(el)) {
        const computed = window.getComputedStyle(el);
        const currentSize = parseFloat(computed.fontSize) || 12;
        const newSize = Math.max(8, Math.min(48, Math.round((currentSize + delta) * 10) / 10));
        el.style.fontSize = `${newSize}px`;
        triggerSaveIndicator(`✓ Size: ${newSize}px`);
      } else {
        triggerSaveIndicator("💡 Highlight text in resume to resize");
      }
      return;
    }

    // Text IS highlighted (range is not collapsed)
    try {
      let parent = range.commonAncestorContainer;
      if (parent.nodeType === Node.TEXT_NODE) parent = parent.parentElement;

      // If already wrapped in a custom sizing span and selection matches it
      if (
        parent &&
        parent.tagName === "SPAN" &&
        parent.classList.contains("selected-text-resize") &&
        parent.textContent === sel.toString()
      ) {
        const currentSize = parseFloat(window.getComputedStyle(parent).fontSize) || 12;
        const newSize = Math.max(8, Math.min(48, Math.round((currentSize + delta) * 10) / 10));
        parent.style.fontSize = `${newSize}px`;
        triggerSaveIndicator(`✓ Selected Text: ${newSize}px`);
        return;
      }

      // Calculate new size based on current computed font size
      const currentSize = parseFloat(window.getComputedStyle(parent).fontSize) || 12;
      const newSize = Math.max(8, Math.min(48, Math.round((currentSize + delta) * 10) / 10));

      const span = document.createElement("span");
      span.className = "selected-text-resize";
      span.style.fontSize = `${newSize}px`;
      span.appendChild(range.extractContents());
      range.insertNode(span);

      // Re-select newly sized text so user can click A+ / A- multiple times seamlessly
      const newRange = document.createRange();
      newRange.selectNodeContents(span);
      sel.removeAllRanges();
      sel.addRange(newRange);

      triggerSaveIndicator(`✓ Selected Text: ${newSize}px`);
    } catch (err) {
      console.warn("Selection size adjust fallback:", err);
    }
  };

  const handleSelectionFontChange = (fontFamily) => {
    if (!fontFamily) {
      setResumeFont("");
      return;
    }

    const sel = window.getSelection();
    if (sel && sel.rangeCount > 0) {
      const range = sel.getRangeAt(0);
      if (
        resumeRef.current &&
        resumeRef.current.contains(range.commonAncestorContainer) &&
        !range.collapsed
      ) {
        try {
          let parent = range.commonAncestorContainer;
          if (parent.nodeType === Node.TEXT_NODE) parent = parent.parentElement;

          if (
            parent &&
            parent.tagName === "SPAN" &&
            parent.classList.contains("selected-text-font") &&
            parent.textContent === sel.toString()
          ) {
            parent.style.fontFamily = fontFamily;
            const fontName = fontFamily.split(",")[0].replace(/['"]/g, "");
            triggerSaveIndicator(`✓ Selected Font: ${fontName}`);
            return;
          }

          const span = document.createElement("span");
          span.className = "selected-text-font";
          span.style.fontFamily = fontFamily;
          span.appendChild(range.extractContents());
          range.insertNode(span);

          const newRange = document.createRange();
          newRange.selectNodeContents(span);
          sel.removeAllRanges();
          sel.addRange(newRange);

          const fontName = fontFamily.split(",")[0].replace(/['"]/g, "");
          triggerSaveIndicator(`✓ Selected Font: ${fontName}`);
          return;
        } catch (err) {
          console.warn("Font selection change error:", err);
        }
      }
    }

    // Default to document-level font
    setResumeFont(fontFamily);
    const fontName = fontFamily.split(",")[0].replace(/['"]/g, "");
    triggerSaveIndicator(`✓ Document Font: ${fontName}`);
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
          model: data.model || "llama3.2:3b",
          model_found: data.model_found,
          error: data.error
        });
      } else {
        setHealth({
          loading: false,
          ollama: false,
          model: "llama3.2:3b",
          model_found: false,
          error: "Backend responded with an error."
        });
      }
    } catch {
      setHealth({
        loading: false,
        ollama: false,
        model: "llama3.2:3b",
        model_found: false,
        error: "Cannot connect to backend server on port 8001."
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
      setMatchScore(analyzeData.match_score || 50);

      setAppState("completed");
      setStatusMessage("Tailored Resume ready!");

      const roleTitle = analyzeData.analysis?.job_title || "Target Role";
      setChatMessages((prev) => [
        ...prev,
        {
          id: Date.now(),
          sender: "ai",
          text: `🎉 Your tailored resume for "${roleTitle}" is ready! All projects are adapted to the target stack & database, industry certifications aligned, and keywords integrated. You can type in the box below to modify any part!`,
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
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

  // Handle Chatbox Query Submit to change resume according to user text & attached screenshot(s)
  const handleChatSubmit = async (queryText) => {
    const query = (queryText || chatInput).trim();
    const imagesToSend = [...chatAttachedImages];
    if ((!query && imagesToSend.length === 0) || isChatSubmitting) return;

    const timeStr = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit"
    });
    const userMsg = {
      id: Date.now(),
      sender: "user",
      text: query || (imagesToSend.length > 0 ? `📷 Attached ${imagesToSend.length} photo(s) for resume update` : ""),
      images: imagesToSend.map((img) => img.dataUrl),
      imagesMeta: imagesToSend,
      time: timeStr
    };

    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput("");
    setChatAttachedImages([]);

    if (!tailoredResume) {
      setTimeout(() => {
        setChatMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            sender: "ai",
            text: "Please generate your initial tailored resume above first. Then whatever problem you type or screenshot you upload/paste here will directly update your resume in real time!",
            time: new Date().toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit"
            }),
            isNotice: true
          }
        ]);
      }, 300);
      return;
    }

    setIsChatSubmitting(true);

    try {
      const res = await fetch(`${API_BASE}/edit-resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resume_content: { ...tailoredResume, photo: candidatePhoto },
          instruction: query,
          image_data: imagesToSend[0]?.dataUrl || null,
          images_data: imagesToSend.map((img) => img.dataUrl),
          original_resume_text: extractedResume,
          jd_text: extractedJd
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
        setTailoredResume(updated);
      }

      const appliedChanges = data.changes || [
        `Updated resume according to: "${query || "attached image(s)"}"`
      ];

      setChatMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: "ai",
          text: `✓ Resume updated successfully based on your problem & photo(s)!`,
          changes: appliedChanges,
          extractedText: data.image_extracted_text || null,
          time: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit"
          })
        }
      ]);
    } catch (err) {
      console.error(err);
      setChatMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: "ai",
          text: `Update failed: ${err.message}`,
          isError: true,
          time: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit"
          })
        }
      ]);
    } finally {
      setIsChatSubmitting(false);
    }
  };

  const handleDownload = async () => {
    if (!tailoredResume) return;

    setIsDownloading(true);
    try {
      const payload = {
        ...tailoredResume,
        photo: candidatePhoto
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
        photo: candidatePhoto
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
                  ? "Checking Ollama..."
                  : health.ollama
                  ? `Ollama: ${health.model}`
                  : "Ollama Offline"}
              </span>
            </div>
            <span className="secure-badge">🔒 100% Local & Private</span>
          </div>
        </div>
      </header>

      {/* Warning banner if Ollama is offline */}
      {!health.loading && (!health.ollama || !health.model_found) && (
        <div className="warning-banner">
          <div className="warning-content">
            <span className="warning-icon">⚠️</span>
            <div>
              <strong>Local Ollama Service Required</strong>
              <p>
                {health.error || "Ollama is not running on localhost:11434."}{" "}
                Please start Ollama on your PC (<code>ollama run {health.model}</code>)
                to enable local AI tailoring.
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

            {/* SECTION 4: AI CHATBOX COPILOT */}
            <div className="chatbox-card chatbox-above-resume">
              <div className="chatbox-header">
                <div className="chatbox-header-left">
                  <span className="chatbox-icon">💬</span>
                  <div>
                    <h3 className="chatbox-title">AI Resume Copilot Chat</h3>
                    <p className="chatbox-subtitle">
                      Type your problem, upload, or paste (Ctrl+V) any screenshot / photo like ChatGPT — the AI extracts the details and updates the resume below in real time!
                    </p>
                  </div>
                </div>
                <div className="chatbox-header-right">
                  <span className="chat-status-pill live">
                    <span className="pill-dot"></span> Live Resume Synced
                  </span>
                </div>
              </div>

              {/* Chat Messages Stream */}
              <div className="chatbox-stream">
                {chatMessages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`chat-message ${
                      msg.sender === "user" ? "user-msg" : "ai-msg"
                    } ${msg.isNotice ? "notice-msg" : ""} ${
                      msg.isError ? "error-msg" : ""
                    }`}
                  >
                    <div className="msg-avatar">
                      {msg.sender === "user" ? "👤" : "✨"}
                    </div>
                    <div className="msg-bubble">
                      <div className="msg-header">
                        <span className="msg-sender-name">
                          {msg.sender === "user" ? "You" : "Resume Copilot"}
                        </span>
                        <span className="msg-time">{msg.time}</span>
                      </div>

                      {/* Display attached image thumbnail(s) in user message */}
                      {((msg.images && msg.images.length > 0) || msg.image) && (
                        <div className="msg-images-gallery">
                          {(msg.images || [msg.image]).map((imgSrc, imgIdx) => (
                            <div
                              key={imgIdx}
                              className="msg-image-wrap"
                              onClick={() => setLightboxImage(imgSrc)}
                              title="Click to view full image"
                            >
                              <img
                                src={imgSrc}
                                alt={`Attached photo ${imgIdx + 1}`}
                                className="msg-attached-img"
                              />
                              <div className="msg-image-meta">
                                <span>📷 Photo {imgIdx + 1}</span>
                                <span className="zoom-hint">🔍 Zoom</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      <p className="msg-text">{msg.text}</p>

                      {/* Extracted OCR Information Note */}
                      {msg.extractedText && (
                        <div className="msg-extracted-note">
                          <span className="ocr-badge">🔍 Extracted from Image:</span>
                          <p className="ocr-snippet">
                            {msg.extractedText.slice(0, 180)}
                            {msg.extractedText.length > 180 ? "..." : ""}
                          </p>
                        </div>
                      )}

                      {msg.changes && msg.changes.length > 0 && (
                        <div className="msg-changes-list">
                          <strong>Modifications Applied:</strong>
                          <ul>
                            {msg.changes.map((ch, cIdx) => (
                              <li key={cIdx}>✓ {ch}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {isChatSubmitting && (
                  <div className="chat-message ai-msg typing-msg">
                    <div className="msg-avatar">✨</div>
                    <div className="msg-bubble">
                      <div className="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                      <span className="typing-text">
                        Analyzing your problem & screenshot, extracting details, and updating resume in real time...
                      </span>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Quick Prompt Suggestion Chips */}
              <div className="chatbox-suggestions">
                <span className="suggestions-label">Suggestions:</span>
                {QUICK_PROMPTS.map((prompt, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="chat-chip"
                    onClick={() => handleChatSubmit(prompt)}
                    disabled={isChatSubmitting}
                  >
                    + {prompt}
                  </button>
                ))}
              </div>

              {/* Attachment Preview Strip (supports multiple attached photos) */}
              {chatAttachedImages.length > 0 && (
                <div className="chatbox-attachments-strip">
                  <div className="attachments-header-row">
                    <span className="attachments-count-badge">
                      📷 {chatAttachedImages.length} Photo{chatAttachedImages.length > 1 ? "s" : ""} Ready to Send
                    </span>
                    <button
                      type="button"
                      className="attachments-clear-all"
                      onClick={() => setChatAttachedImages([])}
                    >
                      Clear all
                    </button>
                  </div>
                  <div className="attachments-cards-row">
                    {chatAttachedImages.map((att) => (
                      <div key={att.id} className="chatbox-attachment-card">
                        <div
                          className="attachment-thumb-wrap"
                          onClick={() => setLightboxImage(att.dataUrl)}
                          title="Click to zoom image"
                        >
                          <img
                            src={att.dataUrl}
                            alt={att.name}
                            className="attachment-thumb"
                          />
                          <span className="attachment-zoom-hint">🔍</span>
                        </div>
                        <div className="attachment-info">
                          <span className="attachment-name" title={att.name}>
                            {att.name}
                          </span>
                          <span className="attachment-size">{att.size}</span>
                        </div>
                        <button
                          type="button"
                          className="attachment-remove-btn"
                          onClick={() => handleRemoveChatImage(att.id)}
                          title="Remove attached image"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                    <button
                      type="button"
                      className="attachment-add-more-btn"
                      onClick={() => chatFileInputRef.current?.click()}
                      title="Add another photo / screenshot"
                    >
                      <span>+ Add Photo</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Chat Input Bar (ChatGPT style with 📎 upload, Ctrl+V, drag & drop) */}
              <form
                className={`chatbox-input-row ${isChatDragging ? "dragging-over" : ""}`}
                onSubmit={(e) => {
                  e.preventDefault();
                  handleChatSubmit();
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsChatDragging(true);
                }}
                onDragLeave={() => setIsChatDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsChatDragging(false);
                  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                    handleAttachChatImages(e.dataTransfer.files);
                  }
                }}
              >
                {/* Hidden file input for uploading images (supports multiple) */}
                <input
                  type="file"
                  ref={chatFileInputRef}
                  style={{ display: "none" }}
                  accept="image/*"
                  multiple
                  onChange={(e) => {
                    if (e.target.files && e.target.files.length > 0) {
                      handleAttachChatImages(e.target.files);
                      e.target.value = "";
                    }
                  }}
                />

                {/* Attach File Button */}
                <button
                  type="button"
                  className={`chat-attach-btn ${chatAttachedImages.length > 0 ? "has-attachment" : ""}`}
                  onClick={() => chatFileInputRef.current?.click()}
                  title="Upload images / screenshots (supports multiple, or paste with Ctrl+V)"
                  disabled={isChatSubmitting}
                >
                  <span className="attach-icon">📎</span>
                  <span className="attach-btn-label">
                    {chatAttachedImages.length > 0 ? `Images (${chatAttachedImages.length})` : "Images"}
                  </span>
                </button>

                <textarea
                  className="chatbox-input chatbox-textarea"
                  rows={1}
                  placeholder="Type anything to change or paste screenshot (Ctrl+V) like ChatGPT (e.g. 'Add this certificate', 'Change projects to match screenshot', 'Use as photo')..."
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onPaste={handleChatPaste}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleChatSubmit();
                    }
                  }}
                  disabled={isChatSubmitting}
                />

                <button
                  type="submit"
                  className="chatbox-send-btn"
                  disabled={isChatSubmitting || (!chatInput.trim() && chatAttachedImages.length === 0)}
                >
                  {isChatSubmitting ? (
                    <span className="chat-btn-spinner" />
                  ) : (
                    <>
                      <span>Update Resume</span>
                      <span className="send-arrow">➤</span>
                    </>
                  )}
                </button>
              </form>
            </div>

            {/* SECTION 5: CLEAN CLASSIC AI TAILORED RESUME PREVIEW */}
            <section className="dashboard-section resume-preview-section">
              <div className="section-title-wrap resume-preview-header-wrap">
                <div className="section-title-left">
                  <span className="section-num">04</span>
                  <h3>AI Tailored Resume Preview</h3>
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
                      estimatedPages === 1 ? "badge-single" : "badge-multi"
                    }`}
                  >
                    <span className="page-badge-dot"></span>
                    <span className="page-badge-text">
                      {estimatedPages === 1
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
                    onChange={(e) => handleSelectionFontChange(e.target.value)}
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
                      onClick={() => handleSelectionSizeAdjust(-1)}
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
                      onClick={() => handleSelectionSizeAdjust(1)}
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
                <div
                  className={`resume-paper ${
                    tailoredResume?.compact_layout || tailoredResume?.single_page
                      ? "compact-1page"
                      : ""
                  } ${isWordMode ? "word-mode-active" : ""}`}
                  ref={resumeRef}
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
                      <h2
                        className={`candidate-name ${isWordMode ? "word-editable" : ""}`}
                        contentEditable={isWordMode}
                        suppressContentEditableWarning={true}
                        onBlur={(e) => updateField("name", e.currentTarget.textContent)}
                        title={isWordMode ? "Click to edit candidate name" : ""}
                      >
                        {tailoredResume.name || "Candidate Name"}
                      </h2>
                      <div className="candidate-contact">
                        {typeof tailoredResume.contact === "string" ? (
                          <span
                            className={isWordMode ? "word-editable" : ""}
                            contentEditable={isWordMode}
                            suppressContentEditableWarning={true}
                            onBlur={(e) => updateField("contact", e.currentTarget.textContent)}
                          >
                            {tailoredResume.contact}
                          </span>
                        ) : tailoredResume.contact && typeof tailoredResume.contact === "object" ? (
                          <div className="candidate-contact-fields">
                            {tailoredResume.contact.email && (
                              <span
                                className={`contact-field-item ${isWordMode ? "word-editable" : ""}`}
                                contentEditable={isWordMode}
                                suppressContentEditableWarning={true}
                                onBlur={(e) => updateContactField("email", e.currentTarget.textContent)}
                                title={isWordMode ? "Click to edit email" : ""}
                              >
                                {tailoredResume.contact.email}
                              </span>
                            )}
                            {tailoredResume.contact.email && tailoredResume.contact.phone && <span className="contact-sep"> • </span>}
                            {tailoredResume.contact.phone && (
                              <span
                                className={`contact-field-item ${isWordMode ? "word-editable" : ""}`}
                                contentEditable={isWordMode}
                                suppressContentEditableWarning={true}
                                onBlur={(e) => updateContactField("phone", e.currentTarget.textContent)}
                                title={isWordMode ? "Click to edit phone" : ""}
                              >
                                {tailoredResume.contact.phone}
                              </span>
                            )}
                            {tailoredResume.contact.location && <span className="contact-sep"> • </span>}
                            {tailoredResume.contact.location && (
                              <span
                                className={`contact-field-item ${isWordMode ? "word-editable" : ""}`}
                                contentEditable={isWordMode}
                                suppressContentEditableWarning={true}
                                onBlur={(e) => updateContactField("location", e.currentTarget.textContent)}
                                title={isWordMode ? "Click to edit location" : ""}
                              >
                                {tailoredResume.contact.location}
                              </span>
                            )}
                            {tailoredResume.contact.linkedin && <span className="contact-sep"> • </span>}
                            {tailoredResume.contact.linkedin && (
                              <span
                                className={`contact-field-item ${isWordMode ? "word-editable" : ""}`}
                                contentEditable={isWordMode}
                                suppressContentEditableWarning={true}
                                onBlur={(e) => updateContactField("linkedin", e.currentTarget.textContent)}
                                title={isWordMode ? "Click to edit LinkedIn" : ""}
                              >
                                {tailoredResume.contact.linkedin}
                              </span>
                            )}
                            {tailoredResume.contact.github && <span className="contact-sep"> • </span>}
                            {tailoredResume.contact.github && (
                              <span
                                className={`contact-field-item ${isWordMode ? "word-editable" : ""}`}
                                contentEditable={isWordMode}
                                suppressContentEditableWarning={true}
                                onBlur={(e) => updateContactField("github", e.currentTarget.textContent)}
                                title={isWordMode ? "Click to edit GitHub" : ""}
                              >
                                {tailoredResume.contact.github}
                              </span>
                            )}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </div>

                  {/* Professional Summary */}
                  <div className="resume-paper-block">
                    <h4 className="resume-sec-title">PROFESSIONAL SUMMARY</h4>
                    <p
                      className={`resume-summary-text ${isWordMode ? "word-editable" : ""}`}
                      contentEditable={isWordMode}
                      suppressContentEditableWarning={true}
                      onBlur={(e) => updateField("summary", e.currentTarget.textContent)}
                      title={isWordMode ? "Click to edit summary directly" : ""}
                    >
                      {tailoredResume.summary}
                    </p>
                  </div>

                  {/* Core Skills */}
                  <div className="resume-paper-block">
                    <h4 className="resume-sec-title">CORE SKILLS & TECHNOLOGIES</h4>
                    <div className="resume-skills-block">
                      {Array.isArray(tailoredResume.skills) ? (
                        <div className="resume-skill-row">
                          <strong>Technical Competencies:</strong>{" "}
                          <span
                            className={isWordMode ? "word-editable" : ""}
                            contentEditable={isWordMode}
                            suppressContentEditableWarning={true}
                            onBlur={(e) => updateField("skills", e.currentTarget.textContent.split(",").map((s) => s.trim()).filter(Boolean))}
                            title={isWordMode ? "Click to edit skills list" : ""}
                          >
                            {tailoredResume.skills.join(", ")}
                          </span>
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
                              <strong>{label}:</strong>{" "}
                              <span
                                className={isWordMode ? "word-editable" : ""}
                                contentEditable={isWordMode}
                                suppressContentEditableWarning={true}
                                onBlur={(e) => updateSkillCategory(cat, e.currentTarget.textContent)}
                                title={isWordMode ? `Click to edit ${label}` : ""}
                              >
                                {Array.isArray(list) ? list.join(", ") : String(list)}
                              </span>
                            </div>
                          );
                        })
                      ) : (
                        <p>{String(tailoredResume.skills || "")}</p>
                      )}
                    </div>
                  </div>

                  {/* Professional Experience */}
                  {tailoredResume.experience?.length > 0 && (
                    <div className="resume-paper-block">
                      <h4 className="resume-sec-title">PROFESSIONAL EXPERIENCE</h4>
                      {tailoredResume.experience.map((job, idx) => (
                        <div key={idx} className="resume-exp-item">
                          <div className="exp-line-header">
                            <span
                              className={`exp-role ${isWordMode ? "word-editable" : ""}`}
                              contentEditable={isWordMode}
                              suppressContentEditableWarning={true}
                              onBlur={(e) => updateExpField(idx, "role", e.currentTarget.textContent)}
                              title={isWordMode ? "Click to edit job role" : ""}
                            >
                              {job.role || job.title}
                            </span>
                            <span
                              className={`exp-duration ${isWordMode ? "word-editable" : ""}`}
                              contentEditable={isWordMode}
                              suppressContentEditableWarning={true}
                              onBlur={(e) => updateExpField(idx, "duration", e.currentTarget.textContent)}
                              title={isWordMode ? "Click to edit duration" : ""}
                            >
                              {job.duration || job.dates}
                            </span>
                          </div>
                          <div className="exp-line-sub">
                            <span
                              className={`exp-company ${isWordMode ? "word-editable" : ""}`}
                              contentEditable={isWordMode}
                              suppressContentEditableWarning={true}
                              onBlur={(e) => updateExpField(idx, "company", e.currentTarget.textContent)}
                              title={isWordMode ? "Click to edit company name" : ""}
                            >
                              {job.company}
                            </span>
                            {job.location && (
                              <span className="exp-location">
                                •{" "}
                                <span
                                  className={isWordMode ? "word-editable" : ""}
                                  contentEditable={isWordMode}
                                  suppressContentEditableWarning={true}
                                  onBlur={(e) => updateExpField(idx, "location", e.currentTarget.textContent)}
                                  title={isWordMode ? "Click to edit location" : ""}
                                >
                                  {job.location}
                                </span>
                              </span>
                            )}
                          </div>
                          <ul className="exp-bullets">
                            {job.bullets?.map((b, bIdx) => (
                              <li key={bIdx} className="word-bullet-item">
                                <span
                                  className={`bullet-text ${isWordMode ? "word-editable" : ""}`}
                                  contentEditable={isWordMode}
                                  suppressContentEditableWarning={true}
                                  onBlur={(e) => updateExpBullet(idx, bIdx, e.currentTarget.textContent)}
                                  title={isWordMode ? "Click to edit bullet" : ""}
                                >
                                  {b}
                                </span>
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
                  {tailoredResume.projects?.length > 0 && (
                    <div className="resume-paper-block">
                      <h4 className="resume-sec-title">KEY PROJECTS</h4>
                      {tailoredResume.projects.map((proj, idx) => (
                        <div key={idx} className="resume-proj-item">
                          <div className="proj-line-header">
                            <span
                              className={`proj-name ${isWordMode ? "word-editable" : ""}`}
                              contentEditable={isWordMode}
                              suppressContentEditableWarning={true}
                              onBlur={(e) => updateProjField(idx, "name", e.currentTarget.textContent)}
                              title={isWordMode ? "Click to edit project name" : ""}
                            >
                              {proj.name || proj.title}
                            </span>
                            {proj.technologies && (
                              <span className="proj-tech">
                                (
                                <span
                                  className={isWordMode ? "word-editable" : ""}
                                  contentEditable={isWordMode}
                                  suppressContentEditableWarning={true}
                                  onBlur={(e) => updateProjField(idx, "technologies", e.currentTarget.textContent)}
                                  title={isWordMode ? "Click to edit tech stack" : ""}
                                >
                                  {proj.technologies}
                                </span>
                                )
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
                            {proj.bullets?.map((b, bIdx) => (
                              <li key={bIdx} className="word-bullet-item">
                                <span
                                  className={`bullet-text ${isWordMode ? "word-editable" : ""}`}
                                  contentEditable={isWordMode}
                                  suppressContentEditableWarning={true}
                                  onBlur={(e) => updateProjBullet(idx, bIdx, e.currentTarget.textContent)}
                                  title={isWordMode ? "Click to edit project bullet" : ""}
                                >
                                  {b}
                                </span>
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
                  {tailoredResume.education?.length > 0 && (
                    <div className="resume-paper-block">
                      <h4 className="resume-sec-title">EDUCATION</h4>
                      {tailoredResume.education.map((edu, idx) => (
                        <div key={idx} className="resume-edu-item">
                          <strong
                            className={isWordMode ? "word-editable" : ""}
                            contentEditable={isWordMode}
                            suppressContentEditableWarning={true}
                            onBlur={(e) => updateEduField(idx, "degree", e.currentTarget.textContent)}
                            title={isWordMode ? "Click to edit degree" : ""}
                          >
                            {edu.degree}
                          </strong>{" "}
                          –{" "}
                          <span
                            className={isWordMode ? "word-editable" : ""}
                            contentEditable={isWordMode}
                            suppressContentEditableWarning={true}
                            onBlur={(e) => updateEduField(idx, "institution", e.currentTarget.textContent)}
                            title={isWordMode ? "Click to edit institution" : ""}
                          >
                            {edu.institution || edu.university}
                          </span>{" "}
                          {edu.year && (
                            <span
                              className={isWordMode ? "word-editable" : ""}
                              contentEditable={isWordMode}
                              suppressContentEditableWarning={true}
                              onBlur={(e) => updateEduField(idx, "year", e.currentTarget.textContent.replace(/[()]/g, ""))}
                              title={isWordMode ? "Click to edit year" : ""}
                            >
                              ({edu.year})
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Certifications */}
                  {tailoredResume.certifications?.length > 0 && (
                    <div className="resume-paper-block">
                      <h4 className="resume-sec-title">CERTIFICATIONS</h4>
                      <ul className="cert-list">
                        {tailoredResume.certifications.map((cert, idx) => (
                          <li key={idx} className="word-bullet-item">
                            <span
                              className={`bullet-text ${isWordMode ? "word-editable" : ""}`}
                              contentEditable={isWordMode}
                              suppressContentEditableWarning={true}
                              onBlur={(e) => updateCert(idx, e.currentTarget.textContent)}
                              title={isWordMode ? "Click to edit certification" : ""}
                            >
                              {cert}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
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
