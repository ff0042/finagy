'use client';

import { useState, useEffect, useCallback } from 'react';
import { ChevronDown, Wallet } from 'lucide-react';

interface Account {
  id: string;
  account_number: string;
  name: string;
  type: string;
  is_active: number;
  cash_balance: number;
}

export default function AccountSelector() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [activeAccount, setActiveAccount] = useState<Account | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  const fetchAccounts = useCallback(async () => {
    try {
      const res = await fetch('/api/accounts');
      if (res.ok) {
        const data: Account[] = await res.json();
        setAccounts(data);
        const currentActive = data.find(a => a.is_active === 1) || data[0] || null;
        setActiveAccount(currentActive);
      }
    } catch (err) {}
  }, []);

  useEffect(() => {
    fetchAccounts();
    const handleRefresh = () => fetchAccounts();
    if (typeof window !== 'undefined') {
      window.addEventListener('refresh-workstation', handleRefresh);
    }
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('refresh-workstation', handleRefresh);
      }
    };
  }, [fetchAccounts]);

  const selectAccount = async (account: Account) => {
    setIsOpen(false);
    try {
      const res = await fetch('/api/accounts/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: account.id })
      });
      if (res.ok) {
        setActiveAccount(account);
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('refresh-workstation'));
        }
      }
    } catch (err) {}
  };

  const getSuffix = (acctNum: string) => {
    return acctNum && acctNum.length >= 4 ? `***${acctNum.slice(-4)}` : '';
  };

  return (
    <div className="relative">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 bg-card2 hover:bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-xs font-semibold text-white transition-colors">
        <Wallet className="w-4 h-4 text-accent" />
        <span className="text-gray-300">{activeAccount ? activeAccount.name : 'Select Account'}</span>
        {activeAccount?.account_number && (
          <span className="text-gray-500 font-mono">{getSuffix(activeAccount.account_number)}</span>
        )}
        <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-56 bg-card border border-gray-700 rounded-md shadow-xl z-50 py-1">
          <div className="px-3 py-1.5 text-[10px] font-bold text-gray-400 uppercase tracking-wider border-b border-gray-800">
            Select Active Account
          </div>
          {accounts.map(acct => {
            const isSelected = activeAccount?.id === acct.id;
            return (
              <button
                key={acct.id}
                onClick={() => selectAccount(acct)}
                className={`w-full text-left px-3 py-2 text-xs flex flex-col hover:bg-gray-800 transition-colors ${
                  isSelected ? 'bg-primary/10 border-l-2 border-primary text-white font-bold' : 'text-gray-300'
                }`}>
                <div className="flex justify-between items-center w-full">
                  <span>{acct.name}</span>
                  <span className="text-[10px] text-gray-500 font-mono">{getSuffix(acct.account_number)}</span>
                </div>
                <div className="flex justify-between items-center w-full text-[10px] text-gray-400 mt-0.5">
                  <span className="uppercase text-accent/80">{acct.type}</span>
                  <span className="font-mono text-gray-300">${acct.cash_balance?.toLocaleString()} Cash</span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
