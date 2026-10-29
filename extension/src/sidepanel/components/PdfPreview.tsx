import React, { useEffect, useRef, useState } from 'react';

interface PdfPreviewProps {
  pdfBase64: string;
  onDownload?: () => void;
}

export const PdfPreview: React.FC<PdfPreviewProps> = ({ pdfBase64, onDownload }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [renderError, setRenderError] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

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
        const loadingTask = pdfjsLib.getDocument({
          data: uint8Array,
          useSystemFonts: true,
          isEvalSupported: false
        });

        const pdf = await loadingTask.promise;
        if (isCancelled) return;

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
          <span className="text-[10px] bg-indigo-50 text-indigo-700 px-1.5 py-0.5 rounded font-semibold border border-indigo-100">
            1-Page Budgeted
          </span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleOpenInNewTab}
            className="text-xs font-semibold text-slate-600 hover:text-slate-900 transition-colors"
            title="Open in new browser tab"
          >
            Open Tab ↗
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
    </div>
  );
};
