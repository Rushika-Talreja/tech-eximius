/**
 * Warm Obsidian Security Engine - Monaco Custom Theme
 * Strictly enforces warm colors: amber, warm charcoal, warm red, warm olive.
 * Cold hues strictly excluded.
 */

export const WARM_MONACO_THEME_NAME = 'warm-obsidian-security';

export const warmMonacoTheme = {
  base: 'vs-dark',
  inherit: false,
  rules: [
    { token: '', foreground: 'F2EBE3', background: '161311' },
    { token: 'comment', foreground: 'A89E93', fontStyle: 'italic' },
    { token: 'keyword', foreground: 'FFBB49', fontStyle: 'bold' },
    { token: 'keyword.control', foreground: 'E0A030' },
    { token: 'identifier', foreground: 'F2EBE3' },
    { token: 'type', foreground: 'FEBA49', fontStyle: 'bold' },
    { token: 'string', foreground: '8FA84A' },
    { token: 'number', foreground: 'E8782A' },
    { token: 'delimiter', foreground: 'D5C4AF' },
    { token: 'delimiter.bracket', foreground: 'E0A030' },
    { token: 'operator', foreground: 'E0A030' },
    { token: 'constant', foreground: 'E8782A' },
    { token: 'function', foreground: 'F2EBE3', fontStyle: 'bold' },
    { token: 'variable', foreground: 'F2EBE3' },
    { token: 'invalid', foreground: 'D6403A', fontStyle: 'underline' }
  ],
  colors: {
    'editor.background': '#161311',
    'editor.foreground': '#F2EBE3',
    'editorCursor.foreground': '#FFBB49',
    'editor.lineHighlightBackground': '#221F1D',
    'editor.selectionBackground': '#3A332D',
    'editor.selectionHighlightBackground': '#2D2927',
    'editorLineNumber.foreground': '#514535',
    'editorLineNumber.activeForeground': '#E0A030',
    'editorGutter.background': '#14110F',
    'editorWidget.background': '#1D1916',
    'editorWidget.border': '#3A332D',
    'editorOverviewRuler.border': '#3A332D',
    'scrollbarSlider.background': '#3A332D80',
    'scrollbarSlider.hoverBackground': '#514535',
    'scrollbarSlider.activeBackground': '#E0A03080',
    'editorIndentGuide.background': '#2D2927',
    'editorIndentGuide.activeBackground': '#514535',
    'editorBracketMatch.background': '#3A332D',
    'editorBracketMatch.border': '#E0A030',
    'input.background': '#1D1916',
    'input.foreground': '#F2EBE3',
    'input.border': '#3A332D',
    'focusBorder': '#E0A030'
  }
};
