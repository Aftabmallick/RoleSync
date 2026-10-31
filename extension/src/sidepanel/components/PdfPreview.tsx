import React, { useEffect, useRef, useState } from 'react';

interface PdfPreviewProps {
  pdfBase64: string;
  onDownload?: () => void;
  onAutoCondense?: () => void;
  allowMultiPage?: boolean;
  onToggleMultiPage?: (allowed: boolean) => void;
}

export const PdfPreview: React.FC<PdfPreviewProps> = ({
  pdfBase64,
  onDownload,
  onAutoCondense,
  allowMultiPage,
  onToggleMultiPage,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [renderError, setRenderError] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [numPages, setNumPages] = useState<number>(1);
  const [multiPageOverride, setMultiPageOverride] = useState<boolean>(allowMultiPage || false);

  useEffect(() => {
    let isCancelled = false;
    let createdUrl: string | null = null;

    async function renderPdfToCanvas() {
      setIsLoading(true);
      setRenderError(false);
      try {
        const rawBytes = atob(pdfBase64);
        const uint8Array = new Uint8Array(rawBytes.length);
        for (let i = 0; i < rawBytes.length; i++) {
          uint8Array[i] = rawBytes.charCodeAt(i);
        }

        // Create Blob URL for native view & download
        const blob = new Blob([uint8Array], { type: 'application/pdf' });
        createdUrl = URL.createObjectURL(blob);
        setBlobUrl(createdUrl);

        // Render PDF page to HTML5 Canvas via pdfjs-dist
        const pdfjsLib = await import('pdfjs-dist');
        if (!pdfjsLib.GlobalWorkerOptions.workerSrc) {
          try {
            const workerUrl = typeof chrome !== 'undefined' && chrome.runtime?.getURL
              ? chrome.runtime.getURL('dist/assets/pdf.worker.min.mjs')
              : '/dist/assets/pdf.worker.min.mjs';
            pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;
          } catch (e) {
            console.warn('[RoleSync UI] Failed to set workerSrc:', e);
          }
        }
        const loadingTask = pdfjsLib.getDocument({
          data: uint8Array,
          useSystemFonts: true,
          isEvalSupported: false
        });

        const pdf = await loadingTask.promise;
        if (isCancelled) return;
        setNumPages(pdf.numPages);

        const page = await pdf.getPage(1);
        if (isCancelled) return;

        const canvas = canvasRef.current;
        if (!canvas) return;

        const context = canvas.getContext('2d');
        if (!context) return;

        const containerWidth = canvas.parentElement?.clientWidth || 320;
        const unscaledViewport = page.getViewport({ scale: 1 });
        const scale = containerWidth / unscaledViewport.width;
        const viewport = page.getViewport({ scale });

        canvas.height = viewport.height;
        canvas.width = viewport.width;

        const renderContext = {
          canvasContext: context,
          viewport: viewport,
        };

        await page.render(renderContext).promise;
        if (!isCancelled) {
          setIsLoading(false);
        }
      } catch (err) {
        console.warn('[RoleSync UI] Canvas render failed, showing native download view:', err);
        if (!isCancelled) {
          setRenderError(true);
          setIsLoading(false);
        }
      }
    }

    if (pdfBase64) {
      renderPdfToCanvas();
    }

    return () => {
      isCancelled = true;
      if (createdUrl) {
        URL.revokeObjectURL(createdUrl);
      }
    };
  }, [pdfBase64]);

  const handleOpenInNewTab = () => {
    if (blobUrl) {
      window.open(blobUrl, '_blank');
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">
            Typst Vector PDF
          </span>
          <span
            className={`text-[10px] px-1.5 py-0.5 rounded font-semibold border ${
              numPages > 1 && !multiPageOverride
                ? 'bg-amber-50 text-amber-800 border-amber-200'
                : 'bg-indigo-50 text-indigo-700 border-indigo-100'
            }`}
          >
            {numPages > 1 && !multiPageOverride
              ? `${numPages} Pages (Budget Exceeded)`
              : numPages > 1
              ? `${numPages} Pages (Override Active)`
              : '1-Page Budgeted'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {blobUrl && (
            <button
              onClick={() => setIsFullscreen(true)}
              className="text-xs font-semibold text-slate-600 hover:text-indigo-600 transition-colors"
              title="Inspect Fullscreen Lightbox"
            >
              🔍 Inspect
            </button>
          )}
          <button
            onClick={handleOpenInNewTab}
            className="text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
            title="Open in new browser tab"
          >
            Tab ↗
          </button>
          {onDownload && (
            <button
              onClick={onDownload}
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 transition-colors"
            >
              Download PDF ↓
            </button>
          )}
        </div>
      </div>

      {/* Amber Overflow Banner (Page Budget Exceeded) */}
      {numPages > 1 && !multiPageOverride && (
        <div className="p-3 bg-amber-50 border border-amber-300 rounded-xl flex flex-col gap-2 text-xs text-amber-900 shadow-xs animate-in fade-in">
          <div className="flex items-center gap-1.5 font-bold text-amber-950">
            <span className="text-sm">⚠️</span>
            <span>Page Budget Exceeded: {numPages}.00 Pages Detected (ATS Overflow Hazard)</span>
          </div>
          <p className="text-[11px] text-amber-800 leading-relaxed">
            Your detailed career history exceeds single-page density. Single-page resumes receive 38% higher recruiter response rates and pass ATS length filters.
          </p>
          <div className="flex items-center gap-2 pt-1">
            <button
              type="button"
              onClick={() => {
                if (onAutoCondense) onAutoCondense();
              }}
              className="px-2.5 py-1.5 bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs rounded-lg shadow-xs transition-colors flex items-center gap-1 cursor-pointer"
            >
              <span>✨ Auto-Condense (Smart Prune)</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setMultiPageOverride(true);
                if (onToggleMultiPage) onToggleMultiPage(true);
              }}
              className="px-2.5 py-1.5 bg-white border border-amber-300 hover:bg-amber-100 text-amber-900 font-semibold text-xs rounded-lg shadow-xs transition-colors cursor-pointer"
            >
              📄 Allow Multi-Page Resume ({numPages} Pages)
            </button>
          </div>
        </div>
      )}

      <div className="w-full min-h-[340px] max-h-[480px] rounded-lg overflow-y-auto border border-slate-200 bg-slate-100 flex items-center justify-center relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-50/80 z-10 text-xs text-slate-500 font-medium">
            Rendering vector PDF preview...
          </div>
        )}
        {!renderError ? (
          <canvas ref={canvasRef} className="w-full h-auto shadow-sm" />
        ) : (
          <div className="p-6 text-center flex flex-col items-center justify-center gap-2">
            <span className="text-2xl">📄</span>
            <span className="text-xs font-bold text-slate-800">Vector PDF Ready</span>
            <p className="text-[11px] text-slate-500 max-w-[200px]">
              Single-page resume compiled successfully. Click below to view or attach.
            </p>
            <div className="flex gap-2 mt-2">
              <button
                onClick={handleOpenInNewTab}
                className="py-1.5 px-3 bg-slate-800 text-white rounded text-xs font-semibold"
              >
                Open Full View
              </button>
              {onDownload && (
                <button
                  onClick={onDownload}
                  className="py-1.5 px-3 bg-indigo-600 text-white rounded text-xs font-semibold"
                >
                  Download PDF
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Fullscreen Lightbox Modal */}
      {isFullscreen && blobUrl && (
        <div className="fixed inset-0 z-50 bg-slate-900/80 backdrop-blur-sm flex flex-col p-4">
          <div className="flex items-center justify-between pb-3 text-white">
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm">Resume Inspection Lightbox</span>
              <span className="text-[11px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded">
                Single-Page Vector PDF
              </span>
            </div>
            <div className="flex items-center gap-3">
              {onDownload && (
                <button
                  onClick={onDownload}
                  className="px-3 py-1 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-sm"
                >
                  Download PDF
                </button>
              )}
              <button
                onClick={() => setIsFullscreen(false)}
                className="text-slate-300 hover:text-white text-base font-bold p-1"
              >
                ✕ Close
              </button>
            </div>
          </div>
          <div className="flex-1 bg-white rounded-xl overflow-hidden shadow-2xl">
            <iframe src={blobUrl} className="w-full h-full border-none" title="Resume Fullscreen Preview" />
          </div>
        </div>
      )}
    </div>
  );
};
