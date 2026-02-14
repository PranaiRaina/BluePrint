import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Target, TrendingUp, Shield, Zap, DollarSign, FileText, Loader2, CheckCircle2 } from 'lucide-react';
import type { Session } from '@supabase/supabase-js';

interface StrategySettingsProps {
    session: Session;
}

interface UserProfile {
    risk_level: number;
    objective: string;
    net_worth: number | null;
    tax_status: string;
    strategy_notes?: string | null;  // New field
    is_default?: boolean;
}

const OBJECTIVES = [
    { value: 'growth', label: 'Capital Growth', icon: TrendingUp, description: 'Long-term appreciation' },
    { value: 'income', label: 'Income Generation', icon: DollarSign, description: 'Dividends & cash flow' },
    { value: 'preservation', label: 'Capital Preservation', icon: Shield, description: 'Protect existing wealth' },
    { value: 'speculation', label: 'Speculative Gains', icon: Zap, description: 'High-risk/high-reward' }
];

const TAX_STATUSES = [
    { value: 'taxable', label: 'Taxable Accounts' },
    { value: 'tax_advantaged', label: 'Tax-Advantaged (401k, IRA)' },
    { value: 'mixed', label: 'Mixed Accounts' }
];

const getRiskLabel = (level: number): string => {
    if (level <= 25) return 'Conservative';
    if (level <= 50) return 'Moderate';
    if (level <= 75) return 'Growth';
    return 'Aggressive';
};

const getRiskColor = (level: number): string => {
    if (level <= 25) return 'text-blue-400';
    if (level <= 50) return 'text-emerald-400';
    if (level <= 75) return 'text-amber-400';
    return 'text-red-400';
};

