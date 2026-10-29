import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[RoleSync ErrorBoundary] Caught error:', error, errorInfo);
  }

  public handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-4 m-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-900 flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <span className="w-5 h-5 rounded-full bg-rose-500 text-white flex items-center justify-center text-xs font-bold">
              !
            </span>
            <h4 className="text-xs font-bold">{this.props.fallbackTitle || 'Component Error'}</h4>
          </div>
          <p className="text-[11px] text-rose-700">
            {this.state.error?.message || 'An unexpected rendering error occurred in this view.'}
          </p>
          <button
            onClick={this.handleReset}
            className="self-start mt-1 px-3 py-1 bg-white border border-rose-300 hover:bg-rose-100/50 text-rose-700 font-semibold text-xs rounded-lg transition-colors shadow-2xs"
          >
            ↻ Recover View
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
