export interface Account {
  id: string;
  name: string;
  type: string;
  cash_balance: number;
}

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  asset_type?: string;
  current_price?: number;
  market_value?: number;
  unrealized_pnl?: number;
  live_pricing?: boolean;
}

export interface Portfolio {
  account: Account | null;
  cash_balance: number;
  positions: Position[];
  total_value: number;
  total_pnl: number;
}

export interface WatchlistItem {
  ticker: string;
  price_data?: any;
}

export interface Trade {
  ticker: string;
  quantity: number;
  side: 'buy' | 'sell';
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  actions?: any;
  created_at: string;
}

export interface AuthStatus {
  authenticated: boolean;
  token_valid_until?: string | null;
}

export interface Order {
  order_id: string;
  ticker: string;
  description?: string;
  action: string;
  quantity: number;
  order_type: string;
  price?: number | null;
  stop_price?: number | null;
  filled_price?: number | null;
  timing: string;
  status: string;
  entered_time?: string;
}
