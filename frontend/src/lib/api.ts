import type { Order } from '../types';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!res.ok) {
    let errorMsg = res.statusText;
    try {
      const errorData = await res.json();
      if (errorData && errorData.detail) errorMsg = errorData.detail;
    } catch (e) {
      // Ignore JSON parse error
    }
    throw new Error(`API Error ${res.status}: ${errorMsg}`);
  }

  // Handle empty responses
  if (res.status === 204) return {} as T;
  
  try {
    return await res.json() as T;
  } catch (e) {
    throw new Error('Failed to parse JSON response');
  }
}

export async function getOrders(): Promise<Order[]> {
  return fetchApi<Order[]>('/api/orders');
}

export async function cancelOrder(orderId: string): Promise<{ message?: string }> {
  return fetchApi<{ message?: string }>(`/api/orders/${orderId}`, {
    method: 'DELETE',
  });
}
