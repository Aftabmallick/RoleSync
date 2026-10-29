import React from 'react';

interface PdfPreviewProps {
  pdfBase64: string;
  onDownload?: () => void;
}

export const PdfPreview: React.FC<PdfPreviewProps> = ({ pdfBase64, onDownload }) => {
  const dataUri = `data:application/pdf;base64,${pdfBase64}`;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
          Typst Vector PDF (1-Page Budgeted)
        </span>
        {onDownload && (
          <button
            onClick={onDownload}
            className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition-colors"
          >
            Download PDF ↓
          </button>
        )}
      </div>

      <div className="w-full h-80 rounded-lg overflow-hidden border border-slate-200 bg-slate-100 flex items-center justify-center">
        <iframe
          src={`${dataUri}#toolbar=0&navpanes=0`}
          title="Resume PDF Preview"
          className="w-full h-full border-0"
        />
      </div>
    </div>
  );
};
