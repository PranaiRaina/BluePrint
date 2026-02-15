import React, { useState, useEffect } from 'react';
import { ChevronRight, ChevronLeft, AlertCircle, CheckCircle2, Briefcase, FileCheck, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { createPortal } from 'react-dom';
import type { Session } from '@supabase/supabase-js';
import GlassCard from '../profile/GlassCard';
import PersonalizedAssetView from './PersonalizedAssetView';

interface StocksViewProps {
    session: Session;
    onAnalyze?: (ticker: string) => void;
    onViewAnalysis?: () => void;
    isSidebarOpen: boolean;
}

interface HoldingItem {
    id: string;
    ticker?: string;
    asset_name?: string;
    quantity?: number;
    price?: number;
    source_doc?: string;
    buy_date?: string;
    status: 'pending' | 'verified';
}

const StocksView: React.FC<StocksViewProps> = ({ session, onViewAnalysis, isSidebarOpen }) => {
    const [pendingItems, setPendingItems] = useState<HoldingItem[]>([]);
    const [verifiedItems, setVerifiedItems] = useState<HoldingItem[]>([]);
    const [showAddModal, setShowAddModal] = useState(false);
    const [selectedItem, setSelectedItem] = useState<HoldingItem | null>(null);
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

                const pendingRes = await fetch('http://localhost:8001/v1/portfolio/pending', {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (pendingRes.ok) {
                    const data = await pendingRes.json() as { items: HoldingItem[] };
                    setPendingItems(data.items);
                }

                const verifiedRes = await fetch('http://localhost:8001/v1/portfolio/holdings', {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (verifiedRes.ok) {
                    const data = await verifiedRes.json() as { items: HoldingItem[] };
                    setVerifiedItems(data.items);
                }
            } catch (e) {
                console.error("Failed to fetch holdings", e);
            }
        };
        void fetchHoldings();
    }, [session]);

    // Carousel Navigation Logic
    const handleNavigate = React.useCallback((direction: 'next' | 'prev') => {
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
    }, [selectedItem, verifiedItems]);

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
    }, [selectedItem, handleNavigate]);

    const handleConfirm = async (itemId: string) => {
        try {
            const token = session.access_token;
            const res = await fetch(`http://localhost:8001/v1/portfolio/confirm/${itemId}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
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
                const data = await res.json() as { status: string, item: HoldingItem };
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
        const tickerMap = new Map<string, HoldingItem>();

        for (const item of verifiedItems) {
            const ticker = item.ticker?.toUpperCase() ?? 'UNKNOWN';
            const existing = tickerMap.get(ticker);

            if (existing) {
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

    // Handler: Delete a holding by ticker
    const handleDeleteHolding = async (ticker: string) => {
        try {
            const token = session.access_token;
            const res = await fetch(`http://localhost:8001/v1/portfolio/holdings/${ticker}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
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
                if (shareChange >= currentQty) {
                    await handleDeleteHolding(editingTicker);
                    return;
                }
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
                    setVerifiedItems(prev => prev.map(i =>
                        (i.ticker?.toUpperCase() === editingTicker.toUpperCase())
                            ? { ...i, quantity: (i.quantity ?? 0) - shareChange }
                            : i
                    ));
                }
            } else {
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
                    const data = await res.json() as { status: string, item: HoldingItem };
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



    return (
        <div className="w-full max-w-5xl mx-auto p-8 md:p-12 pb-32">
            <h1 className="text-4xl font-serif font-bold text-white mb-2">My Stocks</h1>
            <p className="text-slate-400 mb-10">Manage your portfolio holdings and verify extracted assets.</p>

            {/* Portfolio Section */}
            <div>
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
                            <p className="text-xs mt-1">Confirm pending items or add assets manually.</p>
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

            {/* Verification Section */}
            <div>
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

            {/* Personalized Asset View Carousel Modal - Portalled to body to escape parent transforms */}
            {typeof document !== 'undefined' && createPortal(
                <AnimatePresence>
                    {selectedItem && (
                        <>
                            {/* Backdrop - Now respects sidebar width so sidebar remains visible */}
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{
                                    opacity: 1,
                                    left: isSidebarOpen ? 260 : 64
                                }}
                                exit={{ opacity: 0 }}
                                transition={{ duration: 0.15, ease: "linear" }}
                                className="fixed top-0 bottom-0 right-0 bg-black/80 backdrop-blur-md z-[60] flex items-center justify-center p-4 will-change-auto"
                                style={{ transform: 'translateZ(0)' }}
                                onClick={() => { setSelectedItem(null); }}
                            />

                            {/* Modal Container */}
                            <motion.div
                                className="fixed top-0 bottom-0 right-0 z-[61] flex items-center justify-center pointer-events-none p-4 will-change-auto"
                                animate={{
                                    left: isSidebarOpen ? 260 : 64,
                                }}
                                transition={{ duration: 0.15, ease: "linear", type: "tween" }}
                            >
                                <motion.div
                                    layoutId={`card-${selectedItem.id}`}
                                    className="relative w-full max-w-4xl h-[85vh] pointer-events-auto flex items-start overflow-hidden"
                                >
                                    {/* Navigation Arrows */}
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
                                        <button
                                            onClick={() => { setSelectedItem(null); }}
                                            className="absolute top-4 right-4 z-50 p-2 rounded-full bg-black/20 hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
                                        >
                                            <X className="w-5 h-5" />
                                        </button>

                                        <div className="flex-1 overflow-y-auto no-scrollbar">
                                            <PersonalizedAssetView
                                                session={session}
                                                ticker={selectedItem.ticker ?? ''}
                                                quantity={selectedItem.quantity ?? 0}
                                                avgPrice={selectedItem.price ?? 0}
                                                buyDate={selectedItem.buy_date}
                                                totalPortfolioValue={totalPortfolioValue}
                                                onClose={() => { setSelectedItem(null); }}
                                            />
                                        </div>
                                    </div>
                                </motion.div>
                            </motion.div>
                        </>
                    )}
                </AnimatePresence>,
                document.body
            )}

            {/* Delete Confirmation Modal */}
            <AnimatePresence>
                {deleteConfirmTicker && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4"
                        onClick={() => { setDeleteConfirmTicker(null); }}
                    >
                        <motion.div
                            initial={{ scale: 0.9, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.9, opacity: 0 }}
                            className="bg-slate-900 rounded-2xl p-6 max-w-sm w-full border border-white/10"
                            onClick={(e) => { e.stopPropagation(); }}
                        >
                            <h3 className="text-xl font-bold text-white mb-2">Delete {deleteConfirmTicker}?</h3>
                            <p className="text-slate-400 text-sm mb-6">This will remove all shares of {deleteConfirmTicker} from your portfolio. This action cannot be undone.</p>
                            <div className="flex gap-3">
                                <button
                                    type="button"
                                    onClick={() => { setDeleteConfirmTicker(null); }}
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
                            onClick={(e) => { e.stopPropagation(); }}
                        >
                            <h3 className="text-xl font-bold text-white mb-4">Edit {editingTicker}</h3>

                            {/* Add/Remove Toggle */}
                            <div className="flex bg-white/5 rounded-xl p-1 mb-5">
                                <button
                                    type="button"
                                    onClick={() => { setEditMode('add'); }}
                                    className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${editMode === 'add'
                                        ? 'bg-emerald-500/20 text-emerald-400'
                                        : 'text-slate-400 hover:text-white'
                                        }`}
                                >
                                    + Add
                                </button>
                                <button
                                    type="button"
                                    onClick={() => { setEditMode('remove'); }}
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
                                    onChange={(e) => { setEditShares(e.target.value); }}
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

export default StocksView;
