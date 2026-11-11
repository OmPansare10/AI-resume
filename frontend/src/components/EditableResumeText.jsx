import { useLayoutEffect, useRef } from "react";

/**
 * Renders an isolated leaf text container whose DOM children are managed outside
 * React's text reconciliation so inline font-size/font-family spans never
 * conflict with React Fiber updates or cause NotFoundError crashes.
 */
export function EditableResumeText({
  as = "span",
  value = "",
  editable = false,
  onCommit,
  className = "",
  title = "",
  style,
}) {
  const Tag = as;
  const elRef = useRef(null);
  const lastValueRef = useRef(undefined);
  const textValue = value == null ? "" : String(value);

  useLayoutEffect(() => {
    const el = elRef.current;
    if (!el) return;

    const isInitialMount = lastValueRef.current === undefined;
    const externalValueChanged = lastValueRef.current !== textValue;

    if (isInitialMount || (externalValueChanged && el.textContent !== textValue)) {
      el.textContent = textValue;
    }
    lastValueRef.current = textValue;
  }, [textValue]);

  const handleBlur = (e) => {
    if (!editable || !onCommit) return;
    const nextText = e.currentTarget.textContent ?? "";
    if (nextText !== lastValueRef.current) {
      lastValueRef.current = nextText;
      onCommit(nextText);
    }
  };

  return (
    <Tag
      ref={elRef}
      className={className}
      contentEditable={editable ? true : undefined}
      suppressContentEditableWarning={editable ? true : undefined}
      onBlur={editable ? handleBlur : undefined}
      title={title}
      style={style}
    />
  );
}
