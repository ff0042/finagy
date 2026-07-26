'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Cpu, ChevronDown, Check, Lock } from 'lucide-react';

interface ModelInfo {
  id: string;
  name: string;
  cost_tier: string;
  best_for: string;
}

export default function ModelSelector() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [activeModel, setActiveModel] = useState<string>('mock/deterministic');
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const fetchAuthStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/schwab/auth-status');
      if (res.ok) {
        const data = await res.json();
        const authed = !!data.authenticated;
        setIsConnected(authed);
        if (!authed && activeModel !== 'mock/deterministic') {
          selectModel('mock/deterministic');
        }
      }
    } catch (err) {}
  }, [activeModel]);

  const fetchModels = async () => {
    try {
      const res = await fetch('/api/llm/models');
      if (res.ok) {
        const data = await res.json();
        setActiveModel(data.active_model);
        if (data.models && data.models.length > 0) {
          setModels(data.models);
        }
      }
    } catch (err) {
      console.error('Failed to fetch LLM models', err);
    }
  };

  useEffect(() => {
    fetchModels();
    fetchAuthStatus();

    const handleRefresh = () => {
      fetchAuthStatus();
    };

    if (typeof window !== 'undefined') {
      window.addEventListener('refresh-workstation', handleRefresh);
    }

    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      if (typeof window !== 'undefined') {
        window.removeEventListener('refresh-workstation', handleRefresh);
      }
    };
  }, [fetchAuthStatus]);

  const selectModel = async (modelId: string) => {
    try {
      const res = await fetch('/api/llm/model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelId }),
      });
      if (res.ok) {
        const data = await res.json();
        setActiveModel(data.active_model);
        setIsOpen(false);
      }
    } catch (err) {
      console.error('Failed to set active model', err);
    }
  };

  const currentModelInfo = models.find((m) => m.id === activeModel) || {
    id: activeModel,
    name: activeModel.split('/')[1] || activeModel,
    cost_tier: activeModel === 'mock/deterministic' ? 'FREE' : '$$',
    best_for: 'Selected AI Model',
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 bg-card2 hover:bg-gray-800 border border-gray-700 px-3 py-1.5 rounded-lg text-xs transition-colors"
        title="Select AI Model"
      >
        <Cpu size={14} className="text-accent" />
        <span className="font-mono text-gray-200 font-medium">{currentModelInfo.id}</span>
        <span className={`font-mono font-bold px-1.5 py-0.5 rounded text-[11px] ${
          currentModelInfo.cost_tier === 'FREE' ? 'text-emerald-400 bg-emerald-400/10' : 'text-accent bg-accent/10'
        }`}>
          {currentModelInfo.cost_tier}
        </span>
        <ChevronDown size={14} className="text-gray-400" />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-[720px] max-w-[90vw] bg-[#121824] border border-gray-700 rounded-xl shadow-2xl z-50 overflow-hidden">
          <div className="p-3 bg-black/40 border-b border-gray-800 flex justify-between items-center">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-400 flex items-center gap-2">
              <Cpu size={14} className="text-accent" /> OpenRouter Model Selection
            </span>
            {!isConnected ? (
              <span className="text-[11px] text-amber-400 font-medium flex items-center gap-1">
                <Lock size={12} /> Disconnected Mode: Only FREE model available
              </span>
            ) : (
              <span className="text-[10px] text-gray-500 font-mono">Relative Cost: FREE → $$$$$ (Frontier)</span>
            )}
          </div>

          <div className="p-2 overflow-x-auto">
            {/* Table Header */}
            <div className="grid grid-cols-[220px_70px_1fr] gap-3 px-3 py-1.5 text-[11px] font-bold text-gray-400 border-b border-gray-800 uppercase tracking-wider">
              <div>MODEL SPECIFIER</div>
              <div className="text-center">COST</div>
              <div>BEST FOR / WHEN TO USE</div>
            </div>

            {/* Table Rows */}
            <div className="divide-y divide-gray-800/50">
              {models.map((m) => {
                const isSelected = m.id === activeModel;
                const isDisabled = !isConnected && m.id !== 'mock/deterministic';
                return (
                  <button
                    key={m.id}
                    disabled={isDisabled}
                    onClick={() => !isDisabled && selectModel(m.id)}
                    className={`w-full grid grid-cols-[220px_70px_1fr] gap-3 px-3 py-2.5 items-center text-left text-xs transition-colors ${
                      isDisabled
                        ? 'opacity-40 cursor-not-allowed bg-gray-900/30'
                        : isSelected
                        ? 'bg-primary/10 border-l-2 border-primary hover:bg-gray-800/60'
                        : 'hover:bg-gray-800/60'
                    }`}
                  >
                    <div className="font-mono text-gray-200 font-medium truncate flex items-center gap-1.5">
                      {isSelected && <Check size={14} className="text-primary shrink-0" />}
                      {isDisabled && <Lock size={12} className="text-amber-400/70 shrink-0" />}
                      <span className={isSelected ? 'text-primary font-bold' : ''}>{m.id}</span>
                    </div>
                    <div className={`text-center font-mono font-bold py-0.5 rounded text-[11px] ${
                      m.cost_tier === 'FREE' ? 'text-emerald-400 bg-emerald-400/10' : 'text-accent bg-accent/10'
                    }`}>
                      {m.cost_tier}
                    </div>
                    <div className="text-gray-300 text-[11px] leading-tight">
                      {m.best_for}
                      {isDisabled && <span className="text-amber-400/80 font-mono ml-2">(Requires Schwab Connection)</span>}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
