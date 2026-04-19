import { useEffect, useState } from 'react';
import { X, User, Shield } from 'lucide-react';

import type { AgentDetail } from '../../api/types';
import { renderMarkdown } from '../../utils/render';

interface AgentDetailDialogProps {
  agentId: string;
  agentName: string;
  fetchDetail: (agentId: string) => Promise<AgentDetail>;
  onClose: () => void;
}

export function AgentDetailDialog({ agentId, agentName, fetchDetail, onClose }: AgentDetailDialogProps) {
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'soul' | 'scope'>('soul');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchDetail(agentId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [agentId, fetchDetail]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: 'var(--color-overlay)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg max-h-[80vh] flex flex-col rounded-2xl shadow-xl"
        style={{ backgroundColor: 'var(--color-surface)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4" style={{ borderBottomWidth: 1, borderBottomColor: 'var(--color-border)', borderBottomStyle: 'solid' }}>
          <div className="flex items-center gap-2">
            <User className="h-5 w-5" style={{ color: 'var(--color-primary)' }} />
            <h3 className="text-lg font-semibold" style={{ color: 'var(--color-text)' }}>{agentName}</h3>
            <span className="rounded-md px-1.5 py-0.5 text-[10px] font-mono" style={{ backgroundColor: 'var(--color-surface-alt)', color: 'var(--color-text-secondary)' }}>
              {agentId}
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 hover:opacity-80"
            style={{ color: 'var(--color-text-muted)' }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Tab bar */}
        <div className="flex px-6 pt-3 gap-1">
          <button
            type="button"
            onClick={() => setActiveTab('soul')}
            className="flex items-center gap-1.5 rounded-t-lg px-3 py-1.5 text-xs font-medium"
            style={{
              backgroundColor: activeTab === 'soul' ? 'var(--color-primary-soft)' : 'transparent',
              color: activeTab === 'soul' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
              borderWidth: 1,
              borderBottomWidth: 0,
              borderStyle: 'solid',
              borderColor: activeTab === 'soul' ? 'var(--color-primary-border)' : 'transparent',
            }}
          >
            <User className="h-3.5 w-3.5" />
            Soul
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('scope')}
            className="flex items-center gap-1.5 rounded-t-lg px-3 py-1.5 text-xs font-medium"
            style={{
              backgroundColor: activeTab === 'scope' ? 'var(--color-primary-soft)' : 'transparent',
              color: activeTab === 'scope' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
              borderWidth: 1,
              borderBottomWidth: 0,
              borderStyle: 'solid',
              borderColor: activeTab === 'scope' ? 'var(--color-primary-border)' : 'transparent',
            }}
          >
            <Shield className="h-3.5 w-3.5" />
            Data Scope
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>加载中...</span>
            </div>
          )}
          {error && (
            <div className="rounded-lg p-3 text-sm" style={{ backgroundColor: 'var(--color-alert-error-bg)', color: 'var(--color-alert-error-text)' }}>
              {error}
            </div>
          )}
          {!loading && !error && detail && activeTab === 'soul' && (
            detail.soul ? (
              renderMarkdown(detail.soul, false)
            ) : (
              <div className="py-8 text-center text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                暂无 Soul 配置
              </div>
            )
          )}
          {!loading && !error && detail && activeTab === 'scope' && (
            detail.data_scope && Object.keys(detail.data_scope).length > 0 ? (
              <div className="space-y-3">
                {Object.entries(detail.data_scope).map(([key, value]) => (
                  <div key={key} className="rounded-lg p-3" style={{ backgroundColor: 'var(--color-surface-alt)' }}>
                    <div className="mb-1 text-xs font-semibold" style={{ color: 'var(--color-text-secondary)' }}>
                      {key}
                    </div>
                    <div className="text-sm font-mono" style={{ color: 'var(--color-text)' }}>
                      {Array.isArray(value) ? (
                        <div className="flex flex-wrap gap-1">
                          {(value as string[]).map((item, i) => (
                            <span key={i} className="rounded px-1.5 py-0.5 text-xs" style={{ backgroundColor: 'var(--color-surface)', borderWidth: 1, borderColor: 'var(--color-border)', borderStyle: 'solid' }}>
                              {String(item)}
                            </span>
                          ))}
                        </div>
                      ) : typeof value === 'object' && value !== null ? (
                        <pre className="overflow-x-auto text-xs whitespace-pre-wrap" style={{ color: 'var(--color-text)' }}>
                          {JSON.stringify(value, null, 2)}
                        </pre>
                      ) : (
                        <span>{String(value)}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                暂无 Data Scope 配置
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}
