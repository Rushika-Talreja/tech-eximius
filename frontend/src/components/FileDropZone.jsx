import React, { useState } from 'react';

/**
 * FileDropZone component.
 * High-density industrial upload target for Solidity smart contracts.
 * Strictly adheres to text-only affordances with zero icons or emojis.
 */
export function FileDropZone({ onFileSelect, onCodePaste }) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedFileName, setSelectedFileName] = useState('YieldVault.sol');
  const [fileSizeStr, setFileSizeStr] = useState('3.8 KB');

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setSelectedFileName(file.name);
      setFileSizeStr(`${(file.size / 1024).toFixed(1)} KB`);
      const reader = new FileReader();
      reader.onload = (event) => {
        if (onFileSelect) onFileSelect(event.target.result, file.name);
      };
      reader.readAsText(file);
    }
  };

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFileName(file.name);
      setFileSizeStr(`${(file.size / 1024).toFixed(1)} KB`);
      const reader = new FileReader();
      reader.onload = (event) => {
        if (onFileSelect) onFileSelect(event.target.result, file.name);
      };
      reader.readAsText(file);
    }
  };

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`border border-dashed p-6 transition-colors bg-[#1D1916] flex flex-col items-center justify-center gap-3 text-center ${
        isDragOver
          ? 'border-primary bg-[#26211D]'
          : 'border-[#3A332D] hover:border-primary'
      }`}
    >
      <div className="font-label-caps text-xs text-primary font-bold tracking-wider uppercase">
        {isDragOver ? '[ Drop Solidity File Now ]' : '[ Ingestion Interface ]'}
      </div>

      <div className="font-headline-sm text-sm text-on-surface">
        Select Solidity File (.sol) or Drag & Drop Contract Archive
      </div>

      <p className="font-code-sm text-xs text-on-surface-variant max-w-md">
        Accepts raw Solidity source (.sol), flattened verification bundles, or Standard JSON input artifacts.
      </p>

      <div className="flex items-center gap-2 mt-2">
        <label className="cursor-pointer bg-primary-container text-on-primary-container font-label-caps text-xs px-4 py-2 hover:bg-primary hover:text-[#14110F] transition-colors font-bold uppercase">
          [ Browse Files ]
          <input
            type="file"
            accept=".sol,.zip,.json"
            onChange={handleFileInput}
            className="hidden"
          />
        </label>
        <span className="font-code-sm text-xs text-outline">or paste directly into code pane</span>
      </div>

      {selectedFileName && (
        <div className="mt-2 px-3 py-1 bg-[#161311] border border-[#3A332D] flex items-center gap-4 text-xs font-code-md">
          <span className="text-outline">Active Intake:</span>
          <span className="text-primary font-semibold">{selectedFileName}</span>
          <span className="text-on-surface-variant">Size: {fileSizeStr}</span>
          <span className="text-primary font-bold">[ Ready for Analysis ]</span>
        </div>
      )}
    </div>
  );
}

