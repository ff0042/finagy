'use client';

import { useState, useEffect, useCallback } from 'react';
import Header from './Header';
import WatchlistPanel from './WatchlistPanel';
import MainChart from './MainChart';
import PortfolioHeatmap from './PortfolioHeatmap';
import PositionsTable from './PositionsTable';
import PnlChart from './PnlChart';
import TradeBar from './TradeBar';
import AIChatPanel from './AIChatPanel';
import { PriceStreamProvider } from '@/hooks/usePriceStream';
import { ShieldAlert, ExternalLink, RefreshCw, Lock } from 'lucide-react';

export default function Dashboard() {
  const [selectedTicker, setSelectedTicker] = useState('AAPL');
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);

  const checkAuth = useCallback(async () => {
    try {
      const res = await fetch('/api/schwab/auth-status');
      if (res.ok) {
        const data = await res.json();
        setIsAuthenticated(data.authenticated || false);
      } else {
        setIsAuthenticated(false);
      }
    } catch (err) {
      setIsAuthenticated(false);
    }
  }, []);

  useEffect(() => {
    const initSession = async () => {
      if (typeof window !== 'undefined' && !sessionStorage.getItem('finally_session_active')) {
        try {
          await fetch('/api/session/reset', { method: 'POST' });
          sessionStorage.setItem('finally_session_active', 'true');
        } catch (err) {}
      }
      checkAuth();
    };

    initSession();

    const handleRefresh = () => checkAuth();
    if (typeof window !== 'undefined') {
      window.addEventListener('refresh-workstation', handleRefresh);
    }
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('refresh-workstation', handleRefresh);
      }
    };
  }, [checkAuth]);

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

  return (
    <PriceStreamProvider>
      <div className="h-[calc(100vh-2rem)] flex flex-col">
        <Header />
        
        <div className="flex-1 flex gap-4 min-h-0 mt-4">
            <div className="w-[300px] flex-shrink-0">
              <WatchlistPanel onSelect={setSelectedTicker} />
            </div>
            
            <div className="flex-1 flex flex-col gap-4 overflow-y-auto pr-2">
              <div className="h-[400px] flex-shrink-0 flex gap-4">
                <div className="flex-[2]">
                  <MainChart ticker={selectedTicker} />
                </div>
                <div className="flex-[1]">
                  <PortfolioHeatmap />
                </div>
              </div>
              
              <div className="h-[300px] flex-shrink-0 flex gap-4">
                <div className="flex-[2]">
                  <PositionsTable />
                </div>
                <div className="flex-[1]">
                  <PnlChart />
                </div>
              </div>

              <div className="flex-shrink-0">
                <TradeBar selectedTicker={selectedTicker} />
              </div>
            </div>

            <div className="w-[350px] flex-shrink-0">
              <AIChatPanel />
            </div>
          </div>
      </div>
    </PriceStreamProvider>
  );
}
