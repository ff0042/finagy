'use client';
import { useState, useEffect } from 'react';
import { fetchApi } from '../lib/api';

export default function AutonomyToggle() {
    const [enabled, setEnabled] = useState(false);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchApi<{enabled: boolean}>('/api/llm/autonomy')
            .then(data => {
                setEnabled(data.enabled);
                setLoading(false);
            })
            .catch(err => {
                console.error('Failed to load autonomy state', err);
                setLoading(false);
            });
    }, []);

    const toggle = async () => {
        if (loading) return;
        const nextState = !enabled;
        setEnabled(nextState);
        try {
            await fetchApi<{status: string, enabled: boolean}>('/api/llm/autonomy', {
                method: 'POST',
                body: JSON.stringify({ enabled: nextState })
            });
        } catch (err) {
            console.error('Failed to set autonomy', err);
            setEnabled(!nextState); // revert on failure
        }
    };

    if (loading) return <div className="h-9 w-24 bg-gray-800 rounded-md animate-pulse"></div>;

    return (
        <div className="flex items-center gap-2 px-3 py-2 bg-gray-800 rounded-md border border-gray-700" title={enabled ? "Autonomous Mode: Agent executes trades automatically" : "Confirmation Mode: Agent waits for your approval"}>
            <span className="text-xs font-medium text-gray-300 uppercase tracking-wider w-20 text-center">
                {enabled ? 'Auto-Pilot' : 'Co-Pilot'}
            </span>
            <button 
                onClick={toggle}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${enabled ? 'bg-green-500' : 'bg-gray-600'}`}
            >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${enabled ? 'translate-x-4' : 'translate-x-1'}`} />
            </button>
        </div>
    );
}
