'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { AuthStatus } from '../types';
import { fetchApi } from '../lib/api';

interface AuthContextType {
  authStatus: AuthStatus;
  loading: boolean;
  refreshAuthStatus: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authStatus, setAuthStatus] = useState<AuthStatus>({ authenticated: false });
  const [loading, setLoading] = useState(true);

  const refreshAuthStatus = useCallback(async () => {
    try {
      const data = await fetchApi<AuthStatus>('/api/schwab/auth-status');
      setAuthStatus(data);
    } catch (err) {
      console.error('Failed to fetch auth status', err);
      setAuthStatus({ authenticated: false });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshAuthStatus();

    const handleSuccess = (e: MessageEvent) => {
      if (e.data === 'schwab-auth-success') {
        refreshAuthStatus();
      }
    };
    window.addEventListener('message', handleSuccess);
    return () => window.removeEventListener('message', handleSuccess);
  }, [refreshAuthStatus]);

  return (
    <AuthContext.Provider value={{ authStatus, loading, refreshAuthStatus }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuthStatus() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuthStatus must be used within an AuthProvider');
  }
  return context;
}
