'use client';

import { useState, useEffect, useCallback } from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts';
import OrdersPanel from './OrdersPanel';

interface Snapshot {
  time: string;
  val: number;
}

export default function PnlChart() {
  const [data, setData] = useState<Snapshot[]>([]);
  const [activeTab, setActiveTab] = useState<'history' | 'orders'>('history');

  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch('/api/portfolio/history');
      if (res.ok) {
        const snapshots = await res.json();
        const formatted = snapshots.map((s: any) => {
          const dt = new Date(s.recorded_at);
          const timeStr = isNaN(dt.getTime()) 
            ? s.recorded_at.substring(11, 16) 
            : dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
          return {
            time: timeStr,
            val: roundTwo(s.total_value)
          };
        });
        setData(formatted);
      }
    } catch (err) {}
  }, []);

  useEffect(() => {
    fetchHistory();
    const handleRefresh = () => fetchHistory();
    if (typeof window !== 'undefined') {
      window.addEventListener('refresh-workstation', handleRefresh);
    }
    const interval = setInterval(fetchHistory, 10000);
    return () => {
      clearInterval(interval);
      if (typeof window !== 'undefined') {
        window.removeEventListener('refresh-workstation', handleRefresh);
      }
    };
  }, [fetchHistory]);

  const roundTwo = (num: number) => Math.round(num * 100) / 100;

  return (
    <div className="bg-card rounded-lg p-4 h-full flex flex-col">
      <div className="flex items-center gap-4 mb-3 border-b border-gray-800 pb-2">
        <button
          onClick={() => setActiveTab('history')}
          className={`text-sm font-bold transition-colors ${
            activeTab === 'history'
              ? 'text-white border-b-2 border-blue-500 pb-2 -mb-2.5'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          Portfolio Value History
        </button>
        <button
          onClick={() => setActiveTab('orders')}
          className={`text-sm font-bold transition-colors ${
            activeTab === 'orders'
              ? 'text-white border-b-2 border-blue-500 pb-2 -mb-2.5'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          Open Orders
        </button>
      </div>

      {activeTab === 'history' ? (
        <div className="flex-1 relative min-w-0 min-h-0">
          {data.length === 0 ? (
            <div className="h-full flex items-center justify-center text-gray-500 text-xs">
              Accumulating snapshots...
            </div>
          ) : (
            <div className="absolute inset-0">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data}>
                  <defs>
                    <linearGradient id="colorVal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#209dd7" stopOpacity={0.4}/>
                      <stop offset="95%" stopColor="#209dd7" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="time" tick={{fill: '#888', fontSize: 10}} />
                  <YAxis domain={['auto', 'auto']} tick={{fill: '#888', fontSize: 10}} width={55} />
                  <Tooltip 
                    contentStyle={{backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '6px'}}
                    formatter={(val: any) => [`$${Number(val).toFixed(2)}`, 'Portfolio Value']}
                  />
                  <Area type="monotone" dataKey="val" stroke="#209dd7" strokeWidth={2} fillOpacity={1} fill="url(#colorVal)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto">
          <OrdersPanel />
        </div>
      )}
    </div>
  );
}
