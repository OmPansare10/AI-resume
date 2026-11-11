/**
 * Intelligent Dynamic Resume Layout Engine
 * -----------------------------------------
 * Measures actual rendered content and dynamically optimizes vertical spacing,
 * section margins, item gaps, bullet line-heights, and typography so that:
 * 1. Unused whitespace at the bottom of the resume is automatically eliminated.
 * 2. Content is gracefully distributed across the available A4 page height (1123px @ 96 DPI).
 * 3. Priority order strictly followed:
 *    - Normalize section margins and paragraph spacing.
 *    - Optimize line height within readable limits.
 *    - Adjust gaps between sections.
 *    - Adjust gaps between entries and bullet points.
 *    - Distribute remaining free space proportionally.
 *    - Gently scale font size only when necessary within safe readability limits.
 * 4. Never inserts blank paragraphs or simulates spacing with empty elements.
 * 5. Multi-page pagination avoids orphaned headings and splits cleanly.
 */

// Standard A4 Dimensions at 96 DPI (210mm x 297mm)
export const A4_HEIGHT_PX = 1123;
export const A4_WIDTH_PX = 794;

/**
 * Calculates optimal dynamic CSS layout properties for a single-page resume
 * based on actual DOM measurements.
 *
 * @param {HTMLElement} container - The resume paper DOM element.
 * @param {Object} options - Custom configuration overrides.
 * @returns {Object} Layout metrics and computed CSS custom properties.
 */
