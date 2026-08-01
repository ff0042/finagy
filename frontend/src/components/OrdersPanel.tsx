'use client';

import { useState, useEffect, useCallback } from 'react';
import { X, Package } from 'lucide-react';
import { getOrders, cancelOrder } from '@/lib/api';
import type { Order } from '@/types';

const TIMING_LABELS: Record<string, string> = {
  day: 'Day',
  day_ext: 'Day + Ext',
  gtc: 'GTC',
  gtc_ext: 'GTC + Ext',
  ext_am: 'Ext AM',
  ext_pm: 'Ext PM',
};

export default function OrdersPanel() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchOrders = useCallback(async () => {
    try {
      const data = await getOrders();
      setOrders(data);
    } catch {
      setOrders([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOrders();
    const handler = () => fetchOrders();
    window.addEventListener('refresh-workstation', handler);
    return () => window.removeEventListener('refresh-workstation', handler);
  }, [fetchOrders]);

  const handleCancel = async (orderId: string) => {
    try {
      await cancelOrder(orderId);
      // Immediately remove from local state for instant feedback
      setOrders(prev => prev.filter(o => o.order_id !== orderId));
      window.dispatchEvent(new CustomEvent('refresh-workstation'));
    } catch {
      // Silently fail - will re-sync on next refresh
    }
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center text-gray-500 text-sm">
        Loading orders...
      </div>
    );
  }

  if (orders.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-gray-500 text-sm gap-2">
        <Package size={24} className="text-gray-600" />
        No open or filled orders
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-3">
      <div className="space-y-1">
        {orders.map((order) => {
          const isOpen = order.status === 'OPEN';
          const actionDisplay = order.action.replace(/_/g, ' ');
          const priceDisplay = order.order_type.includes('limit') && order.price
            ? ` @ $${order.price.toFixed(2)}`
            : '';
          const timingLabel = TIMING_LABELS[order.timing] || order.timing;

          return (
            <div
              key={order.order_id}
              className="flex items-center justify-between py-2 px-3 rounded-lg bg-card2/50 hover:bg-card2 transition-colors group text-sm"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-white truncate">
                    {order.description || order.ticker}
                  </span>
                  <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                    isOpen 
                      ? 'bg-amber-500/20 text-amber-400' 
                      : 'bg-emerald-500/20 text-emerald-400'
                  }`}>
                    {order.status}
                  </span>
                </div>
                <div className="text-gray-400 text-xs mt-0.5 flex items-center gap-2">
                  <span className="capitalize">{actionDisplay}{priceDisplay}</span>
                  <span>•</span>
                  <span>{order.quantity} shares</span>
                  <span>•</span>
                  <span>{timingLabel}</span>
                  {order.stop_price && (
                    <>
                      <span>•</span>
                      <span>Stop ${order.stop_price.toFixed(2)}</span>
                    </>
                  )}
                  {order.filled_price && (
                    <>
                      <span>•</span>
                      <span className="text-emerald-400">Filled @ ${order.filled_price.toFixed(2)}</span>
                    </>
                  )}
                </div>
              </div>
              {isOpen && (
                <button
                  onClick={() => handleCancel(order.order_id)}
                  className="ml-2 p-1.5 rounded text-gray-600 hover:text-red-400 hover:bg-red-400/10 transition-colors opacity-0 group-hover:opacity-100"
                  title="Cancel order"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
