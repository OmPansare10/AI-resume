const IGNORED_SELECTION_SELECTOR =
  ".btn-delete-bullet, .proj-remove-photo-pill, .proj-zoom-pill, .page-boundary-guide";

const isIgnoredTextNode = (node) => {
  const parent = node?.parentElement;
  return Boolean(parent && parent.closest(IGNORED_SELECTION_SELECTOR));
};

/**
 * Resolves which resume container ("multi" | "single") contains the given DOM node.
 */
export function findResumeTargetForNode(node, multiRef, singleRef, preferredMode = null) {
  if (!node) return null;
  const multiEl = multiRef?.current;
  const singleEl = singleRef?.current;

  if (preferredMode === "single" && singleEl && singleEl.contains(node)) {
    return { mode: "single", container: singleEl };
  }
  if (preferredMode === "multi" && multiEl && multiEl.contains(node)) {
    return { mode: "multi", container: multiEl };
  }
  if (singleEl && singleEl.contains(node)) {
    return { mode: "single", container: singleEl };
  }
  if (multiEl && multiEl.contains(node)) {
    return { mode: "multi", container: multiEl };
  }
  return null;
}

/**
 * Checks whether a DOM Range is non-empty, connected, and entirely within container.
 */
export function isRangeInsideContainer(range, container) {
  if (!range || range.collapsed || !container) return false;
  if (!range.startContainer?.isConnected || !range.endContainer?.isConnected) return false;
  if (!container.contains(range.commonAncestorContainer)) return false;
  return range.toString().trim().length > 0;
}

/**
 * Returns a valid non-collapsed Range either from the live Selection or the last
 * saved selection for that resume preview (e.g. after focus shifted to a dropdown).
 */
export function resolveActiveResumeSelection({
  multiRef,
  singleRef,
  savedSelectionsRef,
  preferredMode = null,
}) {
  const allowedModes =
    preferredMode === "single"
      ? ["single"]
      : preferredMode === "multi"
      ? ["multi"]
      : ["multi", "single"];

  const sel = window.getSelection();
  if (sel && sel.rangeCount > 0) {
    const liveRange = sel.getRangeAt(0);
    const liveTarget = findResumeTargetForNode(
      liveRange.commonAncestorContainer,
      multiRef,
      singleRef,
      preferredMode
    );
    if (
      liveTarget &&
      allowedModes.includes(liveTarget.mode) &&
      isRangeInsideContainer(liveRange, liveTarget.container)
    ) {
      return {
        selection: sel,
        range: liveRange,
        mode: liveTarget.mode,
        container: liveTarget.container,
      };
    }
  }

  for (const mode of allowedModes) {
    const savedRange = savedSelectionsRef?.current?.[mode];
    const container = mode === "single" ? singleRef?.current : multiRef?.current;
    if (isRangeInsideContainer(savedRange, container)) {
      return {
        selection: sel,
        range: savedRange.cloneRange(),
        mode,
        container,
      };
    }
  }

  return null;
}

/**
 * Collects exact [start, end] slices across Text nodes inside range without touching
 * sibling UI controls or moving React-owned Element nodes.
 */
export function collectTextSlicesInRange(range, container) {
  if (!range || range.collapsed || !container) return [];
  const root = range.commonAncestorContainer;

  if (root.nodeType === Node.TEXT_NODE) {
    if (isIgnoredTextNode(root)) return [];
    const len = root.nodeValue ? root.nodeValue.length : 0;
    const start = Math.max(0, Math.min(len, range.startOffset));
    const end = Math.max(start, Math.min(len, range.endOffset));
    return end > start && root.nodeValue.slice(start, end).length > 0
      ? [{ node: root, start, end }]
      : [];
  }

  const slices = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue || !node.nodeValue.length) return NodeFilter.FILTER_REJECT;
      if (isIgnoredTextNode(node)) return NodeFilter.FILTER_REJECT;
      if (!container.contains(node)) return NodeFilter.FILTER_REJECT;
      try {
        if (!range.intersectsNode(node)) return NodeFilter.FILTER_REJECT;
      } catch {
        return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });

  let current;
  while ((current = walker.nextNode())) {
    const len = current.nodeValue.length;
    let start = 0;
    let end = len;

    if (current === range.startContainer) {
      start = range.startOffset;
    } else if (range.comparePoint(current, len) === -1) {
      continue;
    }

    if (current === range.endContainer) {
      end = range.endOffset;
    } else if (range.comparePoint(current, 0) === 1) {
      continue;
    }

    start = Math.max(0, Math.min(len, start));
    end = Math.max(start, Math.min(len, end));
    if (end > start && current.nodeValue.slice(start, end).length > 0) {
      slices.push({ node: current, start, end });
    }
  }

  return slices;
}

