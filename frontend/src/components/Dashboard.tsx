'use client';

import { useState, useEffect } from 'react';
import Header from './Header';
import WatchlistPanel from './WatchlistPanel';
import MainChart from './MainChart';
import PortfolioHeatmap from './PortfolioHeatmap';
import PositionsTable from './PositionsTable';
import PnlChart from './PnlChart';
import TradeBar from './TradeBar';
import AIChatPanel from './AIChatPanel';
import { PriceStreamProvider } from '@/hooks/usePriceStream';

export default function Dashboard() {
  const [selectedTicker, setSelectedTicker] = useState('AAPL');

  return (
    <PriceStreamProvider>
      <div className="h-[calc(100vh-2rem)] flex flex-col">
        <Header />
        
        <div className="flex-1 flex gap-4 min-h-0">
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