export function computeSinglePageLayout(container, options = {}) {
  const defaultLayout = {
    cssVars: {},
    isOverflowing: false,
    overflowPx: 0,
    utilizationPct: 100,
    fitStatus: "normal"
  };

  if (!container || typeof container.querySelectorAll !== "function" || !container.style) {
    return defaultLayout;
  }

  try {

  // Count key structural elements
  const sections = container.querySelectorAll(".resume-paper-block");
  const expItems = container.querySelectorAll(".resume-exp-item");
  const projItems = container.querySelectorAll(".resume-proj-item");
  const eduItems = container.querySelectorAll(".resume-edu-item");
  const bullets = container.querySelectorAll(".exp-bullets > li, .proj-bullets > li, .cert-list > li");

  const numSections = Math.max(1, sections.length);
  const numItems = Math.max(1, expItems.length + projItems.length + eduItems.length);
  const numBullets = Math.max(1, bullets.length);

  // Set minHeight to 0px temporarily to measure true unconstrained natural height
  const savedMinHeight = container.style.minHeight;
  container.style.minHeight = "0px";

  // Set baseline measurement styles temporarily to obtain natural unexpanded height
  container.style.setProperty("--page-padding-y", "20px");
  container.style.setProperty("--page-padding-x", "48px");
  container.style.setProperty("--section-gap", "5px");
  container.style.setProperty("--section-title-margin-bottom", "2px");
  container.style.setProperty("--item-gap", "3px");
  container.style.setProperty("--bullet-gap", "1px");
  container.style.setProperty("--bullet-line-height", "1.26");
  container.style.setProperty("--body-line-height", "1.28");
  container.style.setProperty("--body-font-size", "9.8px");
  container.style.setProperty("--heading-font-size", "11px");
  container.style.setProperty("--name-font-size", "19px");
  container.style.setProperty("--header-margin-bottom", "6px");

  // Force layout flush and measure natural unconstrained scrollHeight
  const rawHeight = container.scrollHeight;
  container.style.minHeight = savedMinHeight || "";
  const targetHeight = options.targetHeight || A4_HEIGHT_PX;
  
  // Available height inside target A4 page
  const availableDelta = targetHeight - rawHeight;

  let computedVars = {};
  let isOverflowing = false;
  let overflowPx = 0;
  let utilizationPct = 100;
  let fitStatus = "balanced";

  if (availableDelta > 30) {
    // -------------------------------------------------------------------------
    // SCENARIO 1: SUBSTANTIAL UNUSED SPACE AT BOTTOM (AvailableDelta > 30px)
    // Distribute availableDelta proportionally across sections, items, and bullets
    // so content fills the entire page beautifully and naturally.
    // -------------------------------------------------------------------------
    fitStatus = "expanded";

    // Space distribution weights:
    // 15% to page padding top & bottom
    // 35% to section gaps
    // 25% to item gaps
    // 15% to bullet gaps & line height
    // 10% to header margin & summary
    const padBudget = availableDelta * 0.15;
    const secBudget = availableDelta * 0.35;
    const itemBudget = availableDelta * 0.25;
    const bulletBudget = availableDelta * 0.15;

    // 1. Page padding: expand from 18px up to 34px
    const addedPadPerSide = Math.min(16, padBudget / 2);
    const pagePaddingY = Math.round(18 + addedPadPerSide);

    // 2. Section gaps: expand from 5px up to 18px
    const addedSecGap = Math.min(13, secBudget / numSections);
    const sectionGap = Math.round((5 + addedSecGap) * 10) / 10;
    const sectionTitleMarginBottom = Math.round((2 + addedSecGap * 0.3) * 10) / 10;

    // 3. Item gaps: expand from 3px up to 12px
    const addedItemGap = Math.min(9, itemBudget / numItems);
    const itemGap = Math.round((3 + addedItemGap) * 10) / 10;

    // 4. Bullet gaps and line height
    const addedBulletGap = Math.min(3.5, bulletBudget / numBullets);
    const bulletGap = Math.round((1 + addedBulletGap) * 10) / 10;
    
    // Line height scaling: from 1.28 up to 1.45
    const lineGrowthRatio = Math.min(0.18, availableDelta / 900);
    const bodyLineHeight = (1.28 + lineGrowthRatio).toFixed(2);
    const bulletLineHeight = (1.26 + lineGrowthRatio).toFixed(2);

    // 5. Header margin: expand from 6px up to 16px
    const headerMarginBottom = Math.min(16, Math.round(6 + availableDelta * 0.04));

    // 6. Font size gentle scaling if resume is very short (e.g. only 1 experience or 2 projects)
    let bodyFontSize = "9.8px";
    let headingFontSize = "11px";
    let nameFontSize = "19px";
    if (availableDelta > 200 && numBullets < 10) {
      bodyFontSize = "10.5px";
      headingFontSize = "12px";
      nameFontSize = "21px";
    } else if (availableDelta > 100) {
      bodyFontSize = "10.0px";
      headingFontSize = "11.5px";
      nameFontSize = "20px";
    }

    computedVars = {
      "--page-padding-y": `${pagePaddingY}px`,
      "--page-padding-x": "50px",
      "--section-gap": `${sectionGap}px`,
      "--section-title-margin-bottom": `${sectionTitleMarginBottom}px`,
      "--item-gap": `${itemGap}px`,
      "--bullet-gap": `${bulletGap}px`,
      "--bullet-line-height": bulletLineHeight,
      "--body-line-height": bodyLineHeight,
      "--body-font-size": bodyFontSize,
      "--heading-font-size": headingFontSize,
      "--name-font-size": nameFontSize,
      "--header-margin-bottom": `${headerMarginBottom}px`
    };

    utilizationPct = Math.min(100, Math.round((rawHeight / targetHeight) * 100));

  } else if (availableDelta >= 0) {
    // -------------------------------------------------------------------------
    // SCENARIO 2: OPTIMAL NATURAL FIT (0 to 30px remaining)
    // Content naturally fills 97-100% of the page!
    // -------------------------------------------------------------------------
    fitStatus = "balanced";
    const microSec = Math.round((5 + availableDelta / numSections) * 10) / 10;
    computedVars = {
      "--page-padding-y": "20px",
      "--page-padding-x": "48px",
      "--section-gap": `${microSec}px`,
      "--section-title-margin-bottom": "2.5px",
      "--item-gap": "3.5px",
      "--bullet-gap": "1.2px",
      "--bullet-line-height": "1.28",
      "--body-line-height": "1.30",
      "--body-font-size": "9.8px",
      "--heading-font-size": "11px",
      "--name-font-size": "19px",
      "--header-margin-bottom": "7px"
    };
    utilizationPct = 100;

  } else {
    // -------------------------------------------------------------------------
    // SCENARIO 3: OVERFLOW (availableDelta < 0)
    // Content exceeds A4 page: Intelligently compact spacing first!
    // -------------------------------------------------------------------------
    const overAmount = Math.abs(availableDelta);

    if (overAmount <= 240) {
      // Mild to medium overflow: Can be fully absorbed by intelligent micro-compacting!
      fitStatus = "compacted";
      computedVars = {
        "--page-padding-y": "12px",
        "--page-padding-x": "42px",
        "--section-gap": "2.2px",
        "--section-title-margin-bottom": "1.0px",
        "--item-gap": "1.6px",
        "--bullet-gap": "0.3px",
        "--bullet-line-height": "1.18",
        "--body-line-height": "1.20",
        "--body-font-size": "9.0px",
        "--heading-font-size": "10.0px",
        "--name-font-size": "16.5px",
        "--header-margin-bottom": "3px"
      };
    } else {
      // Significant overflow: Apply minimum safe readable compaction and flag overflow
      fitStatus = "overflow";
      isOverflowing = true;
      overflowPx = Math.round(overAmount);
      computedVars = {
        "--page-padding-y": "12px",
        "--page-padding-x": "42px",
        "--section-gap": "3px",
        "--section-title-margin-bottom": "1px",
        "--item-gap": "1.8px",
        "--bullet-gap": "0.4px",
        "--bullet-line-height": "1.18",
        "--body-line-height": "1.20",
        "--body-font-size": "9.0px",
        "--heading-font-size": "9.8px",
        "--name-font-size": "16.5px",
        "--header-margin-bottom": "4px"
      };
    }
  }

  // Apply the computed CSS custom properties to the container
  Object.entries(computedVars).forEach(([key, val]) => {
    container.style.setProperty(key, val);
  });

  // Second pass: measure final rendered height after styles applied
  const prevMinH = container.style.minHeight;
  container.style.minHeight = "0px";
  const finalHeight = container.scrollHeight;
  container.style.minHeight = prevMinH || "";
  // Safe A4 tolerance for browser subpixel font antialiasing (up to 35px)
  const finalOverflow = finalHeight > (targetHeight + 35);
  const finalUtilization = Math.min(100, Math.round((finalHeight / targetHeight) * 100));

  return {
    cssVars: computedVars,
    isOverflowing: finalOverflow,
    overflowPx: finalOverflow ? Math.round(finalHeight - targetHeight) : 0,
    measuredHeight: finalHeight,
    rawHeight,
    utilizationPct: finalUtilization,
    fitStatus: finalOverflow ? "overflow" : fitStatus
  };
  } catch (err) {
    console.warn("computeSinglePageLayout safe fallback on error:", err);
    return defaultLayout;
  }
}

