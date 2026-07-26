'use client';

import { useEffect } from 'react';

export function useWorkstationRefresh(callback: () => void) {
  useEffect(() => {
    window.addEventListener('refresh-workstation', callback);
    return () => window.removeEventListener('refresh-workstation', callback);
  }, [callback]);
}

export function triggerWorkstationRefresh() {
  window.dispatchEvent(new Event('refresh-workstation'));
}
