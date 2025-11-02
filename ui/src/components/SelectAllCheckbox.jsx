import { useRef, useEffect } from "react";

export default function SelectAllCheckbox({ selectedFiles, files, onChange }) {
  const checkboxRef = useRef(null); // ✅ no TS generics in JSX

  const isIndeterminate =
    selectedFiles.size > 0 && selectedFiles.size < files.length;

  useEffect(() => {
    if (checkboxRef.current) {
      checkboxRef.current.indeterminate = isIndeterminate;
    }
  }, [isIndeterminate]);

  return (
    <input
      ref={checkboxRef}
      type="checkbox"
      checked={files.length > 0 && selectedFiles.size === files.length}
      onChange={onChange}
      className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
    />
  );
}
