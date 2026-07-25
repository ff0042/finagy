'use client';

import { useState, useEffect } from 'react';

export default function TradeBar({ selectedTicker }: { selectedTicker: string }) {
  const [ticker, setTicker] = useState(selectedTicker || 'AAPL');
  const [qty, setQty] = useState('1');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (selectedTicker) {
      setTicker(selectedTicker);
    }
  }, [selectedTicker]);

  const executeTrade = async (side: 'buy' | 'sell') => {
    const symbol = ticker.trim().toUpperCase();
    const quantity = parseFloat(qty);
    if (!symbol || isNaN(quantity) || quantity <= 0 || loading) return;

    setLoading(true);
    try {
      const res = await fetch('/api/portfolio/trade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: symbol, quantity, side })
      });
      if (res.ok) {
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('refresh-workstation'));
        }
      }
    } catch (err) {} finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-card rounded-lg p-4">
      <h2 className="text-lg font-bold mb-4">Quick Trade</h2>
      <form className="flex gap-4 items-end" onSubmit={(e) => e.preventDefault()}>
        <div className="flex-1">
          <label className="block text-xs text-gray-400 mb-1">Ticker</label>
          <input 
            type="text" 
            value={ticker} 
            onChange={e => setTicker(e.target.value.toUpperCase())}
            className="w-full bg-card2 border border-gray-700 rounded px-3 py-2 text-white uppercase focus:outline-none focus:border-primary"
            placeholder="AAPL"
          />
        </div>
        <div className="flex-1">
          <label className="block text-xs text-gray-400 mb-1">Quantity</label>
          <input 
            type="number" 
            value={qty}
            min="1"
            step="any"
            onChange={e => setQty(e.target.value)}
            className="w-full bg-card2 border border-gray-700 rounded px-3 py-2 text-white focus:outline-none focus:border-primary"
            placeholder="1"
          />
        </div>
        <button 
          type="button"
          onClick={() => executeTrade('buy')}
          disabled={loading}
          className="bg-uptick hover:bg-green-600 text-white px-6 py-2 rounded font-bold transition-colors disabled:opacity-50">
          Buy
        </button>
        <button 
          type="button"
          onClick={() => executeTrade('sell')}
          disabled={loading}
          className="bg-downtick hover:bg-red-600 text-white px-6 py-2 rounded font-bold transition-colors disabled:opacity-50">
          Sell
        </button>
      </form>
    </div>
  );
}