/**
 * Calculates page breaks and spacing optimization for Multi-Page Resume (Resume 1).
 * Prevents orphaned section headings and project/experience titles near page edges.
 *
 * @param {HTMLElement} paper - The multi-page resume DOM element.
 * @param {number} pageHeight - Standard A4 height in pixels (default 1120px).
 * @returns {Object} Page break guides and estimated page count.
 */
export function computeMultiPageLayout(paper, pageHeight = 1120) {
  if (!paper) {
    return { estimatedPages: 1, pageBreaks: [], pageCount: 1 };
  }

  // Remove previous page break markers
  paper.querySelectorAll(".page-break-target").forEach((el) => {
    el.classList.remove("page-break-target");
  });

  const scrollH = paper.scrollHeight;
  const count = Math.max(1, Math.ceil(scrollH / pageHeight));

  if (count <= 1) {
    return { estimatedPages: 1, pageBreaks: [], pageCount: 1 };
  }

  const paperRect = paper.getBoundingClientRect();
  const pageThreshold = 1050; // Points before bottom margin where break should occur
  const BREAK_GAP = 54;

  const candidates = Array.from(
    paper.querySelectorAll(
      ".resume-paper-block, .resume-sec-title, .resume-exp-item, .resume-proj-item, .resume-edu-item"
    )
  );

  const breaks = [];
  let accumulatedShift = 0;

  for (let p = 1; p < count; p++) {
    const currentThreshold = (p - 1) * pageHeight + pageThreshold + accumulatedShift;
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
      // 1. Prevent Orphaned Section Titles:
      if (targetEl.classList.contains("resume-sec-title")) {
        const parentBlock = targetEl.closest(".resume-paper-block");
        if (parentBlock) targetEl = parentBlock;
      }

      // 2. Prevent Orphaned Experience / Project Titles & Bullets:
      if (targetEl.tagName.toLowerCase() === "li") {
        const parentBlock = targetEl.closest(".resume-exp-item, .resume-proj-item");
        if (parentBlock) {
          targetEl = parentBlock;
        }
      }

      targetEl.classList.add("page-break-target");
      accumulatedShift += BREAK_GAP;

      const currentPaperRect = paper.getBoundingClientRect();
      const elRelTop = targetEl.getBoundingClientRect().top - currentPaperRect.top;
      const guideTop = Math.round(elRelTop - BREAK_GAP / 2);
      breaks.push({
        page: p,
        top: guideTop,
        label: `✂ Page ${p} End / Page ${p + 1} Start`
      });
    } else {
      breaks.push({
        page: p,
        top: Math.round(p * pageHeight + accumulatedShift),
        label: `✂ Page ${p} End / Page ${p + 1} Start`
      });
    }
  }

  return {
    estimatedPages: count,
    pageBreaks: breaks,
    pageCount: count
  };
}

/**
 * Normalizes any education object (even if degree and college fields were swapped during parsing)
 * into a standard 2-line executive layout matching Image 2:
 * Line 1: [Institution — Location] on Left, [Year/Duration] on Right
 * Line 2: [Degree - Score]
 */
