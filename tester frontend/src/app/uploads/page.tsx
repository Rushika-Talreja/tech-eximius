"use client";

import React, { useState } from "react";
import { executeApiRequest } from "../../lib/api";
import { useConsole } from "../../lib/store";
import { ErrorDisplay } from "../../components/ErrorDisplay";
import { RawJsonViewer } from "../../components/RawJsonViewer";
import { UploadResult } from "../../types/backend";

// Function to construct a minimal raw zip archive containing path traversal
function createTraversalZip(): Blob {
  const filename = "../../evil.sol";
  const fileData = new TextEncoder().encode("// evil injected contract\ncontract Evil {}");
  const filenameBytes = new TextEncoder().encode(filename);

  // Local File Header
  const lfh = new Uint8Array(30 + filenameBytes.length + fileData.length);
  const lfhView = new DataView(lfh.buffer);
  lfhView.setUint32(0, 0x04034b50, true); // signature
  lfhView.setUint16(4, 20, true);         // version needed
  lfhView.setUint16(6, 0, true);          // flags
  lfhView.setUint16(8, 0, true);          // compression (store)
  lfhView.setUint32(18, fileData.length, true); // compressed size
  lfhView.setUint32(22, fileData.length, true); // uncompressed size
  lfhView.setUint16(26, filenameBytes.length, true); // filename len
  lfhView.setUint16(28, 0, true);         // extra len
  lfh.set(filenameBytes, 30);
  lfh.set(fileData, 30 + filenameBytes.length);

  // Central Directory File Header
  const cdfh = new Uint8Array(46 + filenameBytes.length);
  const cdfhView = new DataView(cdfh.buffer);
  cdfhView.setUint32(0, 0x02014b50, true); // signature
  cdfhView.setUint16(4, 20, true);         // version made by
  cdfhView.setUint16(6, 20, true);         // version needed
  cdfhView.setUint16(10, 0, true);         // compression
  cdfhView.setUint32(20, fileData.length, true);
  cdfhView.setUint32(24, fileData.length, true);
  cdfhView.setUint16(28, filenameBytes.length, true);
  cdfh.set(filenameBytes, 46);

  // End of Central Directory Record
  const eocd = new Uint8Array(22);
  const eocdView = new DataView(eocd.buffer);
  eocdView.setUint32(0, 0x06054b50, true);
  eocdView.setUint16(8, 1, true); // records in central dir on this disk
  eocdView.setUint16(10, 1, true); // total records in central dir
  eocdView.setUint32(12, cdfh.length, true); // size of central dir
  eocdView.setUint32(16, lfh.length, true);  // offset of central dir

  return new Blob([lfh, cdfh, eocd], { type: "application/zip" });
}

export default function UploadsPage() {
  const { authMode, apiKey, addLogEntry } = useConsole();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<any>(null);

  // Upload runner
  const performUpload = async (fileObj: File | Blob, filename: string) => {
    setLoading(true);
    setError(null);
    setUploadResult(null);

    const formData = new FormData();
    formData.append("file", fileObj, filename);

    try {
      const res = await executeApiRequest<UploadResult>("/uploads", {
        method: "POST",
        body: formData,
        authMode,
        apiKey,
        onLog: addLogEntry,
      });
      setUploadResult(res.data);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCustomUpload = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;
    performUpload(selectedFile, selectedFile.name);
  };

  const handleTraversalZipTest = () => {
    const blob = createTraversalZip();
    performUpload(blob, "traversal_attack.zip");
  };

  const handleOversizedTest = () => {
    // 11 MB file exceeds 10 MB limit
    const oversizedBytes = new Uint8Array(11 * 1024 * 1024);
    const blob = new Blob([oversizedBytes], { type: "text/plain" });
    performUpload(blob, "oversized_contract.sol");
  };

  return (
    <div>
      <h2>Contract Uploads</h2>
      <p style={{ color: "#666", fontSize: "14px" }}>
        Exercise <code>POST /uploads</code> with valid Solidity/zip files, plus built-in security guardrail negative tests.
      </p>

      {/* Manual File Picker */}
      <div style={{ border: "1px solid #ddd", padding: "16px", borderRadius: "4px", backgroundColor: "#fafafa", marginBottom: "20px" }}>
        <h3 style={{ margin: "0 0 12px 0" }}>Standard Upload (.sol or .zip)</h3>
        <form onSubmit={handleCustomUpload} style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <input
            type="file"
            accept=".sol,.zip"
            onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
          />
          <button
            type="submit"
            disabled={!selectedFile || loading}
            style={{
              padding: "6px 14px",
              backgroundColor: "#27ae60",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              cursor: selectedFile && !loading ? "pointer" : "not-allowed",
            }}
          >
            {loading ? "Uploading..." : "Upload File"}
          </button>
        </form>
      </div>

      {/* Negative Testing Buttons */}
      <div style={{ border: "1px solid #f5b7b1", padding: "16px", borderRadius: "4px", backgroundColor: "#fdf2e9", marginBottom: "20px" }}>
        <h3 style={{ margin: "0 0 8px 0", color: "#b9770e" }}>Security & Validation Guardrails (Negative Tests)</h3>
        <p style={{ margin: "0 0 12px 0", fontSize: "12px", color: "#666" }}>
          Verify that malicious or non-compliant uploads are rejected with proper HTTP error codes.
        </p>

        <div style={{ display: "flex", gap: "12px" }}>
          <button
            onClick={handleTraversalZipTest}
            disabled={loading}
            style={{
              padding: "8px 14px",
              backgroundColor: "#c0392b",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              fontWeight: "bold",
              cursor: "pointer",
            }}
          >
            Test Path Traversal Zip (Expect 422)
          </button>

          <button
            onClick={handleOversizedTest}
            disabled={loading}
            style={{
              padding: "8px 14px",
              backgroundColor: "#d35400",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              fontWeight: "bold",
              cursor: "pointer",
            }}
          >
            Test Oversized Upload 11MB (Expect 413)
          </button>
        </div>
      </div>

      {/* Results / Error display */}
      <ErrorDisplay error={error} />

      {uploadResult && (
        <div style={{ border: "1px solid #27ae60", padding: "16px", borderRadius: "4px", backgroundColor: "#eafaf1" }}>
          <h4 style={{ margin: "0 0 8px 0", color: "#27ae60" }}>Upload Successful</h4>
          <div style={{ fontFamily: "monospace", fontSize: "13px" }}>
            <div>Upload ID: <strong>{uploadResult.upload_id}</strong></div>
            <div>File Kind: <strong>{uploadResult.kind}</strong></div>
            <div>Size: <strong>{uploadResult.size_bytes} bytes</strong></div>
            <div>SHA256: <code>{uploadResult.sha256}</code></div>
            <div>Expires At: <strong>{uploadResult.expires_at}</strong></div>
          </div>
          <div style={{ marginTop: "10px" }}>
            <button
              onClick={() => {
                navigator.clipboard.writeText(uploadResult.upload_id);
                alert("Upload ID copied to clipboard!");
              }}
              style={{ padding: "4px 8px", fontSize: "12px", cursor: "pointer" }}
            >
              Copy Upload ID for Audit Creation
            </button>
          </div>
        </div>
      )}

      <RawJsonViewer data={uploadResult} title="Raw Upload Result JSON" />
    </div>
  );
}

