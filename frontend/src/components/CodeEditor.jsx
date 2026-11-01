import React, { useEffect, useRef } from 'react';
import { warmMonacoTheme, WARM_MONACO_THEME_NAME } from '../theme/monacoWarmTheme.js';

/**
 * CodeEditor component.
 * Integrates Monaco Editor configured strictly with the Warm Obsidian Security theme.
 * Zero cold hues, warm charcoal background, amber keywords, warm red diagnostics.
 */
export function CodeEditor({
  value,
  onChange,
  language = 'sol',
  readOnly = false,
  height = '480px',
  filename = 'YieldVault.sol'
}) {
  const containerRef = useRef(null);
  const editorInstanceRef = useRef(null);

  useEffect(() => {
    let editor = null;

    const initEditor = () => {
      if (window.monaco && containerRef.current) {
        // Register warm theme
        window.monaco.editor.defineTheme(WARM_MONACO_THEME_NAME, warmMonacoTheme);
        window.monaco.editor.setTheme(WARM_MONACO_THEME_NAME);

        editor = window.monaco.editor.create(containerRef.current, {
          value: value || '',
          language: language === 'sol' ? 'solidity' : language,
          theme: WARM_MONACO_THEME_NAME,
          readOnly: readOnly,
          minimap: { enabled: false },
          lineNumbers: 'on',
          scrollBeyondLastLine: false,
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 13,
          lineHeight: 20,
          renderLineHighlight: 'all',
          automaticLayout: true,
          tabSize: 4
        });

        editorInstanceRef.current = editor;

        editor.onDidChangeModelContent(() => {
          if (onChange) {
            onChange(editor.getValue());
          }
        });
      }
    };

    if (window.monaco) {
      initEditor();
    } else {
      // Poll or wait for Monaco script if loading asynchronously
      const interval = setInterval(() => {
        if (window.monaco) {
          clearInterval(interval);
          initEditor();
        }
      }, 100);

      const timeout = setTimeout(() => {
        clearInterval(interval);
      }, 4000);

      return () => {
        clearInterval(interval);
        clearTimeout(timeout);
        if (editor) editor.dispose();
      };
    }

    return () => {
      if (editor) editor.dispose();
    };
  }, []);

  // Update editor value if changed externally
  useEffect(() => {
    if (editorInstanceRef.current && value !== undefined) {
      if (editorInstanceRef.current.getValue() !== value) {
        editorInstanceRef.current.setValue(value);
      }
    }
  }, [value]);

  return (
    <div className="flex flex-col border border-[#3A332D] bg-[#161311] w-full">
      {/* Editor Sub-header bar */}
      <div className="h-8 px-3 bg-[#1D1916] border-b border-[#3A332D] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-label-caps text-[10px] text-primary uppercase font-bold">
            [Solidity Source]
          </span>
          <span className="font-code-sm text-xs text-on-surface">{filename}</span>
        </div>
        <div className="flex items-center gap-3 text-[10px] font-code-sm text-on-surface-variant">
          <span>Encoding: UTF-8</span>
          <span>Tab Size: 4</span>
          <span className="text-primary font-bold">{readOnly ? 'MODE: INSPECT' : 'MODE: EDIT'}</span>
        </div>
      </div>

      {/* Monaco Container */}
      <div
        ref={containerRef}
        style={{ height }}
        className="w-full relative focus:outline-none"
      >
        {/* Fallback textarea if Monaco has not mounted yet */}
        <noscript>
          <textarea
            readOnly={readOnly}
            value={value}
            onChange={(e) => onChange && onChange(e.target.value)}
            className="w-full h-full bg-[#161311] text-[#F2EBE3] font-mono text-xs p-3 focus:outline-none"
          />
        </noscript>
      </div>
    </div>
  );
}

