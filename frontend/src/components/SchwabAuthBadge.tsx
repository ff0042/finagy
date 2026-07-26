'use client';

import { useState, useEffect, useCallback } from 'react';
import { ShieldCheck, ShieldAlert, ExternalLink, RefreshCw, LogOut } from 'lucide-react';

interface AuthStatus {
  authenticated: boolean;
  status?: string;
  account_count?: number;
  reason?: string;
}

export default function SchwabAuthBadge() {
  const [authStatus, setAuthStatus] = useState<AuthStatus>({ authenticated: false });
  const [loading, setLoading] = useState(false);

  const checkStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/schwab/auth-status');
      if (res.ok) {
        const data = await res.json();
        setAuthStatus(data);
      }
    } catch (err) {}
  }, []);

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 15000);

    const handleMessage = (event: MessageEvent) => {
      if (event.data === 'schwab-auth-success') {
        checkStatus();
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('refresh-workstation'));
        }
      }
    };
    window.addEventListener('message', handleMessage);

    return () => {
      clearInterval(interval);
      window.removeEventListener('message', handleMessage);
    };
  }, [checkStatus]);

  const handleConnect = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/schwab/auth-url');
      if (res.ok) {
        const data = await res.json();
        if (data.auth_url) {
          const width = 600;
          const height = 700;
          const left = window.screenX + (window.outerWidth - width) / 2;
          const top = window.screenY + (window.outerHeight - height) / 2;
          window.open(
            data.auth_url,
            'SchwabAuth',
            `width=${width},height=${height},left=${left},top=${top},status=no,resizable=yes,scrollbars=yes`
          );
        }
      }
    } catch (err) {
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    setLoading(true);
    try {
      await fetch('/api/schwab/disconnect', { method: 'POST' });
      setAuthStatus({ authenticated: false });
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refresh-workstation'));
      }
    } catch (err) {
    } finally {
      setLoading(false);
    }
  };

  if (authStatus.authenticated) {
    return (
      <div 
        className="flex items-center gap-1.5 bg-uptick/10 border border-uptick/30 rounded-md px-2.5 py-1 text-xs font-semibold text-uptick"
        title={`Connected to Schwab Developer API (${authStatus.account_count || 0} account(s))`}>
        <ShieldCheck className="w-4 h-4 text-uptick" />
        <span>Schwab Connected</span>
        <button
          onClick={handleDisconnect}
          disabled={loading}
          className="ml-1.5 p-1 bg-gray-800 hover:bg-downtick/20 border border-gray-700 hover:border-downtick/40 rounded text-gray-300 hover:text-downtick transition-colors flex items-center justify-center"
          title="Disconnect Schwab Session">
          {loading ? (
            <RefreshCw className="w-3 h-3 animate-spin text-downtick" />
          ) : (
            <LogOut className="w-3.5 h-3.5" />
          )}
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={handleConnect}
      disabled={loading}
      className="flex items-center gap-1.5 bg-accent/20 hover:bg-accent/30 border border-accent/50 text-accent rounded-md px-2.5 py-1 text-xs font-semibold transition-colors">
      {loading ? (
        <RefreshCw className="w-3.5 h-3.5 animate-spin text-accent" />
      ) : (
        <ShieldAlert className="w-3.5 h-3.5 text-accent" />
      )}
      <span>Connect Schwab</span>
      <ExternalLink className="w-3 h-3 text-accent/70" />
    </button>
  );
}
