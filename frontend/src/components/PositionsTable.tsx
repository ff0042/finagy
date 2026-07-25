'use client';

import { usePriceStream } from '@/hooks/usePriceStream';
import { useState, useEffect, useCallback } from 'react';

interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
}

export default function PositionsTable() {
  const { prices } = usePriceStream();
  const [positions, setPositions] = useState<Position[]>([]);

  const fetchPositions = useCallback(async () => {
    try {
      const res = await fetch('/api/portfolio');
      if (res.ok) {
        const data = await res.json();
        setPositions(data.positions || []);
      }
    } catch (err) {}
  }, []);

  useEffect(() => {
    fetchPositions();
    const handleRefresh = () => fetchPositions();
    if (typeof window !== 'undefined') {
      window.addEventListener('refresh-workstation', handleRefresh);
    }
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('refresh-workstation', handleRefresh);
      }
    };
  }, [fetchPositions]);

  const handleSell = async (ticker: string, quantity: number) => {
    try {
      await fetch('/api/portfolio/trade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, quantity, side: 'sell' })
      });
      fetchPositions();
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refresh-workstation'));
      }
    } catch (err) {}
  };

  return (
    <div className="bg-card rounded-lg p-4 flex flex-col h-full overflow-x-auto">
      <h2 className="text-lg font-bold mb-4">Positions</h2>
      <table className="w-full text-sm text-left">
        <thead className="text-gray-400 border-b border-gray-800 text-xs">
          <tr>
            <th className="pb-2">Ticker</th>
            <th className="pb-2 text-right">Qty</th>
            <th className="pb-2 text-right">Avg Cost</th>
            <th className="pb-2 text-right">Price</th>
            <th className="pb-2 text-right">Unrealized P&L</th>
            <th className="pb-2 text-center">Action</th>
          </tr>
        </thead>
        <tbody>
          {positions.length === 0 ? (
            <tr>
              <td colSpan={6} className="py-4 text-center text-gray-500 text-xs">
                No active positions. Execute a trade or ask AI to buy shares.
              </td>
            </tr>
          ) : (
            positions.map(p => {
              const liveData = prices[p.ticker];
              const currentPrice = liveData ? liveData.price : p.current_price;
              const pnl = (currentPrice - p.avg_cost) * p.quantity;
              const pnlPercent = p.avg_cost ? ((currentPrice - p.avg_cost) / p.avg_cost) * 100 : 0;
              const isPositive = pnl >= 0;

              return (
                <tr key={p.ticker} className="border-b border-gray-800/50 hover:bg-card2">
                  <td className="py-3 font-bold">{p.ticker}</td>
                  <td className="py-3 text-right font-mono">{p.quantity}</td>
                  <td className="py-3 text-right font-mono">${p.avg_cost.toFixed(2)}</td>
                  <td className="py-3 text-right font-mono">${currentPrice.toFixed(2)}</td>
                  <td className={`py-3 text-right font-mono ${isPositive ? 'text-uptick' : 'text-downtick'}`}>
                    {isPositive ? '+' : '-'}${Math.abs(pnl).toFixed(2)} ({pnlPercent.toFixed(2)}%)
                  </td>
                  <td className="py-3 text-center">
                    <button 
                      onClick={() => handleSell(p.ticker, p.quantity)}
                      className="px-3 py-1 bg-downtick text-white rounded text-xs hover:opacity-80 transition-opacity">
                      Sell
                    </button>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