export function formatEducationItem(edu) {
  if (!edu) {
    return {
      instLine: "",
      year: "",
      degreeLine: ""
    };
  }
  if (typeof edu !== "object") {
    return {
      instLine: String(edu || "").trim(),
      year: "",
      degreeLine: ""
    };
  }

  try {
    let rawInst = String(edu.institution || edu.university || edu.college || "").trim();
    let rawDeg = String(edu.degree || edu.degree_name || "").trim();
    let rawYear = String(edu.year || edu.duration || edu.graduation_year || "").trim();
    let rawScore = String(edu.score || edu.cgpa || edu.percentage || "").trim();
    let rawLoc = String(edu.location || "").trim();

    const isCollege = (s) => /college|university|polytechnic|institute|school|academy|vidyalaya/i.test(s);
    const isDegree = (s) => /bachelor|master|diploma|b\.e|btech|b\.tech|mtech|m\.tech|bca|mca|bsc|b\.sc|msc|m\.sc|phd|higher secondary|hsc|ssc|engineering in/i.test(s);

    // If rawDeg looks like college and rawInst looks like degree (or inverted), swap them
    if ((isCollege(rawDeg) && !isCollege(rawInst)) || (isDegree(rawInst) && !isDegree(rawDeg))) {
      const temp = rawDeg;
      rawDeg = rawInst;
      rawInst = temp;
    }

    // Extract year from rawInst if present
    const yearMatch = rawInst.match(/\b(20\d\d\s*[–—-—-]\s*20\d\d|20\d\d)\b/);
    if (yearMatch) {
      if (!rawYear) rawYear = yearMatch[1].replace(/\s+/g, "").replace("-", "–");
      rawInst = rawInst.replace(yearMatch[0], "").replace(/\s{2,}/g, " ").trim();
    }

    // Extract year from rawDeg if present
    const degYearMatch = rawDeg.match(/\b(20\d\d\s*[–—-—-]\s*20\d\d|20\d\d)\b/);
    if (degYearMatch) {
      if (!rawYear) rawYear = degYearMatch[1].replace(/\s+/g, "").replace("-", "–");
      rawDeg = rawDeg.replace(degYearMatch[0], "").replace(/\s{2,}/g, " ").trim();
    }

    rawInst = rawInst.replace(/[–—\-,\s]+$/, "").trim();

    if (rawLoc && !rawInst.toLowerCase().includes(rawLoc.toLowerCase())) {
      rawInst = `${rawInst} — ${rawLoc}`;
    }

    // Extract score from rawDeg if present
    const scoreMatch = rawDeg.match(/\b(?:CGPA[:\s]*)?(\d{1,2}(?:\.\d{1,2})?(?:%|\s*CGPA)?)\s*$/i);
    if (scoreMatch && !rawScore) {
      rawScore = scoreMatch[1];
      rawDeg = rawDeg.slice(0, scoreMatch.index).trim();
    }

    rawDeg = rawDeg.replace(/[–—\-,\s]+$/, "").trim();
    rawYear = rawYear.replace(/[()]/g, "").trim();
    rawScore = rawScore.replace(/^Score[:\s]*/i, "").trim();

    let degreeLine = rawDeg;
    if (rawScore) {
      if (!degreeLine.includes(rawScore)) {
        degreeLine = `${degreeLine} - ${rawScore}`;
      }
    }

    return {
      instLine: rawInst,
      year: rawYear,
      degreeLine: degreeLine
    };
  } catch (err) {
    console.error("formatEducationItem safe fallback:", err);
    return {
      instLine: String(edu.institution || edu.university || edu.college || ""),
      year: String(edu.year || edu.duration || ""),
      degreeLine: String(edu.degree || "")
    };
  }
}

/**
 */
export function cleanBulletText(text) {
  if (!text) return "";
  let s = String(text).replace(/[\r\n]+/g, " ").trim();
  // Replace internal multiple dots/ellipses ('...', '..', '…') with a single '.'
  s = s.replace(/(\.{2,}|…)+/g, ".").trim();
  // Clean accidental ',.' or ';.' or ':.' artifacts
  s = s.replace(/[,;:\-–—\s]+\.+$/g, "").trim();
  // Strip trailing punctuation/periods before checking dangling words
  s = s.replace(/[.,;:\-–—\s]+$/g, "").trim();
  // Strip dangling prepositions or conjunctions left by broken truncations (e.g. 'and', 'with', 'from', 'to')
  s = s.replace(/\s+\b(and|or|with|to|from|via|by|in|for|of|the|a|an)\s*$/i, "").trim();
  // Strip any trailing punctuation or whitespace and guarantee exactly one period
  s = s.replace(/[.,;:\-–—\s]+$/g, "").trim();
  if (s) {
    s += ".";
  }
  return s;
}
