'use client';

import { usePriceStream } from '@/hooks/usePriceStream';
import { useState, useEffect, useCallback } from 'react';
import { Plus, X } from 'lucide-react';

export default function WatchlistPanel({ onSelect }: { onSelect: (ticker: string) => void }) {
  const { prices } = usePriceStream();
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [newTicker, setNewTicker] = useState('');

  const fetchWatchlist = useCallback(async () => {
    try {
      const res = await fetch('/api/watchlist');
      if (res.ok) {
        const data = await res.json();
        const tickers = data.map((item: any) => item.ticker);
        setWatchlist(tickers);
      }
    } catch (err) {}
  }, []);

  useEffect(() => {
    fetchWatchlist();

    const handleRefresh = () => fetchWatchlist();
    if (typeof window !== 'undefined') {
      window.addEventListener('refresh-workstation', handleRefresh);
    }
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('refresh-workstation', handleRefresh);
      }
    };
  }, [fetchWatchlist]);

  const addTicker = async (e: React.FormEvent) => {
    e.preventDefault();
    const symbol = newTicker.trim().toUpperCase();
    if (!symbol) return;

    try {
      await fetch('/api/watchlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: symbol })
      });
      setNewTicker('');
      fetchWatchlist();
    } catch (err) {}
  };

  const removeTicker = async (ticker: string) => {
    try {
      await fetch(`/api/watchlist/${ticker}`, {
        method: 'DELETE'
      });
      fetchWatchlist();
    } catch (err) {}
  };

  return (
    <div className="bg-card rounded-lg p-4 flex flex-col h-full">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-bold">Watchlist</h2>
        <form onSubmit={addTicker} className="flex gap-2">
          <input
            type="text"
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value)}
            className="bg-card2 border border-gray-700 rounded px-2 py-1 text-sm w-24 uppercase focus:outline-none focus:border-primary"
            placeholder="TICKER"
          />
          <button type="submit" className="bg-primary text-white p-1 rounded hover:opacity-90">
            <Plus size={16} />
          </button>
        </form>
      </div>
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-500 border-b border-gray-800 text-xs text-left">
              <th className="pb-2">Symbol</th>
              <th className="pb-2 text-right">Price</th>
              <th className="pb-2 text-right">Change</th>
              <th className="pb-2 text-right"></th>
            </tr>
          </thead>
          <tbody>
            {watchlist.length === 0 ? (
              <tr>
                <td colSpan={4} className="py-4 text-center text-gray-500 text-xs">
                  No watched tickers. Add one above or via AI chat.
                </td>
              </tr>
            ) : (
              watchlist.map(ticker => {
                const data = prices[ticker];
                const flashClass = data?.flash === 'green' ? 'flash-green' : data?.flash === 'red' ? 'flash-red' : '';
                const tickColor = data?.tickDirection === 'up' ? 'text-uptick' : data?.tickDirection === 'down' ? 'text-downtick' : 'text-gray-400';

                return (
                  <tr key={ticker} className={`border-b border-gray-800/50 cursor-pointer hover:bg-card2 transition-colors ${tickColor}`} onClick={() => onSelect(ticker)}>
                    <td className="py-2.5 font-bold">{ticker}</td>
                    <td className={`py-2.5 text-right font-mono ${flashClass}`}>
                      {data ? `$${Number(data.price.toFixed(4))}` : '---'}
                    </td>
                    <td className="py-2.5 text-right font-mono">
                      {data ? `${data.change >= 0 ? '+' : ''}${data.changePercent.toFixed(2)}%` : '---'}
                    </td>
                    <td className="py-2.5 text-right">
                      <button onClick={(e) => { e.stopPropagation(); removeTicker(ticker); }} className="text-gray-500 hover:text-red-500 p-1">
                        <X size={14} />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
