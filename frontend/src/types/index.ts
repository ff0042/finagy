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
  current_price?: number;
  market_value?: number;
  unrealized_pnl?: number;
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
