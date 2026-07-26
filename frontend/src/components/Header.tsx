'use client';

import { usePriceStream } from '@/hooks/usePriceStream';
import { useState, useEffect, useCallback } from 'react';
import AccountSelector from './AccountSelector';
import SchwabAuthBadge from './SchwabAuthBadge';
import ModelSelector from './ModelSelector';

export default function Header() {
  const { status, prices } = usePriceStream();
  const [portfolio, setPortfolio] = useState({ cash_balance: 0.0, total_value: 0.0, positions: [] as any[] });
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const fetchAuthStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/schwab/auth-status');
      if (res.ok) {
        const data = await res.json();
        setIsAuthenticated(data.authenticated || false);
      }
    } catch (err) {
      setIsAuthenticated(false);
    }
  }, []);

  const fetchPortfolio = useCallback(async () => {
    try {
      const res = await fetch('/api/portfolio');
      if (res.ok) {
        const data = await res.json();
        setPortfolio(data);
      }
    } catch (err) {}
  }, []);

  useEffect(() => {
    fetchAuthStatus();
    fetchPortfolio();

    const handleRefresh = () => {
      fetchAuthStatus();
      fetchPortfolio();
    };

    if (typeof window !== 'undefined') {
      window.addEventListener('refresh-workstation', handleRefresh);
    }
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('refresh-workstation', handleRefresh);
      }
    };
  }, [fetchAuthStatus, fetchPortfolio]);

  let livePosValue = 0;
  if (portfolio.positions) {
    portfolio.positions.forEach((p: any) => {
      const cp = prices[p.ticker]?.price || p.current_price || p.avg_cost;
      livePosValue += cp * p.quantity;
    });
  }

  const liveCash = portfolio.cash_balance !== undefined ? portfolio.cash_balance : 10000.0;
  const liveTotalValue = portfolio.positions && portfolio.positions.length > 0 ? (liveCash + livePosValue) : (portfolio.total_value !== undefined ? portfolio.total_value : liveCash);

  return (
    <header className="flex flex-wrap items-center justify-between p-4 bg-card rounded-lg mb-4 gap-4">
      <div className="flex items-center gap-4">
        <h1 className="text-2xl font-bold text-white">Fin<span className="text-primary">Ally</span></h1>
      </div>
      <div className="flex items-center gap-4">
        <SchwabAuthBadge />
        <AccountSelector />
        <ModelSelector />
        <div className="text-right pl-2 border-l border-gray-800">
          <p className="text-xs text-gray-400">Total Value</p>
          <p className="text-xl font-mono text-white font-bold">${liveTotalValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-gray-400">Cash Balance</p>
          <p className="text-xl font-mono text-white">${liveCash.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
        </div>
      </div>
    </header>
  );
}
