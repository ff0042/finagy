'use client';

import { useState, useEffect } from 'react';
import Header from './Header';
import WatchlistPanel from './WatchlistPanel';
import MainChart from './MainChart';
import PortfolioHeatmap from './PortfolioHeatmap';
import PositionsTable from './PositionsTable';
import PnlChart from './PnlChart';
import AIChatPanel from './AIChatPanel';
import { PriceStreamProvider } from '@/hooks/usePriceStream';

export default function Dashboard() {
  const [selectedTicker, setSelectedTicker] = useState('AAPL');
  const [topHeight, setTopHeight] = useState(400);
  const [leftWidth, setLeftWidth] = useState(300);
  const [rightWidth, setRightWidth] = useState(350);
  const [centerLeftWidth, setCenterLeftWidth] = useState(800); // Dynamic width for Chart/Positions relative to Heatmap/PnL

  useEffect(() => {
    const initSession = async () => {
      if (typeof window !== 'undefined' && !sessionStorage.getItem('finally_session_active')) {
        try {
          await fetch('/api/session/reset', { method: 'POST' });
          sessionStorage.setItem('finally_session_active', 'true');
        } catch (err) {}
      }
    };

    initSession();
  }, []);

  return (
    <PriceStreamProvider>
      <div className="h-[calc(100vh-1rem)] flex flex-col">
        <Header />
        
        <div className="flex-1 flex min-h-0 mt-2">
            
            {/* Left Panel */}
            <div style={{ width: `${leftWidth}px` }} className="flex-shrink-0 h-full">
              <WatchlistPanel onSelect={setSelectedTicker} />
            </div>

            {/* Left Vertical Resizer */}
            <div 
              className="w-2 cursor-col-resize bg-transparent hover:bg-blue-500/10 transition-colors rounded flex flex-col items-center justify-center group z-10 flex-shrink-0"
              onMouseDown={(e) => {
                const startX = e.clientX;
                const startWidth = leftWidth;
                const handleMouseMove = (me: MouseEvent) => {
                  const delta = me.clientX - startX;
                  setLeftWidth(Math.max(150, Math.min(800, startWidth + delta)));
                };
                const handleMouseUp = () => {
                  document.removeEventListener('mousemove', handleMouseMove);
                  document.removeEventListener('mouseup', handleMouseUp);
                };
                document.addEventListener('mousemove', handleMouseMove);
                document.addEventListener('mouseup', handleMouseUp);
              }}
            >
              <div className="w-1 h-12 bg-gray-700/50 rounded-full group-hover:bg-blue-400"></div>
            </div>
            
            {/* Center Panel */}
            <div className="flex-1 flex flex-col h-full min-w-0">
              
              {/* TOP ROW */}
              <div style={{ height: `${topHeight}px` }} className="flex-shrink-0 flex min-h-0">
                <div style={{ width: `${centerLeftWidth}px` }} className="flex-shrink-0 h-full min-h-0">
                  <MainChart ticker={selectedTicker} />
                </div>
                
                {/* Center-Vertical Resizer (Top Half) */}
                <div 
                  className="w-2 cursor-col-resize bg-transparent hover:bg-blue-500/10 transition-colors rounded flex flex-col items-center justify-center group z-10 flex-shrink-0"
                  onMouseDown={(e) => {
                    const startX = e.clientX;
                    const startWidth = centerLeftWidth;
                    const handleMouseMove = (me: MouseEvent) => {
                      const delta = me.clientX - startX;
                      setCenterLeftWidth(Math.max(300, Math.min(2000, startWidth + delta)));
                    };
                    const handleMouseUp = () => {
                      document.removeEventListener('mousemove', handleMouseMove);
                      document.removeEventListener('mouseup', handleMouseUp);
                    };
                    document.addEventListener('mousemove', handleMouseMove);
                    document.addEventListener('mouseup', handleMouseUp);
                  }}
                >
                  <div className="w-1 h-12 bg-gray-700/50 rounded-full group-hover:bg-blue-400"></div>
                </div>

                <div className="flex-1 h-full min-h-0">
                  <PortfolioHeatmap />
                </div>
              </div>
              
              {/* Center Horizontal Resizer */}
              <div 
                className="h-2 cursor-row-resize bg-transparent hover:bg-blue-500/10 transition-colors rounded flex items-center justify-center group z-10 flex-shrink-0"
                onMouseDown={(e) => {
                  const startY = e.clientY;
                  const startHeight = topHeight;
                  const handleMouseMove = (me: MouseEvent) => {
                    const delta = me.clientY - startY;
                    setTopHeight(Math.max(200, Math.min(800, startHeight + delta)));
                  };
                  const handleMouseUp = () => {
                    document.removeEventListener('mousemove', handleMouseMove);
                    document.removeEventListener('mouseup', handleMouseUp);
                  };
                  document.addEventListener('mousemove', handleMouseMove);
                  document.addEventListener('mouseup', handleMouseUp);
                }}
              >
                 <div className="w-12 h-1 bg-gray-700/50 rounded-full group-hover:bg-blue-400"></div>
              </div>
              
              {/* BOTTOM ROW */}
              <div className="flex-1 min-h-0 flex">
                <div style={{ width: `${centerLeftWidth}px` }} className="flex-shrink-0 h-full min-h-0">
                  <PositionsTable />
                </div>
                
                {/* Center-Vertical Resizer (Bottom Half) */}
                <div 
                  className="w-2 cursor-col-resize bg-transparent hover:bg-blue-500/10 transition-colors rounded flex flex-col items-center justify-center group z-10 flex-shrink-0"
                  onMouseDown={(e) => {
                    const startX = e.clientX;
                    const startWidth = centerLeftWidth;
                    const handleMouseMove = (me: MouseEvent) => {
                      const delta = me.clientX - startX;
                      setCenterLeftWidth(Math.max(300, Math.min(2000, startWidth + delta)));
                    };
                    const handleMouseUp = () => {
                      document.removeEventListener('mousemove', handleMouseMove);
                      document.removeEventListener('mouseup', handleMouseUp);
                    };
                    document.addEventListener('mousemove', handleMouseMove);
                    document.addEventListener('mouseup', handleMouseUp);
                  }}
                >
                  <div className="w-1 h-12 bg-gray-700/50 rounded-full group-hover:bg-blue-400"></div>
                </div>

                <div className="flex-1 h-full min-h-0">
                  <PnlChart />
                </div>
              </div>
            </div>

            {/* Right Vertical Resizer */}
            <div 
              className="w-2 cursor-col-resize bg-transparent hover:bg-blue-500/10 transition-colors rounded flex flex-col items-center justify-center group z-10 flex-shrink-0"
              onMouseDown={(e) => {
                const startX = e.clientX;
                const startWidth = rightWidth;
                const handleMouseMove = (me: MouseEvent) => {
                  const delta = startX - me.clientX; // Moving left increases width
                  setRightWidth(Math.max(200, Math.min(800, startWidth + delta)));
                };
                const handleMouseUp = () => {
                  document.removeEventListener('mousemove', handleMouseMove);
                  document.removeEventListener('mouseup', handleMouseUp);
                };
                document.addEventListener('mousemove', handleMouseMove);
                document.addEventListener('mouseup', handleMouseUp);
              }}
            >
              <div className="w-1 h-12 bg-gray-700/50 rounded-full group-hover:bg-blue-400"></div>
            </div>

            {/* Right Panel */}
            <div style={{ width: `${rightWidth}px` }} className="flex-shrink-0 h-full">
              <AIChatPanel />
            </div>

          </div>
      </div>
    </PriceStreamProvider>
  );
}
