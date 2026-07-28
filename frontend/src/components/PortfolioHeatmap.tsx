'use client';

import { usePriceStream } from '@/hooks/usePriceStream';
import { useState, useEffect, useCallback } from 'react';

export default function PortfolioHeatmap() {
  const { prices } = usePriceStream();
  const [positions, setPositions] = useState<any[]>([]);

  const fetchPortfolio = useCallback(async () => {
    try {
      const res = await fetch('/api/portfolio');
      if (res.ok) {
        const data = await res.json();
        setPositions(data.positions || []);
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

  let totalMarketVal = 0;
  const items = positions.map(p => {
    const cp = prices[p.ticker]?.price || p.current_price || p.avg_cost;
    const mktVal = cp * p.quantity;
    const pnlPct = p.avg_cost ? ((cp - p.avg_cost) / p.avg_cost) * 100 : 0;
    totalMarketVal += mktVal;
    return {
      ticker: p.ticker,
      description: p.description || p.ticker,
      asset_type: p.asset_type,
      mktVal,
      pnlPct,
    };
  });

  return (
    <div className="bg-card rounded-lg p-4 h-full flex flex-col">
      <h2 className="text-lg font-bold mb-4">Portfolio Heatmap</h2>
      {items.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-gray-500 text-xs">
          No positions held
        </div>
      ) : (
        <div className="flex-1 flex flex-wrap gap-1 content-start overflow-y-auto">
          {items.map(p => {
            const weight = totalMarketVal > 0 ? (p.mktVal / totalMarketVal) * 100 : 100 / items.length;
            const isPositive = p.pnlPct >= 0;
            const bgClass = isPositive ? 'bg-uptick/80 hover:bg-uptick' : 'bg-downtick/80 hover:bg-downtick';
            const isOption = p.asset_type === 'OPTION' || p.description.length > 10;
            return (
              <div 
                key={p.ticker} 
                title={p.description}
                className={`${bgClass} flex flex-col items-center justify-center p-1 rounded transition-all cursor-pointer min-w-[60px] flex-1`}
                style={{ flexBasis: `${Math.max(15, weight)}%`, height: `${Math.max(50, Math.min(180, weight * 3))}px` }}>
                <span className={`font-bold text-center leading-tight break-words max-w-full px-1 ${isOption ? 'text-[9px]' : 'text-sm'}`}>
                  {p.description}
                </span>
                <span className="text-[10px] font-mono mt-0.5">{p.pnlPct >= 0 ? '+' : ''}{p.pnlPct.toFixed(2)}%</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
