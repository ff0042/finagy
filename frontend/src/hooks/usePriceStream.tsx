'use client';

import React, { useState, useEffect, createContext, useContext } from 'react';

export type PriceData = {
  price: number;
  change: number;
  changePercent: number;
  flash: 'green' | 'red' | null;
  tickDirection?: 'up' | 'down' | 'flat';
  history: number[];
};

export type PriceMap = Record<string, PriceData>;

interface PriceStreamContextType {
  prices: PriceMap;
  status: 'connected' | 'reconnecting' | 'disconnected';
}

const PriceStreamContext = createContext<PriceStreamContextType | null>(null);

export function PriceStreamProvider({ children }: { children: React.ReactNode }) {
  const [prices, setPrices] = useState<PriceMap>({});
  const [status, setStatus] = useState<'connected' | 'reconnecting' | 'disconnected'>('disconnected');

  useEffect(() => {
    let sse: EventSource | null = null;
    let reconnectTimer: NodeJS.Timeout;

    const connect = () => {
      setStatus('reconnecting');
      // Relative path or endpoint to work seamlessly when served from FastAPI container or dev
      const streamUrl = typeof window !== 'undefined' && window.location.port === '3000' 
        ? 'http://localhost:8000/api/stream/prices' 
        : '/api/stream/prices';

      sse = new EventSource(streamUrl);
      
      sse.onopen = () => setStatus('connected');
      
      sse.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          setPrices((prev) => {
            const next = { ...prev };
            for (const [ticker, item] of Object.entries(data)) {
              const itemObj = typeof item === 'object' && item !== null ? (item as any) : { price: item };
              const currentPrice = itemObj.price || 0;
              const old = prev[ticker];
              const oldPrice = old?.price || currentPrice;
              
              let flash: 'green' | 'red' | null = null;
              let tickDirection: 'up' | 'down' | 'flat' = old?.tickDirection || 'flat';

              if (old && currentPrice > old.price) {
                flash = 'green';
                tickDirection = 'up';
              } else if (old && currentPrice < old.price) {
                flash = 'red';
                tickDirection = 'down';
              }

              const history = old?.history ? [...old.history, currentPrice].slice(-20) : [currentPrice];

              const change = itemObj.change !== undefined ? itemObj.change : (currentPrice - oldPrice);
              const changePercent = itemObj.change_percent !== undefined ? itemObj.change_percent : (itemObj.changePercent !== undefined ? itemObj.changePercent : (oldPrice ? ((currentPrice - oldPrice) / oldPrice) * 100 : 0));

              next[ticker] = {
                price: currentPrice,
                change,
                changePercent,
                flash,
                tickDirection,
                history,
              };
            }
            return next;
          });
        } catch (err) {}
      };

      sse.onerror = () => {
        sse?.close();
        setStatus('disconnected');
        reconnectTimer = setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      sse?.close();
      clearTimeout(reconnectTimer);
    };
  }, []);

  return (
    <PriceStreamContext.Provider value={{ prices, status }}>
      {children}
    </PriceStreamContext.Provider>
  );
}

export const usePriceStream = () => {
  const ctx = useContext(PriceStreamContext);
  if (!ctx) throw new Error('usePriceStream must be used within PriceStreamProvider');
  return ctx;
};
