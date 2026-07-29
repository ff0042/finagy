'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Zap, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
  actions?: {
    trades?: any[];
    watchlist_changes?: any[];
  };
}

export default function AIChatPanel() {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: 'assistant', text: 'Hello! I am FinAlly, your AI trading copilot. How can I help with your portfolio or watchlist today?' }
  ]);

  useEffect(() => {
    const handleResetChat = () => {
      setMessages([
        { role: 'assistant', text: 'Hello! I am FinAlly, your AI trading copilot. How can I help with your portfolio or watchlist today?' }
      ]);
    };

    if (typeof window !== 'undefined') {
      window.addEventListener('reset-chat', handleResetChat);
    }
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('reset-chat', handleResetChat);
      }
    };
  }, []);

  const sendPrompt = async (promptText: string) => {
    if (!promptText.trim() || loading) return;
    
    const userMsg = promptText.trim();
    setMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    if (input === promptText) setInput('');
    setLoading(true);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg })
      });
      
      const data = await res.json();
      
      const assistantText = data.message || 'Action executed successfully.';
      const actions = {
        trades: data.trades || [],
        watchlist_changes: data.watchlist_changes || []
      };

      setMessages(prev => [...prev, { 
        role: 'assistant', 
        text: assistantText,
        actions 
      }]);

      if ((actions.trades && actions.trades.length > 0) || (actions.watchlist_changes && actions.watchlist_changes.length > 0)) {
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('refresh-workstation'));
        }
      }
    } catch (err: any) {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        text: `Failed to communicate with AI server: ${err.message || 'Server error'}` 
      }]);
    } finally {
      setLoading(false);
      setTimeout(() => {
        inputRef.current?.focus();
      }, 50);
    }
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    sendPrompt(input);
  };

  return (
    <div className="bg-card rounded-lg flex flex-col h-full border-l border-gray-800">
      <div className="p-4 border-b border-gray-800 flex justify-between items-center">
        <h2 className="text-lg font-bold flex items-center gap-2">
          <Bot className="text-submit" size={20} /> FinAlly AI
        </h2>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${m.role === 'user' ? 'bg-primary' : 'bg-submit'}`}>
              {m.role === 'user' ? <User size={16} /> : <Bot size={16} />}
            </div>
            <div className={`rounded-lg p-3 max-w-[85%] ${m.role === 'user' ? 'bg-primary/20 text-right' : 'bg-card2 text-left'}`}>
              <div className={`text-sm ${m.role === 'assistant' ? 'markdown-content' : ''}`}>
                {m.role === 'assistant' ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
                ) : (
                  <p>{m.text}</p>
                )}
              </div>
              
              {m.actions?.trades && m.actions.trades.length > 0 && (
                <div className="mt-2 text-xs bg-black/40 p-1.5 rounded text-uptick font-mono">
                  {m.actions.trades.map((t, idx) => (
                    <div key={idx}>✓ Executed: {t.side.toUpperCase()} {t.quantity} {t.ticker}</div>
                  ))}
                </div>
              )}

              {m.actions?.watchlist_changes && m.actions.watchlist_changes.length > 0 && (
                <div className="mt-2 text-xs bg-black/40 p-1.5 rounded text-accent font-mono">
                  {m.actions.watchlist_changes.map((w, idx) => (
                    <div key={idx}>✓ Watchlist {w.action.toUpperCase()}: {w.ticker}</div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex gap-3 items-center text-gray-400 text-sm">
            <div className="w-8 h-8 rounded-full bg-submit flex items-center justify-center">
              <Loader2 size={16} className="animate-spin text-white" />
            </div>
            <span>FinAlly AI is thinking & executing orders...</span>
          </div>
        )}
      </div>

      <div className="p-4 border-t border-gray-800">
        <div className="flex gap-2 mb-3 overflow-x-auto pb-1 no-scrollbar">
          <button 
            onClick={() => sendPrompt('Please add IBIT to watchlist')}
            className="whitespace-nowrap text-xs bg-card2 hover:bg-gray-700 px-3 py-1 rounded-full flex items-center gap-1 text-gray-300">
            <Zap size={12} className="text-accent" /> Add IBIT to Watchlist
          </button>
          <button 
            onClick={() => sendPrompt('Please buy 1 share of AAPL')}
            className="whitespace-nowrap text-xs bg-card2 hover:bg-gray-700 px-3 py-1 rounded-full flex items-center gap-1 text-gray-300">
            <Zap size={12} className="text-accent" /> Buy 1 AAPL
          </button>
          <button 
            onClick={() => sendPrompt('Rebalance portfolio')}
            className="whitespace-nowrap text-xs bg-card2 hover:bg-gray-700 px-3 py-1 rounded-full flex items-center gap-1 text-gray-300">
            <Zap size={12} className="text-accent" /> Rebalance
          </button>
        </div>
        <form onSubmit={submit} className="relative">
          <input 
            ref={inputRef}
            type="text" 
            value={input}
            onChange={e => setInput(e.target.value)}
            disabled={loading}
            placeholder="Ask AI to trade or manage watchlist..."
            className="w-full bg-card2 border border-gray-700 rounded-lg pl-4 pr-10 py-3 text-sm focus:outline-none focus:border-submit transition-colors"
          />
          <button 
            type="submit" 
            disabled={loading || !input.trim()}
            className="absolute right-2 top-2 p-1.5 text-white bg-submit rounded hover:opacity-90 transition-opacity disabled:opacity-50">
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  );
}