const StrategySettings: React.FC<StrategySettingsProps> = ({ session }) => {
    const [profile, setProfile] = useState<UserProfile>({
        risk_level: 50,
        objective: 'growth',
        net_worth: null,
        tax_status: 'mixed',
        strategy_notes: ''
    });
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    // Fetch profile on mount
    useEffect(() => {
        const fetchProfile = async () => {
            try {
                const res = await fetch('http://localhost:8001/v1/user/profile', {
                    headers: { 'Authorization': `Bearer ${session.access_token}` }
                });
                if (res.ok) {
                    const data = await res.json() as UserProfile;
                    setProfile(data);
                }
            } catch (e) {
                console.error('Failed to fetch profile:', e);
            } finally {
                setLoading(false);
            }
        };
        void fetchProfile();
    }, [session]);

    // Debounced save
    const saveProfile = useCallback(async (newProfile: UserProfile) => {
        setSaving(true);
        setSaved(false);
        try {
            const res = await fetch('http://localhost:8001/v1/user/profile', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${session.access_token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(newProfile)
            });
            if (res.ok) {
                setSaved(true);
                setTimeout(() => { setSaved(false); }, 2000);
            }
        } catch (e) {
            console.error('Failed to save profile:', e);
        } finally {
            setSaving(false);
        }
    }, [session]);

    // Debounce on profile changes
    useEffect(() => {
        if (loading) return;
        const timeoutId = setTimeout(() => {
            // Validate word count before saving
            const words = (profile.strategy_notes ?? '').trim().split(/\s+/).filter(Boolean).length;
            if (words <= 150) {
                void saveProfile(profile);
            }
        }, 800);
        return () => { clearTimeout(timeoutId); };
    }, [profile, loading, saveProfile]);

    const updateProfile = (updates: Partial<UserProfile>) => {
        setProfile(prev => ({ ...prev, ...updates }));
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 animate-spin text-primary" />
            </div>
        );
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
        >
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-primary/10">
                        <Target className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                        <h3 className="text-lg font-semibold text-white">Strategy Profile</h3>
                        <p className="text-sm text-slate-400">Personalize your AI advisor's recommendations</p>
                        <p className="text-xs text-slate-500 mt-1">These preferences currently apply only to the general chatbot, not to stock-specific reports and recommendations.</p>
                    </div>
                </div>
                {saving && (
                    <div className="flex items-center gap-2 text-slate-400 text-sm">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Saving...
                    </div>
                )}
                {saved && (
                    <div className="flex items-center gap-2 text-emerald-400 text-sm">
                        <CheckCircle2 className="w-4 h-4" />
                        Saved
                    </div>
                )}
            </div>

            {/* Risk Level Slider */}
            <div className="bg-white/5 rounded-xl p-5 border border-white/5">
                <div className="flex items-center justify-between mb-4">
                    <span className="text-white font-medium" id="risk-label">Risk Tolerance</span>
                    <span className={`font-semibold ${getRiskColor(profile.risk_level)}`}>
                        {getRiskLabel(profile.risk_level)} ({profile.risk_level}%)
                    </span>
                </div>
                <input
                    aria-labelledby="risk-label"
                    type="range"
                    min="0"
                    max="100"
                    value={profile.risk_level}
                    onChange={(e) => { updateProfile({ risk_level: parseInt(e.target.value) }); }}
                    className="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-primary"
                />
                <div className="flex justify-between text-xs text-slate-500 mt-2">
                    <span>Conservative</span>
                    <span>Moderate</span>
                    <span>Growth</span>
                    <span>Aggressive</span>
                </div>
            </div>

            {/* Investment Objective */}
            <div className="bg-white/5 rounded-xl p-5 border border-white/5">
                <span className="text-white font-medium block mb-4">Investment Objective</span>
                <div className="grid grid-cols-2 gap-3">
                    {OBJECTIVES.map(obj => {
                        const Icon = obj.icon;
                        const isActive = profile.objective === obj.value;
                        return (
                            <button
                                key={obj.value}
                                type="button"
                                onClick={() => { updateProfile({ objective: obj.value }); }}
                                className={`p-4 rounded-xl border transition-all text-left ${isActive
                                    ? 'bg-primary/10 border-primary/50 text-white'
                                    : 'bg-white/5 border-white/5 text-slate-300 hover:border-white/20'
                                    }`}
                            >
                                <Icon className={`w-5 h-5 mb-2 ${isActive ? 'text-primary' : 'text-slate-400'}`} />
                                <div className="font-medium text-sm">{obj.label}</div>
                                <div className="text-xs text-slate-500 mt-1">{obj.description}</div>
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Net Worth & Tax Status Row */}
            <div className="grid md:grid-cols-2 gap-4">
                {/* Net Worth */}
                <div className="bg-white/5 rounded-xl p-5 border border-white/5">
                    <label htmlFor="net-worth-input" className="text-white font-medium block mb-3">
                        <DollarSign className="w-4 h-4 inline mr-2" />
                        Approximate Net Worth
                    </label>
                    <div className="relative">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">$</span>
                        <input
                            id="net-worth-input"
                            type="number"
                            value={profile.net_worth ?? ''}
                            onChange={(e) => { updateProfile({ net_worth: e.target.value ? parseFloat(e.target.value) : null }); }}
                            placeholder="Optional"
                            className="w-full bg-slate-800/50 border border-white/10 rounded-lg pl-8 pr-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-primary/50"
                        />
                    </div>
                    <p className="text-xs text-slate-500 mt-2">Helps tailor advice to your situation</p>
                </div>

                {/* Tax Status */}
                <div className="bg-white/5 rounded-xl p-5 border border-white/5">
                    <label htmlFor="tax-status-select" className="text-white font-medium block mb-3">
                        <FileText className="w-4 h-4 inline mr-2" />
                        Primary Account Type
                    </label>
                    <select
                        id="tax-status-select"
                        value={profile.tax_status}
                        onChange={(e) => { updateProfile({ tax_status: e.target.value }); }}
                        className="w-full bg-slate-800/50 border border-white/10 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-primary/50"
                    >
                        {TAX_STATUSES.map(status => (
                            <option key={status.value} value={status.value}>
                                {status.label}
                            </option>
                        ))}
                    </select>
                    <p className="text-xs text-slate-500 mt-2">Influences tax-aware recommendations</p>
                </div>
            </div>

            {/* Strategy Notes (The "Brain") */}
            <div className="bg-white/5 rounded-xl p-5 border border-white/5">
                <div className="flex items-center justify-between mb-3">
                    <label htmlFor="strategy-notes" className="text-white font-medium">
                        <FileText className="w-4 h-4 inline mr-2" />
                        Strategy Notes (The "Brain")
                    </label>
                    <span className={`text-xs ${(profile.strategy_notes ?? '').trim().split(/\s+/).filter(Boolean).length > 150 ? 'text-red-400' : 'text-slate-500'}`}>
                        {(profile.strategy_notes ?? '').trim().split(/\s+/).filter(Boolean).length} / 150 words
                    </span>
                </div>
                <textarea
                    id="strategy-notes"
                    value={profile.strategy_notes ?? ''}
                    onChange={(e) => { updateProfile({ strategy_notes: e.target.value }); }}
                    placeholder="Describe your specific investment philosophy, sectors to avoid, or unique constraints..."
                    rows={4}
                    className={`w-full bg-slate-800/50 border rounded-lg p-3 text-white placeholder-slate-500 focus:outline-none transition-colors
                        ${(profile.strategy_notes ?? '').trim().split(/\s+/).filter(Boolean).length > 150
                            ? 'border-red-500/50 focus:border-red-500'
                            : 'border-white/10 focus:border-primary/50'
                        }`}
                />
                <p className="text-xs text-slate-500 mt-2">
                    These notes will directly influence the agent's reasoning. Keep it under 150 words for best results.
                </p>
            </div>

            {/* Active Mode Badge */}
            <div className="bg-gradient-to-r from-primary/10 to-ai/10 rounded-xl p-4 border border-primary/20">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary/20">
                        <Zap className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                        <div className="text-white font-medium">
                            Active Mode: {getRiskLabel(profile.risk_level)} {OBJECTIVES.find(o => o.value === profile.objective)?.label}
                        </div>
                        <div className="text-sm text-slate-400">
                            AI responses will be tailored to this profile
                        </div>
                    </div>
                </div>
            </div>
        </motion.div>
    );
};

export default StrategySettings;