const isFormattingSpan = (el) =>
  Boolean(
    el &&
      el.tagName === "SPAN" &&
      (el.classList.contains("selected-text-resize") ||
        el.classList.contains("selected-text-font"))
  );

function applyStyleToTextSlices(range, container, selection, buildStyleUpdate) {
  const slices = collectTextSlicesInRange(range, container);
  if (slices.length === 0) return null;

  const styledNodes = [];
  let lastMetric = null;

  for (const { node, start, end } of slices) {
    const parent = node.parentElement;
    if (!parent || !parent.isConnected) continue;

    const text = node.nodeValue || "";
    const computed = window.getComputedStyle(parent);
    const update = buildStyleUpdate(computed, parent);
    if (!update) continue;

    if (update.metric !== undefined && update.metric !== null) {
      lastMetric = update.metric;
    }

    const beforeText = text.slice(0, start);
    const selectedText = text.slice(start, end);
    const afterText = text.slice(end);
    const isFullNode = start === 0 && end === text.length;

    if (isFormattingSpan(parent) && parent.childNodes.length === 1) {
      if (isFullNode) {
        if (update.className) parent.classList.add(update.className);
        if (update.fontSize) parent.style.fontSize = update.fontSize;
        if (update.fontFamily !== undefined) {
          parent.style.fontFamily = update.fontFamily;
        }
        styledNodes.push(parent);
      } else {
        const replacement = document.createDocumentFragment();
        if (beforeText) {
          const beforeSpan = parent.cloneNode(false);
          beforeSpan.textContent = beforeText;
          replacement.appendChild(beforeSpan);
        }
        const midSpan = parent.cloneNode(false);
        if (update.className) midSpan.classList.add(update.className);
        if (update.fontSize) midSpan.style.fontSize = update.fontSize;
        if (update.fontFamily !== undefined) {
          midSpan.style.fontFamily = update.fontFamily;
        }
        midSpan.textContent = selectedText;
        replacement.appendChild(midSpan);
        styledNodes.push(midSpan);

        if (afterText) {
          const afterSpan = parent.cloneNode(false);
          afterSpan.textContent = afterText;
          replacement.appendChild(afterSpan);
        }
        parent.replaceWith(replacement);
      }
      continue;
    }

    const span = document.createElement("span");
    span.className = update.className || "selected-text-resize";
    if (update.fontSize) span.style.fontSize = update.fontSize;
    if (update.fontFamily !== undefined) {
      span.style.fontFamily = update.fontFamily;
    }
    span.textContent = selectedText;

    const replacement = document.createDocumentFragment();
    if (beforeText) replacement.appendChild(document.createTextNode(beforeText));
    replacement.appendChild(span);
    if (afterText) replacement.appendChild(document.createTextNode(afterText));

    parent.replaceChild(replacement, node);
    styledNodes.push(span);
  }

  if (styledNodes.length === 0) return null;

  let nextRange = null;
  const firstText = styledNodes[0].firstChild;
  const lastNode = styledNodes[styledNodes.length - 1];
  const lastText = lastNode.lastChild;
  if (selection && firstText && lastText) {
    nextRange = document.createRange();
    nextRange.setStart(firstText, 0);
    nextRange.setEnd(lastText, lastText.nodeValue ? lastText.nodeValue.length : 0);
    selection.removeAllRanges();
    selection.addRange(nextRange);
  }

  return { count: styledNodes.length, metric: lastMetric, nextRange };
}

/**
 * Safely scales font size only on highlighted text slices within container.
 */
export function applyFontSizeDeltaToRange(range, delta, container, selection) {
  return applyStyleToTextSlices(range, container, selection, (computed) => {
    const currentSize = parseFloat(computed.fontSize) || 12;
    const newSize = Math.max(8, Math.min(48, Math.round((currentSize + delta) * 10) / 10));
    return {
      className: "selected-text-resize",
      fontSize: `${newSize}px`,
      metric: newSize,
    };
  });
}

/**
 * Safely changes font family only on highlighted text slices within container.
 */
export function applyFontFamilyToRange(range, fontFamily, container, selection) {
  return applyStyleToTextSlices(range, container, selection, () => ({
    className: "selected-text-font",
    fontFamily,
    metric: fontFamily,
  }));
}
