'use client';

import { usePriceStream } from '@/hooks/usePriceStream';
import { useState, useEffect, useCallback } from 'react';

interface Position {
  ticker: string;
  description?: string;
  asset_type?: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  live_pricing?: boolean;
}

export default function PositionsTable() {
  const { prices } = usePriceStream();
  const [positions, setPositions] = useState<Position[]>([]);
  const [cashBalance, setCashBalance] = useState<number>(0);

  const fetchPositions = useCallback(async () => {
    try {
      const res = await fetch('/api/portfolio');
      if (res.ok) {
        const data = await res.json();
        setPositions(data.positions || []);
        setCashBalance(data.cash_balance || 0);
      }
    } catch (err) { }
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

  const handleSell = async (ticker: string, quantity: number, side: string = 'sell') => {
    try {
      await fetch('/api/portfolio/trade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, quantity: Math.abs(quantity), side })
      });
      fetchPositions();
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('refresh-workstation'));
      }
    } catch (err) { }
  };

  const equities = positions.filter(p => p.asset_type === 'EQUITY' || !p.asset_type).sort((a, b) => a.ticker.localeCompare(b.ticker));
  const funds = positions.filter(p => p.asset_type === 'MUTUAL_FUND' || p.asset_type === 'ETF').sort((a, b) => a.ticker.localeCompare(b.ticker));
  const options = positions.filter(p => p.asset_type === 'OPTION').sort((a, b) => (a.description || a.ticker).localeCompare(b.description || b.ticker));

  const renderGroup = (title: string, groupPositions: Position[]) => {
    if (groupPositions.length === 0) return null;
    return (
      <tbody className="before:content-[''] before:block before:h-2">
        <tr>
          <td colSpan={6} className="text-sm font-bold text-gray-300 border-b border-gray-600 pb-1 mb-1 pt-2">{title}</td>
        </tr>
        {groupPositions.map(p => {
          const liveData = prices[p.ticker];
          const currentPrice = (liveData && p.live_pricing !== false) ? liveData.price : p.current_price;
          const multiplier = p.asset_type === 'OPTION' ? 100 : 1;
          const pnl = (currentPrice - p.avg_cost) * p.quantity * multiplier;
          const pnlPercent = p.avg_cost ? ((currentPrice - p.avg_cost) / p.avg_cost) * 100 * Math.sign(p.quantity) : 0;
          const isPositive = pnl >= 0;

          return (
            <tr key={p.ticker} className="hover:bg-card2 group border-0">
              <td className="py-0.5 truncate pr-2 font-normal text-xs" title={p.description || p.ticker}>{p.description || p.ticker}</td>
              <td className="py-0.5 text-right font-mono font-normal text-xs">{p.quantity}</td>
              <td className="py-0.5 text-right font-mono font-normal text-xs">${Number(p.avg_cost.toFixed(4))}</td>
              <td className="py-0.5 text-right font-mono font-normal text-xs">${Number(currentPrice.toFixed(4))}</td>
              <td className={`py-0.5 text-right font-mono font-normal text-xs ${isPositive ? 'text-uptick' : 'text-downtick'}`}>
                {isPositive ? '+' : '-'}${Math.abs(pnl).toFixed(2)} ({pnlPercent.toFixed(2)}%)
              </td>
              <td className="py-0.5 text-right">
                <button
                  onClick={() => handleSell(p.ticker, Math.abs(p.quantity), p.quantity > 0 ? 'sell' : 'buy')}
                  className="px-2 py-0.5 bg-downtick text-white rounded text-[10px] opacity-0 group-hover:opacity-100 transition-opacity">
                  {p.quantity > 0 ? 'Sell' : 'Close'}
                </button>
              </td>
            </tr>
          );
        })}
      </tbody>
    );
  };

  const renderCash = () => {
    if (cashBalance <= 0 && positions.length === 0) return null;
    return (
      <tbody className="before:content-[''] before:block before:h-2">
        <tr>
          <td colSpan={6} className="text-sm font-bold text-gray-300 border-b border-gray-600 pb-1 mb-1 pt-2">Cash</td>
        </tr>
        <tr className="hover:bg-card2 border-0">
          <td className="py-0.5 font-normal text-xs">Cash & Sweep</td>
          <td className="py-0.5 text-right font-mono font-normal text-xs"></td>
          <td className="py-0.5 text-right font-mono font-normal text-xs"></td>
          <td className="py-0.5 text-right font-mono font-normal text-xs"></td>
          <td className="py-0.5 text-right font-mono font-normal text-xs">${cashBalance.toFixed(2)}</td>
          <td className="py-0.5 text-right"></td>
        </tr>
      </tbody>
    );
  };

  return (
    <div className="bg-card rounded-lg p-4 flex flex-col h-full overflow-x-auto">
      <h2 className="text-lg font-bold mb-4">Positions</h2>
      <table className="w-full text-left">
        <thead className="text-gray-400 border-b border-gray-800 text-xs">
          <tr>
            <th className="pb-2 font-normal">Symbol</th>
            <th className="pb-2 text-right font-normal">Qty</th>
            <th className="pb-2 text-right font-normal">Avg Cost</th>
            <th className="pb-2 text-right font-normal">Price</th>
            <th className="pb-2 text-right font-normal">Unrealized P&L</th>
            <th className="pb-2 text-right font-normal"></th>
          </tr>
        </thead>
        {positions.length === 0 && cashBalance <= 0 ? (
          <tbody>
            <tr>
              <td colSpan={6} className="py-4 text-center text-gray-500 text-xs">
                No active positions. Execute a trade or ask AI to buy shares.
              </td>
            </tr>
          </tbody>
        ) : (
          <>
            {renderGroup('Equities', equities)}
            {renderGroup('Funds', funds)}
            {renderGroup('Options', options)}
            {renderCash()}
          </>
        )}
      </table>
    </div>
  );
}
