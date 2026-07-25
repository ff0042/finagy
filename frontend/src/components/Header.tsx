'use client';

import { usePriceStream } from '@/hooks/usePriceStream';
import { useState, useEffect, useCallback } from 'react';
import AccountSelector from './AccountSelector';

export default function Header() {
  const { status, prices } = usePriceStream();
  const [portfolio, setPortfolio] = useState({ cash_balance: 10000.0, total_value: 10000.0, positions: [] as any[] });

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
    fetchPortfolio();
    const handleRefresh = () => fetchPortfolio();
    if (typeof window !== 'undefined') {
      window.addEventListener('refresh-workstation', handleRefresh);
    }
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('refresh-workstation', handleRefresh);
      }
    };
  }, [fetchPortfolio]);

  let livePosValue = 0;
  if (portfolio.positions) {
    portfolio.positions.forEach((p: any) => {
      const cp = prices[p.ticker]?.price || p.current_price || p.avg_cost;
      livePosValue += cp * p.quantity;
    });
  }
  const liveTotalValue = (portfolio.cash_balance || 0) + livePosValue;

  return (
    <header className="flex flex-wrap items-center justify-between p-4 bg-card rounded-lg mb-4 gap-4">
      <div className="flex items-center gap-4">
        <h1 className="text-2xl font-bold text-white">Fin<span className="text-primary">Ally</span></h1>
        <div className="flex items-center gap-2" title={`SSE Connection Status: ${status}`}>
          <div className={`w-3 h-3 rounded-full ${
            status === 'connected' ? 'bg-uptick' : 
            status === 'reconnecting' ? 'bg-accent animate-pulse' : 'bg-downtick'
          }`} />
          <span className="text-xs text-gray-400 capitalize">{status}</span>
        </div>
      </div>
      <div className="flex items-center gap-6">
        <AccountSelector />
        <div className="text-right">
          <p className="text-xs text-gray-400">Total Value</p>
          <p className="text-xl font-mono text-white font-bold">${liveTotalValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-gray-400">Cash Balance</p>
          <p className="text-xl font-mono text-white">${(portfolio.cash_balance || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
        </div>
      </div>
    </header>
  );
}
