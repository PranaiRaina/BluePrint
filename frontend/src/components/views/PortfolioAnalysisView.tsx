import React, { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import { ArrowLeft, TrendingUp, TrendingDown, Wallet, PieChart, BarChart3, Sparkles, Loader2 } from 'lucide-react';
import { PieChart as RechartsPie, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import type { Session } from '@supabase/supabase-js';
import { agentService } from '../../services/agent';

interface Holding {
    id?: string;
    ticker?: string;
    asset_name?: string;
    quantity?: number;
    price?: number;
    buy_date?: string;
}

interface LiveData {
    ticker: string;
    currentPrice: number;
    change: number;
    changePercent: number;
}

interface PortfolioAnalysisViewProps {
    session: Session;
    onBack: () => void;
}

const COLORS = ['#3b82f6', '#10b981', '#0ea5e9', '#f59e0b', '#ec4899', '#8b5cf6', '#ef4444', '#14b8a6'];

const PortfolioAnalysisView: React.FC<PortfolioAnalysisViewProps> = ({ session, onBack }) => {
    const [holdings, setHoldings] = useState<Holding[]>([]);
    const [liveData, setLiveData] = useState<Map<string, LiveData>>(new Map());
    const [loading, setLoading] = useState(true);

    // Fetch user's holdings from API
    useEffect(() => {
        const fetchHoldings = async () => {
            try {
                const token = session.access_token;
                const res = await fetch('http://localhost:8001/v1/portfolio/holdings', {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (res.ok) {
                    const response = await res.json() as { items?: Holding[] } | Holding[];
                    // Handle both formats: { items: [...] } or direct array
                    const data = Array.isArray(response) ? response : (response.items ?? []);
                    // Aggregate by ticker
                    const aggregated = new Map<string, Holding>();
                    for (const h of data) {
                        const key = (h.ticker ?? '').toUpperCase();
                        if (!key) continue;
                        if (aggregated.has(key)) {
                            const existing = aggregated.get(key);
                            if (existing) {
                                const newQty = (existing.quantity ?? 0) + (h.quantity ?? 0);
                                const existingTotal = (existing.quantity ?? 0) * (existing.price ?? 0);
                                const newTotal = (h.quantity ?? 0) * (h.price ?? 0);
                                existing.quantity = newQty;
                                existing.price = newQty > 0 ? (existingTotal + newTotal) / newQty : 0;
                            }
                        } else {
                            aggregated.set(key, { ...h, ticker: key });
                        }
                    }
                    setHoldings(Array.from(aggregated.values()));
                }
            } catch (e) {
                console.error('Failed to fetch holdings:', e);
            }
        };
        void fetchHoldings();
    }, [session]);

    // Fetch live prices for all holdings IN PARALLEL for speed
    useEffect(() => {
        if (holdings.length === 0) return;

        const fetchLivePrices = async () => {
            setLoading(true);
            const dataMap = new Map<string, LiveData>();

            // Fetch all prices in parallel for speed
            const promises = holdings.map(async (h) => {
                if (!h.ticker) return null;
                try {
                    const data = await agentService.getStockData(h.ticker.toUpperCase(), session, '1d');
                    // Data is typed as always defined by agentService
                    return {
                        ticker: h.ticker.toUpperCase(),
                        currentPrice: data.currentPrice,
                        change: data.change,
                        changePercent: data.changePercent
                    };
                } catch (e) {
                    console.error(`Failed to fetch ${h.ticker}:`, e);
                }
                return null;
            });

            const results = await Promise.all(promises);
            for (const r of results) {
                if (r) dataMap.set(r.ticker, r);
            }

            setLiveData(dataMap);
            setLoading(false);
        };

        void fetchLivePrices();
    }, [holdings, session]);

    // Calculate portfolio metrics
    const metrics = useMemo(() => {
        let totalCostBasis = 0;
        let totalCurrentValue = 0;

        const holdingDetails = holdings.map((h, i) => {
            const qty = h.quantity ?? 0;
            const avgPrice = h.price ?? 0;
            const costBasis = qty * avgPrice;
            const live = liveData.get((h.ticker ?? '').toUpperCase());
            const currentPrice = live?.currentPrice ?? avgPrice;
            const currentValue = qty * currentPrice;
            const pnl = currentValue - costBasis;
            const pnlPercent = costBasis > 0 ? (pnl / costBasis) * 100 : 0;

            totalCostBasis += costBasis;
            totalCurrentValue += currentValue;

            return {
                ticker: h.ticker?.toUpperCase() ?? 'N/A',
                name: h.asset_name ?? h.ticker ?? 'Unknown',
                shares: qty,
                avgPrice,
                costBasis,
                currentPrice,
                currentValue,
                pnl,
                pnlPercent,
                dayChange: live?.changePercent ?? 0,
                color: COLORS[i % COLORS.length]
            };
        });

        const totalPnL = totalCurrentValue - totalCostBasis;
        const totalPnLPercent = totalCostBasis > 0 ? (totalPnL / totalCostBasis) * 100 : 0;

        // Calculate weights
        const holdingsWithWeight = holdingDetails.map(h => ({
            ...h,
            weight: totalCurrentValue > 0 ? (h.currentValue / totalCurrentValue) * 100 : 0
        }));

        // Sort by value for insights
        const sorted = [...holdingsWithWeight].sort((a, b) => b.currentValue - a.currentValue);

        return {
            holdings: holdingsWithWeight,
            totalCostBasis,
            totalCurrentValue,
            totalPnL,
            totalPnLPercent,
            numHoldings: holdings.length,
            largestPosition: sorted[0] as typeof sorted[0] | undefined,
            bestPerformer: [...holdingsWithWeight].sort((a, b) => b.pnlPercent - a.pnlPercent)[0] as typeof sorted[0] | undefined,
            worstPerformer: [...holdingsWithWeight].sort((a, b) => a.pnlPercent - b.pnlPercent)[0] as typeof sorted[0] | undefined
        };
    }, [holdings, liveData]);

    // Pie chart data
    const pieData = metrics.holdings.map(h => ({
        name: h.ticker,
        value: h.currentValue,
        color: h.color
    }));

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="w-full h-full overflow-y-auto pb-8"
        >
            <div className="max-w-6xl mx-auto px-6 py-8">
                {/* Header */}
                <div className="flex items-center gap-4 mb-8">
                    <button
                        type="button"
                        onClick={onBack}
                        className="p-2 rounded-xl bg-white/5 hover:bg-white/10 transition-colors"
                    >
                        <ArrowLeft className="w-5 h-5 text-slate-400" />
                    </button>
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-xl bg-blue-500/10">
                            <BarChart3 className="w-6 h-6 text-blue-400" />
                        </div>
                        <h1 className="text-2xl font-bold text-white">Portfolio Analysis</h1>
                    </div>
                    {loading && (
                        <div className="flex items-center gap-2 text-slate-400 text-sm ml-auto">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Loading live prices...
                        </div>
                    )}
                </div>

                {holdings.length === 0 && !loading ? (
                    <div className="text-center py-20 text-slate-400">
                        <BarChart3 className="w-12 h-12 mx-auto mb-4 opacity-50" />
                        <p>No holdings found. Add assets to your portfolio to see analytics.</p>
                    </div>
                ) : (
                    <div className="space-y-6">
                        {/* Overview Stats */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div className="bg-white/5 rounded-xl p-5 border border-white/5">
                                <div className="flex items-center gap-2 text-slate-400 text-sm mb-2">
                                    <Wallet className="w-4 h-4" />
                                    Total Value
                                </div>
                                <div className="text-2xl font-bold text-white">
                                    ${metrics.totalCurrentValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                                </div>
                            </div>

                            <div className="bg-white/5 rounded-xl p-5 border border-white/5">
                                <div className="flex items-center gap-2 text-slate-400 text-sm mb-2">
                                    {metrics.totalPnL >= 0 ? <TrendingUp className="w-4 h-4 text-emerald-400" /> : <TrendingDown className="w-4 h-4 text-red-400" />}
                                    Total P&L
                                </div>
                                <div className={`text-2xl font-bold ${metrics.totalPnL >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                    {metrics.totalPnL >= 0 ? '+' : ''}${metrics.totalPnL.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                                </div>
                                <div className={`text-sm ${metrics.totalPnL >= 0 ? 'text-emerald-400/70' : 'text-red-400/70'}`}>
                                    {metrics.totalPnL >= 0 ? '+' : ''}{metrics.totalPnLPercent.toFixed(2)}%
                                </div>
                            </div>

                            <div className="bg-white/5 rounded-xl p-5 border border-white/5">
                                <div className="text-slate-400 text-sm mb-2">Cost Basis</div>
                                <div className="text-2xl font-bold text-white">
                                    ${metrics.totalCostBasis.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                                </div>
                            </div>

                            <div className="bg-white/5 rounded-xl p-5 border border-white/5">
                                <div className="text-slate-400 text-sm mb-2">Holdings</div>
                                <div className="text-2xl font-bold text-white">{metrics.numHoldings}</div>
                            </div>
                        </div>

                        {/* Chart + Insights Row */}
                        <div className="grid md:grid-cols-2 gap-6">
                            {/* Donut Chart */}
                            <div className="bg-white/5 rounded-xl p-6 border border-white/5">
                                <div className="flex items-center gap-2 text-white font-semibold mb-4">
                                    <PieChart className="w-4 h-4 text-blue-400" />
                                    Allocation
                                </div>
                                <div className="h-48">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <RechartsPie>
                                            <Pie
                                                data={pieData}
                                                cx="50%"
                                                cy="50%"
                                                innerRadius={50}
                                                outerRadius={80}
                                                paddingAngle={2}
                                                dataKey="value"
                                            >
                                                {pieData.map((entry, index) => (
                                                    <Cell key={`cell-${String(index)}`} fill={entry.color} />
                                                ))}
                                            </Pie>
                                            <Tooltip
                                                contentStyle={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px' }}
                                                formatter={(value: number) => [`$${value.toLocaleString()}`, 'Value']}
                                            />
                                        </RechartsPie>
                                    </ResponsiveContainer>
                                </div>
                                {/* Legend */}
                                <div className="flex flex-wrap gap-3 mt-4 justify-center">
                                    {metrics.holdings.map(h => (
                                        <div key={h.ticker} className="flex items-center gap-2 text-xs text-slate-300">
                                            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: h.color }} />
                                            {h.ticker} ({h.weight.toFixed(1)}%)
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Key Insights */}
                            <div className="bg-white/5 rounded-xl p-6 border border-white/5">
                                <div className="flex items-center gap-2 text-white font-semibold mb-4">
                                    <Sparkles className="w-4 h-4 text-amber-400" />
                                    Key Insights
                                </div>
                                <div className="space-y-4">
                                    {metrics.largestPosition && (
                                        <div className="bg-white/5 rounded-lg p-4">
                                            <div className="text-slate-400 text-xs uppercase tracking-wider mb-1">Largest Position</div>
                                            <div className="text-white font-semibold">{metrics.largestPosition.ticker}</div>
                                            <div className="text-slate-300 text-sm">{metrics.largestPosition.weight.toFixed(1)}% of portfolio</div>
                                        </div>
                                    )}
                                    {metrics.bestPerformer && (
                                        <div className="bg-emerald-500/10 rounded-lg p-4 border border-emerald-500/20">
                                            <div className="text-emerald-400 text-xs uppercase tracking-wider mb-1">Best Performer</div>
                                            <div className="text-white font-semibold">{metrics.bestPerformer.ticker}</div>
                                            <div className="text-emerald-400 text-sm">+{metrics.bestPerformer.pnlPercent.toFixed(2)}%</div>
                                        </div>
                                    )}
                                    {/* Worst Performer Card */}
                                    {metrics.worstPerformer && metrics.worstPerformer.pnlPercent < 0 ? (
                                        <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
                                            <div className="text-red-400 text-xs uppercase tracking-wider mb-1">Underperformer</div>
                                            <div className="text-white font-semibold">{metrics.worstPerformer.ticker}</div>
                                            <div className="text-red-400 text-sm">{metrics.worstPerformer.pnlPercent.toFixed(2)}%</div>
                                        </div>
                                    ) : null}
                                </div>
                            </div>
                        </div>

                        {/* Performance Table */}
                        <div className="bg-white/5 rounded-xl border border-white/5 overflow-hidden">
                            <div className="px-6 py-4 border-b border-white/5">
                                <div className="text-white font-semibold">Performance by Holding</div>
                            </div>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="text-slate-400 text-xs uppercase tracking-wider border-b border-white/5">
                                            <th className="text-left px-6 py-3">Ticker</th>
                                            <th className="text-right px-6 py-3">Shares</th>
                                            <th className="text-right px-6 py-3">Avg Cost</th>
                                            <th className="text-right px-6 py-3">Current</th>
                                            <th className="text-right px-6 py-3">Value</th>
                                            <th className="text-right px-6 py-3">P&L</th>
                                            <th className="text-right px-6 py-3">Weight</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {metrics.holdings.map(h => (
                                            <tr key={h.ticker} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                                                <td className="px-6 py-4">
                                                    <div className="flex items-center gap-3">
                                                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: h.color }} />
                                                        <span className="text-white font-medium">{h.ticker}</span>
                                                    </div>
                                                </td>
                                                <td className="text-right px-6 py-4 text-slate-300">{h.shares}</td>
                                                <td className="text-right px-6 py-4 text-slate-300">${h.avgPrice.toFixed(2)}</td>
                                                <td className="text-right px-6 py-4 text-white">${h.currentPrice.toFixed(2)}</td>
                                                <td className="text-right px-6 py-4 text-white font-medium">${h.currentValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                                                <td className={`text-right px-6 py-4 font-medium ${h.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                                    {h.pnl >= 0 ? '+' : ''}${h.pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                                                    <span className="text-xs ml-1">({h.pnl >= 0 ? '+' : ''}{h.pnlPercent.toFixed(1)}%)</span>
                                                </td>
                                                <td className="text-right px-6 py-4 text-slate-300">{h.weight.toFixed(1)}%</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </motion.div >
    );
};

export default PortfolioAnalysisView;
