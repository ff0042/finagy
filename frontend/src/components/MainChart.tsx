'use client';

import { usePriceStream } from '@/hooks/usePriceStream';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip } from 'recharts';

export default function MainChart({ ticker }: { ticker: string }) {
  const { prices } = usePriceStream();
  const data = prices[ticker];

  const chartData = data?.history.map((price, i) => ({
    time: i,
    price
  })) || [];

  return (
    <div className="bg-card rounded-lg p-4 h-full flex flex-col">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold">{ticker} <span className="text-sm font-normal text-gray-400">Live Tick Data</span></h2>
        <div className="flex gap-2">
          {['1D', '5D', '1M', 'ALL'].map(tf => (
            <button key={tf} className="px-2 py-1 text-xs bg-card2 rounded hover:bg-gray-700">{tf}</button>
          ))}
        </div>
      </div>
      <div className="flex-1 relative min-w-0 min-h-0">
        {chartData.length > 0 ? (
          <div className="absolute inset-0">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <XAxis dataKey="time" hide />
                <YAxis domain={['auto', 'auto']} tick={{fill: '#888'}} />
                <Tooltip contentStyle={{backgroundColor: '#161b22', border: 'none'}} />
                <Line type="monotone" dataKey="price" stroke="#209dd7" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">Waiting for data...</div>
        )}
      </div>
    </div>
  );
}
