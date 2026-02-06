import React, { useState, useEffect, useRef } from 'react';
import { TrendingUp, TrendingDown, MoreVertical, Pencil, Trash2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Session } from '@supabase/supabase-js';
import { agentService } from '../../services/agent';

export interface GlassCardProps {
    ticker: string;
    name: string;
    shares: number;
    price: number;
    change: number;
    value: number;
    color?: string;
    onClick?: () => void;
    session: Session;
    layoutId?: string;
    onEdit?: (ticker: string) => void;
    onDelete?: (ticker: string) => void;
}

const GlassCard: React.FC<GlassCardProps> = ({
    ticker, name, shares, price, change, value, color = "#10b981",
    onClick, session, layoutId, onEdit, onDelete
}) => {
    const [liveData, setLiveData] = useState<{ currentPrice: number; change: number; changePercent: number } | null>(null);
    const [sparkData, setSparkData] = useState<number[]>([]);
    const [showMenu, setShowMenu] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);

    const displayPrice = liveData?.currentPrice ?? price;
    const displayValue = liveData ? (liveData.currentPrice * shares) : value;
    const displayChange = liveData?.changePercent ?? change;
    const isPositive = displayChange >= 0;

    useEffect(() => {
        const fetchSparkline = async () => {
            if (!ticker) return;
            try {
                const data = await agentService.getStockData(ticker.toUpperCase(), session, '1d');

                const values = data.candles.map(c => c.value);
                const slice = values.slice(-24);
                setSparkData(slice.length > 0 ? slice : values);
                setLiveData({
                    currentPrice: data.currentPrice,
                    change: data.change,
                    changePercent: data.changePercent
                });
            } catch (e) {
                console.error("Sparkline fetch failed", e);
            }
        };
        void fetchSparkline();
    }, [ticker, session]);

    // Close menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
                setShowMenu(false);
            }
        };
        if (showMenu) document.addEventListener('mousedown', handleClickOutside);
        return () => { document.removeEventListener('mousedown', handleClickOutside); };
    }, [showMenu]);

    const normalizedBars = React.useMemo(() => {
        if (sparkData.length === 0) return Array.from({ length: 20 }).map(() => 50);
        const min = Math.min(...sparkData);
        const max = Math.max(...sparkData);
        const range = max - min || 1;
        return sparkData.map(val => ((val - min) / range) * 80 + 10);
    }, [sparkData]);

    const handleMenuClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        setShowMenu(!showMenu);
    };

    const handleEdit = (e: React.MouseEvent) => {
        e.stopPropagation();
        setShowMenu(false);
        onEdit?.(ticker);
    };

    const handleDelete = (e: React.MouseEvent) => {
        e.stopPropagation();
        setShowMenu(false);
        onDelete?.(ticker);
    };

    return (
        <motion.button
            layoutId={layoutId}
            type="button"
            onClick={onClick}
            className="relative w-80 h-48 rounded-3xl overflow-hidden glass-card border border-white/10 group hover:border-primary/30 transition-all duration-300 flex-shrink-0 text-left bg-black/40 backdrop-blur-xl"
        >
            {/* Background Gradient Blob */}
            <div
                className="absolute -top-10 -right-10 w-32 h-32 rounded-full blur-3xl opacity-10 pointer-events-none transition-all group-hover:opacity-30"
                style={{ backgroundColor: color }}
            />

            {/* Three-Dots Menu */}
            <div className="absolute top-4 right-4 z-20" ref={menuRef}>
                <button
                    type="button"
                    onClick={handleMenuClick}
                    className="p-1.5 rounded-lg bg-white/5 hover:bg-white/15 transition-colors opacity-0 group-hover:opacity-100"
                >
                    <MoreVertical className="w-4 h-4 text-slate-400" />
                </button>

                <AnimatePresence>
                    {showMenu && (
                        <motion.div
                            initial={{ opacity: 0, y: -5, scale: 0.95 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            exit={{ opacity: 0, y: -5, scale: 0.95 }}
                            transition={{ duration: 0.15 }}
                            className="absolute right-0 mt-1 w-36 bg-slate-900/95 backdrop-blur-lg rounded-xl border border-white/10 shadow-2xl overflow-hidden"
                        >
                            <button
                                type="button"
                                onClick={handleEdit}
                                className="w-full px-3 py-2.5 flex items-center gap-2 text-sm text-slate-300 hover:bg-white/10 hover:text-white transition-colors"
                            >
                                <Pencil className="w-4 h-4" />
                                Edit Shares
                            </button>
                            <button
                                type="button"
                                onClick={handleDelete}
                                className="w-full px-3 py-2.5 flex items-center gap-2 text-sm text-red-400 hover:bg-red-500/20 hover:text-red-300 transition-colors"
                            >
                                <Trash2 className="w-4 h-4" />
                                Delete
                            </button>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            <div className="relative z-10 p-6 h-full flex flex-col justify-between">
                {/* Header */}
                <div className="flex justify-between items-start">
                    <div className="flex items-center gap-3 min-w-0">
                        <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center font-bold text-white border border-white/10 text-xs flex-shrink-0">
                            {ticker.slice(0, 4)}
                        </div>
                        <div className="min-w-0">
                            <div className="text-white font-bold tracking-wide truncate max-w-[140px]">{name}</div>
                            <div className="flex items-center gap-2 text-xs text-slate-400 font-mono">
                                <span>{shares} SHARES</span>
                                <span className="text-slate-600">•</span>
                                <span>${displayPrice.toLocaleString()}</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Graph (Sparkline) */}
                <div className="flex-1 flex items-center py-2 gap-[2px]">
                    <div className="w-full h-10 flex items-end gap-[3px] opacity-80">
                        {normalizedBars.map((height, i) => (
                            <div
                                key={i}
                                className="w-full rounded-t-sm transition-all duration-500"
                                style={{
                                    height: `${height.toFixed(1)}%`,
                                    backgroundColor: isPositive ? color : '#f43f5e',
                                    opacity: 0.6 + (i / normalizedBars.length) * 0.4
                                }}
                            />
                        ))}
                    </div>
                </div>

                {/* Footer Metrics */}
                <div className="flex justify-between items-end">
                    <div>
                        <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">Current Value</div>
                        <div className="text-2xl font-serif font-bold text-white">
                            ${displayValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                        </div>
                    </div>
                    <div className={`flex items-center gap-1 text-sm font-medium ${isPositive ? 'text-emerald-400' : 'text-red-400'} bg-white/5 px-2 py-1 rounded-lg border border-white/5`}>
                        {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                        {displayChange > 0 ? '+' : ''}{displayChange.toFixed(2)}%
                    </div>
                </div>
            </div>
        </motion.button>
    );
};

export default GlassCard;
