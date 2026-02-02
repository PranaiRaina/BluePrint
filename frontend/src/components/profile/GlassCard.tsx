import React from 'react';
import { TrendingUp, TrendingDown, MoreHorizontal } from 'lucide-react';

export interface GlassCardProps {
    ticker: string;
    name: string;
    shares: number;
    price: number;
    change: number; // Percent change
    value: number;
    color?: string; // Hex or tailwind class
}

const GlassCard: React.FC<GlassCardProps> = ({ ticker, name, shares, price, change, value, color = "#10b981" }) => {
    const isPositive = change >= 0;

    return (
        <div className="relative w-80 h-48 rounded-3xl overflow-hidden glass-card border border-white/10 group hover:border-primary/30 transition-all duration-300 flex-shrink-0">
            {/* Background Gradient Blob */}
            <div
                className="absolute -top-10 -right-10 w-32 h-32 rounded-full blur-3xl opacity-20 pointer-events-none transition-all group-hover:opacity-40"
                style={{ backgroundColor: color }}
            />

            <div className="relative z-10 p-6 h-full flex flex-col justify-between">
                {/* Header */}
                <div className="flex justify-between items-start">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center font-bold text-white border border-white/10">
                            {ticker}
                        </div>
                        <div>
                            <div className="text-white font-bold tracking-wide">{name}</div>
                            <div className="flex items-center gap-2 text-xs text-slate-400 font-mono">
                                <span>{shares} SHARES</span>
                                <span className="text-slate-600">•</span>
                                <span>${price.toLocaleString()}</span>
                            </div>
                        </div>
                    </div>
                    <button className="text-slate-500 hover:text-white transition-colors">
                        <MoreHorizontal className="w-5 h-5" />
                    </button>
                </div>

                {/* Graph Placeholder (Sparkline) */}
                <div className="flex-1 flex items-center py-2">
                    <div className="w-full h-8 flex gap-1 items-end opacity-50">
                        {/* Fake Sparkline Bars */}
                        {Array.from({ length: 20 }).map((_, i) => (
                            <div
                                key={i}
                                className="w-full rounded-t-sm"
                                style={{
                                    height: `${(Math.random() * 80 + 20).toString()}%`,
                                    backgroundColor: isPositive ? color : '#f43f5e'
                                }}
                            />
                        ))}
                    </div>
                </div>

                {/* Footer Metrics */}
                <div className="flex justify-between items-end">
                    <div>
                        <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Current Value</div>
                        <div className="text-2xl font-serif font-bold text-white">
                            ${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                        </div>
                    </div>
                    <div className={`flex items-center gap-1 text-sm font-medium ${isPositive ? 'text-emerald-400' : 'text-red-400'} bg-white/5 px-2 py-1 rounded-lg border border-white/5`}>
                        {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                        {change > 0 ? '+' : ''}{change}%
                    </div>
                </div>
            </div>
        </div>
    );
};

export default GlassCard;
