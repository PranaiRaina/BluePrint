import React, { useState, useRef, useEffect } from 'react';
import { Mail, CreditCard, ChevronRight, ChevronLeft, Target, AlertCircle, CheckCircle2, LayoutDashboard, Briefcase, FileCheck, Lock, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Session } from '@supabase/supabase-js';
import GlassCard from '../profile/GlassCard';
import PersonalizedAssetView from './PersonalizedAssetView';
import StrategySettings from '../profile/StrategySettings';

interface UserProfileViewProps {
    session: Session;
    onAnalyze?: (ticker: string) => void;
    onViewAnalysis?: () => void;
}

interface PendingItem {
    id: string;
    ticker?: string;
    asset_name?: string;
    quantity?: number;
    price?: number;
    source_doc?: string;
    buy_date?: string;
    status: 'pending' | 'verified';
}

const UserProfileView: React.FC<UserProfileViewProps> = ({ session, onViewAnalysis }) => {
    const user = session.user;
    const email = user.email ?? 'No Email';

    // Section Refs for Scrolling
    const overviewRef = useRef<HTMLDivElement>(null);
    const strategyRef = useRef<HTMLDivElement>(null);
    const portfolioRef = useRef<HTMLDivElement>(null);
    const verificationRef = useRef<HTMLDivElement>(null);
    const securityRef = useRef<HTMLDivElement>(null);

    const [activeSection, setActiveSection] = useState('overview');
    const [pendingItems, setPendingItems] = useState<PendingItem[]>([]);
    const [verifiedItems, setVerifiedItems] = useState<PendingItem[]>([]);
    const [showAddModal, setShowAddModal] = useState(false);
    const [selectedItem, setSelectedItem] = useState<PendingItem | null>(null);
    const [newAsset, setNewAsset] = useState({ ticker: '', asset_name: '', quantity: '', price: '' });
    const [deleteConfirmTicker, setDeleteConfirmTicker] = useState<string | null>(null);
    const [editingTicker, setEditingTicker] = useState<string | null>(null);
    const [editShares, setEditShares] = useState('');
    const [editMode, setEditMode] = useState<'add' | 'remove'>('add');

    // Fetch both pending and verified holdings
    React.useEffect(() => {
        const fetchHoldings = async () => {
            try {
                const token = session.access_token;

                // Fetch pending
                const pendingRes = await fetch('http://localhost:8001/v1/portfolio/pending', {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (pendingRes.ok) {
                    const data = await pendingRes.json() as { items: PendingItem[] };
                    setPendingItems(data.items);
                }

                // Fetch verified
                const verifiedRes = await fetch('http://localhost:8001/v1/portfolio/holdings', {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (verifiedRes.ok) {
                    const data = await verifiedRes.json() as { items: PendingItem[] };
                    setVerifiedItems(data.items);
                }
            } catch (e) {
                console.error("Failed to fetch holdings", e);
            }
        };
        void fetchHoldings();
    }, [session]);

    const handleConfirm = async (itemId: string) => {
        try {
            const token = session.access_token;
            const res = await fetch(`http://localhost:8001/v1/portfolio/confirm/${itemId}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                // Move item from pending to verified
                const confirmedItem = pendingItems.find(i => i.id === itemId);
                if (confirmedItem) {
                    setPendingItems(prev => prev.filter(i => i.id !== itemId));
                    setVerifiedItems(prev => [...prev, { ...confirmedItem, status: 'verified' }]);
                }
            }
        } catch (e) {
            console.error("Failed to confirm item", e);
        }
    };

    const handleAddAsset = async () => {
        if (!newAsset.ticker || !newAsset.quantity) return;

        try {
            const token = session.access_token;
            const payload = {
                ticker: newAsset.ticker.toUpperCase(),
                asset_name: newAsset.asset_name || newAsset.ticker.toUpperCase(),
                quantity: parseFloat(newAsset.quantity),
                price: newAsset.price ? parseFloat(newAsset.price) : 0,
                source_doc: 'Manual Entry',
                buy_date: new Date().toISOString()
            };

            const res = await fetch('http://localhost:8001/v1/portfolio/holdings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                const data = await res.json() as { status: string, item: PendingItem };
                // Add directly to verified items
                setVerifiedItems(prev => [...prev, data.item]);
                setNewAsset({ ticker: '', asset_name: '', quantity: '', price: '' });
                setShowAddModal(false);
            } else {
                console.error("Failed to save asset");
            }
        } catch (e) {
            console.error("Error saving asset:", e);
        }
    };

    // Calculate Total Portfolio Value (Cost Basis) for Weighting
    const totalPortfolioValue = verifiedItems.reduce((acc, item) => {
        return acc + ((item.quantity ?? 0) * (item.price ?? 0));
    }, 0);

    // Aggregate holdings by ticker to prevent duplicate cards
    const aggregatedHoldings = React.useMemo(() => {
        const tickerMap = new Map<string, PendingItem>();

        for (const item of verifiedItems) {
            const ticker = item.ticker?.toUpperCase() ?? 'UNKNOWN';
            const existing = tickerMap.get(ticker);

            if (existing) {
                // Combine: sum quantity, use weighted avg price, keep latest buy_date
                const existingQty = existing.quantity ?? 0;
                const existingPrice = existing.price ?? 0;
                const newQty = item.quantity ?? 0;
                const newPrice = item.price ?? 0;

                const totalQty = existingQty + newQty;
                const avgPrice = totalQty > 0
                    ? ((existingQty * existingPrice) + (newQty * newPrice)) / totalQty
                    : 0;

                tickerMap.set(ticker, {
                    ...existing,
                    quantity: totalQty,
                    price: avgPrice,
                    // Keep most recent buy_date
                    buy_date: (item.buy_date && existing.buy_date && item.buy_date > existing.buy_date)
                        ? item.buy_date
                        : existing.buy_date
                });
            } else {
                tickerMap.set(ticker, { ...item, ticker });
            }
        }

        return Array.from(tickerMap.values());
    }, [verifiedItems]);

    // Handler: Delete a holding by ticker (calls backend DELETE)
    const handleDeleteHolding = async (ticker: string) => {
        try {
            const token = session.access_token;
            const res = await fetch(`http://localhost:8001/v1/portfolio/holdings/${ticker}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                // Remove from local state
                setVerifiedItems(prev => prev.filter(i => (i.ticker?.toUpperCase() ?? '') !== ticker.toUpperCase()));
                setDeleteConfirmTicker(null);
            } else {
                console.error("Delete failed");
            }
        } catch (e) {
            console.error("Error deleting holding:", e);
        }
    };

    // Handler: Add or Remove shares from existing holding
    const handleEditShares = async () => {
        if (!editingTicker || !editShares) return;
        try {
            const token = session.access_token;
            const existingItem = aggregatedHoldings.find(i => i.ticker?.toUpperCase() === editingTicker.toUpperCase());
            if (!existingItem) return;

            const shareChange = parseFloat(editShares);
            const currentQty = existingItem.quantity ?? 0;

            if (editMode === 'remove') {
                // If removing more than we have, just delete all
                if (shareChange >= currentQty) {
                    await handleDeleteHolding(editingTicker);
                    return;
                }
                // For partial removal: Add negative entry (or update backend to support PATCH)
                // Simple approach: Add with negative quantity (backend aggregation will handle)
                const payload = {
                    ticker: editingTicker.toUpperCase(),
                    asset_name: existingItem.asset_name ?? editingTicker,
                    quantity: -shareChange,
                    price: existingItem.price ?? 0,
                    source_doc: 'Manual Entry',
                    buy_date: new Date().toISOString()
                };

                const res = await fetch('http://localhost:8001/v1/portfolio/holdings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify(payload)
                });

                if (res.ok) {
                    // Update local state to reflect reduction
                    setVerifiedItems(prev => prev.map(i =>
                        (i.ticker?.toUpperCase() === editingTicker.toUpperCase())
                            ? { ...i, quantity: (i.quantity ?? 0) - shareChange }
                            : i
                    ));
                }
            } else {
                // Add shares
                const payload = {
                    ticker: editingTicker.toUpperCase(),
                    asset_name: existingItem.asset_name ?? editingTicker,
                    quantity: shareChange,
                    price: existingItem.price ?? 0,
                    source_doc: 'Manual Entry',
                    buy_date: new Date().toISOString()
                };

                const res = await fetch('http://localhost:8001/v1/portfolio/holdings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify(payload)
                });

                if (res.ok) {
                    const data = await res.json() as { status: string, item: PendingItem };
                    setVerifiedItems(prev => [...prev, data.item]);
                }
            }

            setEditingTicker(null);
            setEditShares('');
            setEditMode('add');
        } catch (e) {
            console.error("Error editing shares:", e);
        }
    };


    // Carousel Navigation Logic
    const handleNavigate = (direction: 'next' | 'prev') => {
        if (!selectedItem || verifiedItems.length === 0) return;
        const currentIndex = verifiedItems.findIndex(i => i.id === selectedItem.id);
        if (currentIndex === -1) return;

        let newIndex;
        if (direction === 'next') {
            newIndex = (currentIndex + 1) % verifiedItems.length;
        } else {
            newIndex = (currentIndex - 1 + verifiedItems.length) % verifiedItems.length;
        }
        setSelectedItem(verifiedItems[newIndex]);
    };

    // Keyboard support for carousel
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (!selectedItem) return;
            if (e.key === 'ArrowRight') handleNavigate('next');
            if (e.key === 'ArrowLeft') handleNavigate('prev');
            if (e.key === 'Escape') setSelectedItem(null);
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => { window.removeEventListener('keydown', handleKeyDown); };
    }, [selectedItem, verifiedItems]);

    const scrollToSection = (sectionId: string, ref: React.RefObject<HTMLDivElement>) => {
        setActiveSection(sectionId);
        ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };

    const navItems = [
        { id: 'overview', label: 'Overview', icon: LayoutDashboard, ref: overviewRef },
        { id: 'strategy', label: 'Strategy', icon: Target, ref: strategyRef },
        { id: 'portfolio', label: 'Portfolio', icon: Briefcase, ref: portfolioRef },
        { id: 'verification', label: 'Verification', icon: FileCheck, ref: verificationRef },
        { id: 'security', label: 'Security & Billing', icon: Lock, ref: securityRef },
    ];

    return (
        <div className="w-full h-full flex">
            {/* Left Side Navigation (Fixed) */}
            <div className="w-64 fixed h-[calc(100vh-4rem)] top-16 left-0 border-r border-white/5 bg-black/20 backdrop-blur-sm p-6 hidden md:block overflow-y-auto">
                <div className="mb-8">
                    <h2 className="text-xs text-slate-500 font-bold uppercase tracking-widest mb-4">On This Page</h2>
                    <div className="space-y-1">
                        {navItems.map((item) => (
                            <button
                                key={item.id}
                                onClick={() => { scrollToSection(item.id, item.ref); }}
                                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 group ${activeSection === item.id
                                    ? 'bg-primary/10 text-primary'
                                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                                    }`}
                            >
                                <item.icon className={`w-4 h-4 ${activeSection === item.id ? 'text-primary' : 'text-slate-500 group-hover:text-slate-300'}`} />
                                {item.label}
                                {activeSection === item.id && (
                                    <div className="ml-auto w-1.5 h-1.5 rounded-full bg-primary shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
                                )}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Mini Profile Summary in Nav */}
                <div className="p-4 rounded-xl bg-white/5 border border-white/5">
                    <div className="text-xs text-slate-500 mb-2">Current Plan</div>
                    <div className="text-white font-bold text-sm mb-1">Pro Member</div>
                    <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden mb-2">
                        <div className="w-3/4 h-full bg-primary" />
                    </div>
                    <div className="text-[10px] text-slate-400">Renews Feb 28, 2026</div>
                </div>
            </div>

            {/* Main Content Area (Scrollable) */}
            <div className="flex-1 ml-0 md:ml-64 p-8 md:p-12 pb-32 max-w-5xl mx-auto">
                <h1 className="text-4xl font-serif font-bold text-white mb-2">My Profile</h1>
                <p className="text-slate-400 mb-10">Manage your family office settings, portfolio strategy, and security.</p>

                {/* 1. Overview Section */}
                <div ref={overviewRef} className="scroll-mt-24">
                    <div className="glass-card p-8 rounded-3xl border border-white/10 flex items-center gap-6">
                        <div className="w-20 h-20 rounded-full bg-gradient-to-br from-primary to-ai flex items-center justify-center text-3xl font-serif text-white shadow-xl shadow-primary/20">
                            {email.substring(0, 2).toUpperCase()}
                        </div>
                        <div>
                            <h2 className="text-2xl font-bold text-white mb-1">Welcome back, Rishi</h2>
                            <div className="flex items-center gap-2 text-text-secondary mb-3">
                                <Mail className="w-4 h-4" />
                                <span>{email}</span>
                            </div>
                            <div className="flex gap-2">
                                <span className="px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 text-xs font-mono border border-emerald-500/20">
                                    Verified Investor
                                </span>
                            </div>
                        </div>
                        <button className="ml-auto px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-sm font-medium text-white transition-colors border border-white/10">
                            Edit Profile
                        </button>
                    </div>
                </div>

                <hr className="border-t border-dashed border-white/10 my-12" />

                {/* 2. Strategy Section */}
                <div ref={strategyRef} className="scroll-mt-24">
                    <StrategySettings session={session} />
                </div>

                <hr className="border-t border-dashed border-white/10 my-12" />

                {/* 3. Portfolio Section */}
                <div ref={portfolioRef} className="scroll-mt-24">
                    <div className="flex justify-between items-end mb-6">
                        <div className="flex items-center gap-3">
                            <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
                                <Briefcase className="w-5 h-5" />
                            </div>
                            <h2 className="text-2xl font-bold text-white">Your Portfolio</h2>
                        </div>
                        <button
                            type="button"
                            onClick={() => onViewAnalysis?.()}
                            className="text-primary hover:text-white text-sm font-medium flex items-center gap-1 transition-colors"
                        >
                            View Analysis <ChevronRight className="w-4 h-4" />
                        </button>
                    </div>

                    <div className="flex gap-6 overflow-x-auto pb-8 pt-2 px-1 -mx-1 no-scrollbar">
                        {aggregatedHoldings.length > 0 ? (
                            aggregatedHoldings.map((item, index) => {
                                const colors = ['#3b82f6', '#10b981', '#0ea5e9', '#8b5cf6', '#f59e0b', '#ef4444'];
                                return (
                                    <GlassCard
                                        key={item.id}
                                        ticker={item.ticker ?? 'N/A'}
                                        name={item.asset_name ?? 'Unknown'}
                                        shares={item.quantity ?? 0}
                                        price={item.price ?? 0}
                                        change={0}
                                        value={(item.quantity ?? 0) * (item.price ?? 0)}
                                        color={colors[index % colors.length]}
                                        onClick={() => { setSelectedItem(item); }}
                                        session={session}
                                        layoutId={`card-${item.id}`}
                                        onEdit={(ticker) => { setEditingTicker(ticker); }}
                                        onDelete={(ticker) => { setDeleteConfirmTicker(ticker); }}
                                    />
                                );
                            })
                        ) : (
                            <div className="w-full text-center py-12 text-slate-500">
                                <Briefcase className="w-12 h-12 mx-auto mb-3 opacity-20" />
                                <p>No verified holdings yet.</p>
                                <p className="text-xs mt-1">Confirm pending items to add them here.</p>
                            </div>
                        )}
                        <button
                            type="button"
                            onClick={() => { setShowAddModal(true); }}
                            className="w-48 h-48 rounded-3xl border-2 border-dashed border-white/10 flex flex-col items-center justify-center text-slate-500 hover:text-white hover:border-white/30 hover:bg-white/5 transition-all cursor-pointer flex-shrink-0 group"
                        >
                            <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
                                <span className="text-2xl font-light">+</span>
                            </div>
                            <span className="text-sm font-medium">Add Asset</span>
                        </button>
                    </div>
                </div>

                <hr className="border-t border-dashed border-white/10 my-12" />

                {/* 4. Verification Section (Human in Loop) */}
                <div ref={verificationRef} className="scroll-mt-24">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="p-2 rounded-lg bg-yellow-500/10 text-yellow-500">
                            <FileCheck className="w-5 h-5" />
                        </div>
                        <h2 className="text-2xl font-bold text-white">Pending Verification</h2>
                    </div>

                    {pendingItems.length > 0 ? (
                        <div className="glass-card p-6 rounded-2xl border border-yellow-500/20 bg-yellow-500/5 mb-8">
                            <div className="flex items-start gap-4">
                                <div className="p-2 bg-yellow-500/20 rounded-lg text-yellow-500 shrink-0">
                                    <AlertCircle className="w-6 h-6" />
                                </div>
                                <div className="flex-1">
                                    <h3 className="text-white font-bold text-lg mb-1">Action Required: Verify Extracted Data</h3>
                                    <p className="text-slate-300 text-sm mb-4">
                                        The Agent found recent assets in your uploaded documents.
                                        Please confirm details before adding to your portfolio.
                                    </p>

                                    <div className="space-y-3">
                                        {pendingItems.map((item) => (
                                            <div key={item.id} className="bg-black/40 rounded-xl p-4 border border-white/5 flex flex-col md:flex-row md:items-center justify-between gap-4">
                                                <div className="flex items-center gap-4">
                                                    <span className="font-mono text-yellow-500 font-bold">{item.ticker ?? 'UNKNOWN'}</span>
                                                    <span className="text-white">{item.asset_name ?? 'Unknown Asset'}</span>
                                                    <span className="text-slate-400 text-sm">
                                                        {item.quantity ?? 0} Shares @ {item.price != null ? `$${String(item.price)}` : 'Unknown Price'}
                                                    </span>
                                                    <span className="text-xs text-slate-500 italic ml-2">from {item.source_doc ?? 'Unknown'}</span>
                                                </div>
                                                <div className="flex gap-2">
                                                    <button className="px-3 py-1.5 rounded-lg bg-white/5 text-slate-400 hover:text-white hover:bg-white/10 text-sm transition-colors">Edit</button>
                                                    <button
                                                        onClick={() => { void handleConfirm(item.id); }}
                                                        className="px-3 py-1.5 rounded-lg bg-primary/20 text-primary hover:bg-primary/30 text-sm font-medium transition-colors flex items-center gap-1"
                                                    >
                                                        <CheckCircle2 className="w-3 h-3" /> Confirm
                                                    </button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="bg-white/5 rounded-2xl p-8 text-center border border-white/10">
                            <CheckCircle2 className="w-12 h-12 text-emerald-500/20 mx-auto mb-3" />
                            <h3 className="text-slate-300 font-medium">All caught up!</h3>
                            <p className="text-slate-500 text-sm">No pending items to verify.</p>
                        </div>
                    )}
                </div>

                <hr className="border-t border-dashed border-white/10 my-12" />

                {/* 5. Security & Billing */}
                <div ref={securityRef} className="scroll-mt-24">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400">
                            <Lock className="w-5 h-5" />
                        </div>
                        <h2 className="text-2xl font-bold text-white">Security & Billing</h2>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Security */}
                        <div className="glass-card p-6 rounded-2xl border border-white/10">
                            <h3 className="text-lg font-bold text-white mb-4">Security Settings</h3>
                            <div className="space-y-4">
                                <div className="flex justify-between items-center p-3 hover:bg-white/5 rounded-lg transition-colors cursor-pointer group">
                                    <div>
                                        <div className="text-white text-sm font-medium">Password</div>
                                        <div className="text-xs text-slate-500">Last changed 3 months ago</div>
                                    </div>
                                    <button className="text-xs text-primary group-hover:underline">Update</button>
                                </div>
                                <div className="flex justify-between items-center p-3 hover:bg-white/5 rounded-lg transition-colors cursor-pointer group">
                                    <div>
                                        <div className="text-white text-sm font-medium">2-Factor Auth</div>
                                        <div className="text-xs text-emerald-400">Enabled</div>
                                    </div>
                                    <button className="text-xs text-primary group-hover:underline">Configure</button>
                                </div>
                            </div>
                        </div>

                        {/* Billing */}
                        <div className="glass-card p-6 rounded-2xl border border-white/10">
                            <div className="flex items-center gap-2 mb-4">
                                <CreditCard className="w-5 h-5 text-purple-400" />
                                <h3 className="text-lg font-bold text-white">Billing Method</h3>
                            </div>
                            <div className="p-4 bg-gradient-to-br from-purple-500/10 to-blue-500/10 border border-purple-500/20 rounded-xl">
                                <div className="flex justify-between items-start mb-2">
                                    <span className="text-white font-mono text-sm">•••• 4242</span>
                                    <span className="text-xs text-white/50">Exp 12/28</span>
                                </div>
                                <div className="text-xs text-purple-300">Next billing date: Feb 28, 2026</div>
                            </div>
                            <div className="mt-4 flex gap-2">
                                <button className="flex-1 py-2 rounded-lg bg-white/5 text-xs text-white hover:bg-white/10 transition-colors">History</button>
                                <button className="flex-1 py-2 rounded-lg bg-white/5 text-xs text-white hover:bg-white/10 transition-colors">Edit</button>
                            </div>
                        </div>
                    </div>
                </div>


                {/* Bottom Spacer */}
                <div className="h-24" />

            </div>

            {/* Add Asset Modal */}
            {showAddModal && (
                <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
                    <div className="bg-slate-900 border border-white/10 rounded-2xl p-6 w-full max-w-md mx-4">
                        <h3 className="text-xl font-bold text-white mb-4">Add New Asset</h3>

                        <div className="space-y-4">
                            <div>
                                <label htmlFor="ticker-input" className="block text-sm text-slate-400 mb-1">Ticker Symbol *</label>
                                <input
                                    id="ticker-input"
                                    type="text"
                                    placeholder="e.g. AAPL"
                                    value={newAsset.ticker}
                                    onChange={(e) => { setNewAsset(prev => ({ ...prev, ticker: e.target.value })); }}
                                    className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white placeholder:text-slate-500 focus:border-primary/50 focus:outline-none"
                                />
                            </div>

                            <div>
                                <label htmlFor="asset-name-input" className="block text-sm text-slate-400 mb-1">Asset Name</label>
                                <input
                                    id="asset-name-input"
                                    type="text"
                                    placeholder="e.g. Apple Inc."
                                    value={newAsset.asset_name}
                                    onChange={(e) => { setNewAsset(prev => ({ ...prev, asset_name: e.target.value })); }}
                                    className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white placeholder:text-slate-500 focus:border-primary/50 focus:outline-none"
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label htmlFor="shares-input" className="block text-sm text-slate-400 mb-1">Shares *</label>
                                    <input
                                        id="shares-input"
                                        type="number"
                                        placeholder="100"
                                        value={newAsset.quantity}
                                        onChange={(e) => { setNewAsset(prev => ({ ...prev, quantity: e.target.value })); }}
                                        className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white placeholder:text-slate-500 focus:border-primary/50 focus:outline-none"
                                    />
                                </div>
                                <div>
                                    <label htmlFor="price-input" className="block text-sm text-slate-400 mb-1">Price ($)</label>
                                    <input
                                        id="price-input"
                                        type="number"
                                        step="0.01"
                                        placeholder="150.00"
                                        value={newAsset.price}
                                        onChange={(e) => { setNewAsset(prev => ({ ...prev, price: e.target.value })); }}
                                        className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white placeholder:text-slate-500 focus:border-primary/50 focus:outline-none"
                                    />
                                </div>
                            </div>
                        </div>

                        <div className="flex gap-3 mt-6">
                            <button
                                onClick={() => { setShowAddModal(false); }}
                                className="flex-1 px-4 py-2 rounded-lg border border-white/10 text-slate-400 hover:bg-white/5 transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={() => { void handleAddAsset(); }}
                                className="flex-1 px-4 py-2 rounded-lg bg-primary text-white font-medium hover:bg-primary/80 transition-colors"
                            >
                                Add Asset
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Refined Pop-Up Modal with Carousel */}
            <AnimatePresence>
                {selectedItem && (
                    <>
                        {/* Backdrop */}
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4"
                            onClick={() => { setSelectedItem(null); }}
                        />

                        {/* Modal Container */}
                        <motion.div
                            layoutId={`card-${selectedItem.id}`}
                            className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none"
                        >
                            <div className="relative w-full max-w-4xl h-auto min-h-[500px] pointer-events-auto flex items-center">
                                {/* Navigation Arrows (Outside Card) */}
                                <button
                                    onClick={(e) => { e.stopPropagation(); handleNavigate('prev'); }}
                                    className="absolute -left-16 p-3 rounded-full bg-white/5 border border-white/10 hover:bg-white/10 hover:scale-110 transition-all text-white hidden md:block group z-50"
                                >
                                    <ChevronLeft className="w-8 h-8 group-hover:-translate-x-0.5 transition-transform" />
                                </button>

                                <button
                                    onClick={(e) => { e.stopPropagation(); handleNavigate('next'); }}
                                    className="absolute -right-16 p-3 rounded-full bg-white/5 border border-white/10 hover:bg-white/10 hover:scale-110 transition-all text-white hidden md:block group z-50"
                                >
                                    <ChevronRight className="w-8 h-8 group-hover:translate-x-0.5 transition-transform" />
                                </button>

                                {/* Main Card Content */}
                                <div className="w-full h-full bg-[#0f172a] rounded-3xl overflow-hidden border border-white/10 shadow-2xl flex flex-col relative">
                                    {/* Close Button */}
                                    <button
                                        onClick={() => { setSelectedItem(null); }}
                                        className="absolute top-4 right-4 z-50 p-2 rounded-full bg-black/20 hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
                                    >
                                        <X className="w-5 h-5" />
                                    </button>

                                    {/* Content Scroll Area */}
                                    <div className="flex-1 overflow-y-auto no-scrollbar">
                                        <PersonalizedAssetView
                                            session={session}
                                            ticker={selectedItem.ticker ?? ''}
                                            quantity={selectedItem.quantity ?? 0}
                                            avgPrice={selectedItem.price ?? 0}
                                            buyDate={selectedItem.buy_date} // Pass buy_date if available
                                            totalPortfolioValue={totalPortfolioValue}
                                            onClose={() => { setSelectedItem(null); }}
                                        />
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    </>
                )}
            </AnimatePresence>

            {/* Delete Confirmation Modal */}
            <AnimatePresence>
                {deleteConfirmTicker && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4"
                        onClick={() => setDeleteConfirmTicker(null)}
                    >
                        <motion.div
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.9, opacity: 0 }}
                            className="bg-slate-900 rounded-2xl p-6 max-w-sm w-full border border-white/10"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <h3 className="text-xl font-bold text-white mb-2">Delete {deleteConfirmTicker}?</h3>
                            <p className="text-slate-400 text-sm mb-6">This will remove all shares of {deleteConfirmTicker} from your portfolio. This action cannot be undone.</p>
                            <div className="flex gap-3">
                                <button
                                    type="button"
                                    onClick={() => setDeleteConfirmTicker(null)}
                                    className="flex-1 px-4 py-2.5 rounded-xl bg-white/5 text-slate-300 hover:bg-white/10 transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="button"
                                    onClick={() => void handleDeleteHolding(deleteConfirmTicker)}
                                    className="flex-1 px-4 py-2.5 rounded-xl bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors font-medium"
                                >
                                    Delete
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Edit Shares Modal */}
            <AnimatePresence>
                {editingTicker && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4"
                        onClick={() => { setEditingTicker(null); setEditShares(''); setEditMode('add'); }}
                    >
                        <motion.div
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.9, opacity: 0 }}
                            className="bg-slate-900 rounded-2xl p-6 max-w-sm w-full border border-white/10"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <h3 className="text-xl font-bold text-white mb-4">Edit {editingTicker}</h3>

                            {/* Add/Remove Toggle */}
                            <div className="flex bg-white/5 rounded-xl p-1 mb-5">
                                <button
                                    type="button"
                                    onClick={() => setEditMode('add')}
                                    className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${editMode === 'add'
                                        ? 'bg-emerald-500/20 text-emerald-400'
                                        : 'text-slate-400 hover:text-white'
                                        }`}
                                >
                                    + Add
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setEditMode('remove')}
                                    className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${editMode === 'remove'
                                        ? 'bg-red-500/20 text-red-400'
                                        : 'text-slate-400 hover:text-white'
                                        }`}
                                >
                                    − Remove
                                </button>
                            </div>

                            <div className="mb-6">
                                <label className="block text-sm text-slate-400 mb-2">
                                    {editMode === 'add' ? 'Shares to Add' : 'Shares to Remove'}
                                </label>
                                <input
                                    type="number"
                                    value={editShares}
                                    onChange={(e) => setEditShares(e.target.value)}
                                    placeholder="0"
                                    min="0"
                                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-primary/50"
                                />
                            </div>
                            <div className="flex gap-3">
                                <button
                                    type="button"
                                    onClick={() => { setEditingTicker(null); setEditShares(''); setEditMode('add'); }}
                                    className="flex-1 px-4 py-2.5 rounded-xl bg-white/5 text-slate-300 hover:bg-white/10 transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="button"
                                    onClick={() => void handleEditShares()}
                                    className={`flex-1 px-4 py-2.5 rounded-xl font-medium transition-colors ${editMode === 'add'
                                        ? 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30'
                                        : 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                                        }`}
                                >
                                    {editMode === 'add' ? 'Add Shares' : 'Remove Shares'}
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default UserProfileView;
