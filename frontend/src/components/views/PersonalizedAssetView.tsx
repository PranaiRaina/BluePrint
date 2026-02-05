import React, { useState, useEffect } from 'react';
import { AreaChart, Area, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { TrendingUp, TrendingDown, DollarSign, Calendar, Target, AlertTriangle, PieChart, Zap } from 'lucide-react';
import type { Session } from '@supabase/supabase-js';
import { agentService, type StockData } from '../../services/agent';

interface PersonalizedAssetViewProps {
    session: Session;
    ticker: string;
    quantity: number;
    avgPrice: number;
    buyDate?: string;
    totalPortfolioValue?: number;
    onClose?: () => void;
}

const PersonalizedAssetView: React.FC<PersonalizedAssetViewProps> = ({
    session,
    ticker,
    quantity,
    avgPrice,
    buyDate,
    totalPortfolioValue = 0
}) => {
    const [stockData, setStockData] = useState<StockData | null>(null);
    const [loading, setLoading] = useState(true);
    const [hoverData, setHoverData] = useState<{ value: number; label?: string } | null>(null);

    useEffect(() => {
        const fetchData = async () => {
            if (!ticker) return;
            setLoading(true);
            try {
                const data = await agentService.getStockData(ticker, session, '1y', buyDate);
                setStockData(data);
            } catch (error) {
                console.error('Failed to fetch stock data:', error);
            } finally {
                setLoading(false);
            }
        };
        void fetchData();
    }, [ticker, session, buyDate]);

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center text-slate-400 gap-2">
                <div className="w-4 h-4 rounded-full border-2 border-primary border-t-transparent animate-spin" />
                Loading intelligence...
            </div>
        );
    }

    if (!stockData) return <div className="p-8 text-center text-slate-500">Asset data unavailable</div>;

    // --- DYNAMIC CALCULATIONS ---
    const activePrice = hoverData?.value ?? stockData.currentPrice;

    // Financials based on ACTIVE Price (Hover or Current)
    const currentVal = quantity * activePrice;
    const costBasis = quantity * avgPrice;
    const totalReturn = currentVal - costBasis;
    const returnPercent = costBasis !== 0 ? (totalReturn / costBasis) * 100 : 0;
    const isPositive = totalReturn >= 0;

    const weightPercent = totalPortfolioValue > 0 ? (costBasis / totalPortfolioValue) * 100 : 0;
    const isConcentrated = weightPercent > 20;

    const dividendYield = stockData.metrics?.dividendYield ?? 0;
    const estAnnualIncome = currentVal * (dividendYield / 100);
    const hasDividends = estAnnualIncome > 0;

    const daysHeld = buyDate
        ? Math.floor((new Date().getTime() - new Date(buyDate).getTime()) / (1000 * 60 * 60 * 24))
        : 0;

    const todaysReturn = stockData.change * quantity; // Always today's return
    const isTodayPositive = todaysReturn >= 0;

    return (
        <div className="w-full h-full flex flex-col bg-[#0f172a] text-white overflow-hidden">
            {/* Header: Compact & Dynamic */}
            <div className="flex justify-between items-start px-6 pt-6 pb-2">
                <div>
                    <div className="flex items-center gap-2">
                        <h1 className="text-3xl font-bold tracking-tight text-white">{ticker}</h1>
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-white/5 border border-white/10 text-slate-400">NASDAQ</span>
                    </div>
                    <p className="text-base text-slate-400 font-light">{stockData.name ?? ticker}</p>
                </div>
                <div className="text-right">
                    <div className="text-4xl font-mono font-bold tracking-tight">${activePrice.toFixed(2)}</div>
                    <div className={`text-lg font-medium flex items-center justify-end gap-2 ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                        <span>{isPositive ? '+' : ''}${totalReturn.toLocaleString(undefined, { maximumFractionDigits: 0 })} ({returnPercent.toFixed(2)}%)</span>
                    </div>
                    {hoverData && <div className="text-xs text-slate-500 font-mono mt-1">At: {hoverData.label}</div>}
                </div>
            </div>

            {/* Smart Alert Banner (Compact) */}
            {isConcentrated && (
                <div className="mx-6 mt-2 mb-2 px-3 py-2 bg-amber-500/10 border border-amber-500/20 rounded flex items-center gap-2 text-amber-200 text-sm">
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                    <span className="font-medium">Concentration Risk:</span>
                    <span className="text-amber-200/80">{weightPercent.toFixed(1)}% of portfolio.</span>
                </div>
            )}

            {/* Main Graph: Interactive - Fixed Height to ensure render */}
            <div className="relative w-full h-[350px] border-y border-white/5 bg-gradient-to-b from-white/[0.02] to-transparent mb-4">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                        data={stockData.candles}
                        margin={{ top: 10, right: 0, left: 0, bottom: 0 }}
                        onMouseMove={(e) => {
                            if (e.activePayload && e.activePayload[0]) {
                                const payload = e.activePayload[0].payload as { value: number; time: string };
                                setHoverData({ value: payload.value, label: payload.time });
                            }
                        }}
                        onMouseLeave={() => setHoverData(null)}
                    >
                        <defs>
                            <linearGradient id={`gradientColor-${ticker}`} x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor={isPositive ? '#10b981' : '#f43f5e'} stopOpacity={0.2} />
                                <stop offset="95%" stopColor={isPositive ? '#10b981' : '#f43f5e'} stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <Tooltip
                            content={<></>} // Custom handling via header, hide default tooltip
                            cursor={{ stroke: '#94a3b8', strokeWidth: 1, strokeDasharray: '4 4' }}
                        />
                        <ReferenceLine y={avgPrice} stroke="#94a3b8" strokeDasharray="3 3" opacity={0.3} />
                        <Area
                            type="monotone"
                            dataKey="value"
                            stroke={isPositive ? '#10b981' : '#f43f5e'}
                            strokeWidth={2}
                            fill={`url(#gradientColor-${ticker})`}
                            isAnimationActive={false} // Disable animation for clearer scrubbing
                        />
                        <YAxis hide={true} domain={['dataMin - 2', 'dataMax + 2']} />
                    </AreaChart>
                </ResponsiveContainer>

                {/* Avg Cost Label */}
                {!hoverData && (
                    <div
                        className="absolute left-4 top-1/2 -translate-y-1/2 flex items-center pointer-events-none"
                    >
                        <span className="bg-[#0f172a]/80 backdrop-blur border border-white/10 text-slate-400 text-[10px] px-1.5 py-0.5 rounded">Avg: ${avgPrice.toFixed(2)}</span>
                    </div>
                )}
            </div>

            {/* Metrics Grid - Tighter Layout */}
            <div className="px-6 pb-8 grid grid-cols-2 md:grid-cols-4 gap-6">

                {/* Col 1 */}
                <div>
                    <div className="flex items-center gap-1.5 text-slate-500 text-[10px] uppercase tracking-wider mb-1">
                        <Target className="w-3 h-3" /> Cost Basis
                    </div>
                    <div className="text-xl font-light text-white">${costBasis.toLocaleString()}</div>
                    <div className="text-xs text-slate-600">{quantity} shares</div>
                </div>

                {/* Col 2 */}
                <div>
                    <div className="flex items-center gap-1.5 text-slate-500 text-[10px] uppercase tracking-wider mb-1">
                        <DollarSign className="w-3 h-3" /> Market Value
                    </div>
                    <div className="text-xl font-light text-white">${currentVal.toLocaleString()}</div>
                    {/* Only show today's return when not hovering, to avoid confusion */}
                    {!hoverData && (
                        <div className={`text-xs ${isTodayPositive ? 'text-emerald-500' : 'text-rose-500'}`}>
                            {isTodayPositive ? '+' : ''}${todaysReturn.toFixed(0)} Today
                        </div>
                    )}
                </div>

                {/* Col 3 */}
                <div>
                    <div className="flex items-center gap-1.5 text-slate-500 text-[10px] uppercase tracking-wider mb-1">
                        <PieChart className="w-3 h-3" /> Weight
                    </div>
                    <div className="text-xl font-light text-white">{weightPercent.toFixed(1)}%</div>
                    <div className="text-xs text-slate-600">
                        {weightPercent > 15 ? 'Heavy' : 'Balanced'}
                    </div>
                </div>

                {/* Col 4 */}
                <div>
                    {hasDividends ? (
                        <div>
                            <div className="flex items-center gap-1.5 text-slate-500 text-[10px] uppercase tracking-wider mb-1">
                                <Zap className="w-3 h-3 text-amber-400" /> Est. Income
                            </div>
                            <div className="text-xl font-light text-amber-100">${estAnnualIncome.toFixed(0)}</div>
                            <div className="text-xs text-amber-500/60">{dividendYield.toFixed(2)}% Yield</div>
                        </div>
                    ) : (
                        <div>
                            <div className="flex items-center gap-1.5 text-slate-500 text-[10px] uppercase tracking-wider mb-1">
                                <Calendar className="w-3 h-3" /> Days Held
                            </div>
                            <div className="text-xl font-light text-white">{daysHeld}</div>
                            <div className="text-xs text-slate-600">Long-term</div>
                        </div>
                    )}
                </div>

            </div>

            {/* Texture Overlay */}
            <div className="absolute inset-0 pointer-events-none opacity-[0.03]" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")` }}></div>
        </div>
    );
};

export default PersonalizedAssetView;
