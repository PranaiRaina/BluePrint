import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import type { Session } from '@supabase/supabase-js';
import { agentService, type StockData } from '../../services/agent';
import ArticleList from '../views/ArticleList';
import AnimatedCounter from '../ui/AnimatedCounter';

interface StockDashboardProps {
    session: Session;
    ticker: string;
    onClose?: () => void;
    embedded?: boolean; // If true, hides header/dropdown to fit in another view
    userInfo?: {
        avgPrice: number;
        quantity: number;
        buyDate?: string;
    };
}

const StockDashboard: React.FC<StockDashboardProps> = ({ session, ticker, embedded = false, userInfo }) => {
    const [stockData, setStockData] = useState<StockData | null>(null);
    const [hoverData, setHoverData] = useState<{ open: number; high: number; low: number; value: number } | null>(null);
    const [loading, setLoading] = useState(false);
    const [timeRange, setTimeRange] = useState("3m");

    // Fetch stock data
    useEffect(() => {
        const fetchData = async () => {
            if (!ticker) return;
            setLoading(true);
            try {
                const data = await agentService.getStockData(ticker, session, timeRange);
                setStockData(data);
            } catch (error) {
                console.error('Failed to fetch stock data:', error);
            } finally {
                setLoading(false);
            }
        };
        void fetchData();
    }, [ticker, session, timeRange]);

    // Calculate dynamic change
    const getDynamicChange = () => {
        if (timeRange === '1d' && stockData) {
            return {
                percent: stockData.changePercent,
                value: stockData.change
            };
        }
        if (!stockData?.candles || stockData.candles.length === 0) {
            return {
                percent: stockData?.changePercent ?? 0,
                value: stockData?.change ?? 0
            };
        }
        const firstPrice = stockData.candles[0].value;
        const currentPrice = stockData.currentPrice;
        const changeValue = currentPrice - firstPrice;
        const changePercent = (changeValue / firstPrice) * 100;
        return { percent: changePercent, value: changeValue };
    };

    const dynamicStats = getDynamicChange();
    const isPositive = dynamicStats.percent >= 0;

    // Calculate User Performance if provided
    const getUserPerformance = () => {
        if (!userInfo || !stockData) return null;
        const currentVal = userInfo.quantity * stockData.currentPrice;
        const initialVal = userInfo.quantity * userInfo.avgPrice;
        const totalReturn = currentVal - initialVal;
        const returnPercent = (totalReturn / initialVal) * 100;
        return {
            currentVal,
            totalReturn,
            returnPercent,
            isPositive: totalReturn >= 0
        };
    };

    const userPerf = getUserPerformance();

    return (
        <div className={`w-full ${embedded ? '' : 'max-w-5xl mx-auto pt-10 px-4 pb-20'}`}>
            {/* Header (Only if not embedded or if desired) */}
            {!embedded && (
                <div className="flex justify-between items-end mb-8">
                    <div>
                        <h1 className="text-3xl font-bold text-white mb-2">Stock Analytics</h1>
                        <p className="text-text-secondary">Real-time visualization</p>
                    </div>
                </div>
            )}

            {/* Stock Info Header */}
            {stockData && (
                <div className="glass-card p-6 mb-6">
                    <div className="flex justify-between items-start">
                        <div>
                            <div className="flex items-center gap-3 mb-1">
                                <h2 className="text-3xl font-bold text-white">{stockData.ticker}</h2>
                                <span className="px-2 py-0.5 rounded text-xs font-mono bg-white/10 text-slate-300">NASDAQ</span>
                            </div>
                            <p className="text-text-secondary text-sm">Apple Inc.</p>
                        </div>
                        <div className="text-right">
                            <div className="text-4xl font-mono font-bold text-white">${stockData.currentPrice.toFixed(2)}</div>
                            <div className={`text-lg font-medium flex items-center justify-end gap-2 ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                                {isPositive ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
                                <span className="flex items-center">
                                    {isPositive ? '+' : ''}
                                    <AnimatedCounter value={dynamicStats.percent} suffix="%" />
                                    <span className="text-sm opacity-70 ml-2">(${dynamicStats.value.toFixed(2)})</span>
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* User Holdings Summary (If User Info Provided) */}
                    {userPerf && userInfo && (
                        <div className="mt-6 pt-6 border-t border-white/5 grid grid-cols-3 gap-4">
                            <div>
                                <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Your Position</div>
                                <div className="text-white font-medium">
                                    {userInfo.quantity} Shares @ ${userInfo.avgPrice.toFixed(2)}
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Market Value</div>
                                <div className="text-white font-medium">
                                    ${userPerf.currentVal.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Total Return</div>
                                <div className={`font-medium ${userPerf.isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                                    {userPerf.isPositive ? '+' : ''}${userPerf.totalReturn.toFixed(2)} ({userPerf.returnPercent.toFixed(2)}%)
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Chart */}
            <div className="glass-card p-6 h-80 w-full relative mb-6">
                <div className="absolute top-4 right-6 z-10 flex gap-1 bg-black/40 backdrop-blur-md rounded-lg p-1 border border-white/5">
                    {['1d', '1w', '1m', '3m', '6m', '1y'].map((range) => (
                        <button
                            key={range}
                            onClick={() => { setTimeRange(range); }}
                            className={`px-3 py-1 rounded-md text-xs font-semibold transition-all ${timeRange === range ? 'bg-primary text-black' : 'text-slate-400 hover:text-white hover:bg-white/5'}`}
                        >
                            {range.toUpperCase()}
                        </button>
                    ))}
                </div>

                {loading ? (
                    <div className="w-full h-full flex items-center justify-center">
                        <div className="text-slate-500 animate-pulse">Loading market data...</div>
                    </div>
                ) : stockData?.candles && stockData.candles.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={stockData.candles} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
                            <defs>
                                <linearGradient id="colorStock" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor={isPositive ? "#10B981" : "#EF4444"} stopOpacity={0.3} />
                                    <stop offset="95%" stopColor={isPositive ? "#10B981" : "#EF4444"} stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.1} vertical={false} />
                            <XAxis
                                dataKey="time"
                                hide
                            />
                            <YAxis domain={['auto', 'auto']} hide />
                            <Tooltip
                                contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', boxShadow: '0 4px 20px rgba(0,0,0,0.5)' }}
                                itemStyle={{ color: '#fff' }}
                                formatter={(val: number) => [`$${val.toFixed(2)}`, 'Price']}
                                labelStyle={{ color: '#94a3b8', marginBottom: '0.5rem' }}
                            />
                            <Area
                                type="monotone"
                                dataKey="value"
                                stroke={isPositive ? "#10B981" : "#EF4444"}
                                strokeWidth={2}
                                fillOpacity={1}
                                fill="url(#colorStock)"
                            />
                        </AreaChart>
                    </ResponsiveContainer>
                ) : (
                    <div className="w-full h-full flex items-center justify-center text-slate-600">
                        No chart data available
                    </div>
                )}
            </div>

            {/* Stats Grid */}
            {stockData && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                    {[
                        { label: 'Open', value: `$${(hoverData?.open ?? stockData.open).toFixed(2)}` },
                        { label: 'High', value: `$${(hoverData?.high ?? stockData.high).toFixed(2)}` },
                        { label: 'Low', value: `$${(hoverData?.low ?? stockData.low).toFixed(2)}` },
                        { label: 'Prev Close', value: `$${stockData.previousClose.toFixed(2)}` },
                    ].map((stat, i) => (
                        <div key={i} className="glass-card p-4 text-center border border-white/5 bg-white/5">
                            <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">{stat.label}</div>
                            <div className="text-lg font-mono text-white">{stat.value}</div>
                        </div>
                    ))}
                </div>
            )}

            {/* Articles (Only if relevant for slideover) */}
            <div className="glass-card p-6">
                <h3 className="text-lg font-bold text-white mb-4">Latest News</h3>
                <ArticleList session={session} ticker={ticker} />
            </div>
        </div>
    );
};

export default StockDashboard;
