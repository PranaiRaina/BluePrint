import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, RefreshCcw, ChevronDown } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import type { Session } from '@supabase/supabase-js';
import { agentService } from '../../services/agent';

interface StockData {
    ticker: string;
    currentPrice: number;
    change: number;
    changePercent: number;
    high: number;
    low: number;
    open: number;
    previousClose: number;
    candles: { time: string; value: number }[];
}

interface StockAnalyticsViewProps {
    session: Session;
    tickers: string[];
}

const StockAnalyticsView: React.FC<StockAnalyticsViewProps> = ({ session, tickers }) => {
    const [selectedTicker, setSelectedTicker] = useState<string>(tickers[0] || '');
    const [stockData, setStockData] = useState<StockData | null>(null);
    const [loading, setLoading] = useState(false);
    const [dropdownOpen, setDropdownOpen] = useState(false);

    // Fetch stock data when ticker changes
    useEffect(() => {
        const fetchData = async () => {
            if (!selectedTicker) return;
            setLoading(true);
            try {
                const data = await agentService.getStockData(selectedTicker, session);
                setStockData(data);
            } catch (error) {
                console.error('Failed to fetch stock data:', error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [selectedTicker, session]);

    // Update selected ticker when tickers prop changes
    useEffect(() => {
        if (tickers.length > 0 && !tickers.includes(selectedTicker)) {
            setSelectedTicker(tickers[0]);
        }
    }, [tickers]);

    const isPositive = (stockData?.changePercent || 0) >= 0;

    // Empty state when no tickers available
    if (tickers.length === 0) {
        return (
            <div className="w-full max-w-5xl mx-auto pt-10 px-4">
                <div className="flex justify-between items-end mb-8">
                    <div>
                        <h1 className="text-3xl font-bold text-white mb-2">Stock Analytics</h1>
                        <p className="text-text-secondary">Real-time price visualization for your queried stocks.</p>
                    </div>
                </div>
                <div className="glass-card p-12 h-96 w-full flex flex-col items-center justify-center text-center">
                    <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-6">
                        <TrendingUp className="w-8 h-8 text-text-secondary" />
                    </div>
                    <h2 className="text-xl font-bold text-white mb-2">No stocks to display</h2>
                    <p className="text-text-secondary max-w-md">
                        Ask about stocks in the <span className="text-primary font-semibold">Home</span> tab to see their charts here.
                        <br />
                        <span className="text-sm mt-2 block opacity-75">Try: "Compare NVDA and AAPL" or "Analyze TSLA stock"</span>
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="w-full max-w-5xl mx-auto pt-10 px-4">
            {/* Header */}
            <div className="flex justify-between items-end mb-8">
                <div>
                    <h1 className="text-3xl font-bold text-white mb-2">Stock Analytics</h1>
                    <p className="text-text-secondary">Real-time price visualization for your queried stocks.</p>
                </div>
                <button
                    onClick={() => setSelectedTicker(selectedTicker)}
                    className="neon-button flex items-center gap-2 text-sm"
                >
                    <RefreshCcw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                    Refresh
                </button>
            </div>

            {/* Ticker Dropdown */}
            <div className="mb-6 relative">
                <button
                    onClick={() => setDropdownOpen(!dropdownOpen)}
                    className="glass-card px-4 py-3 flex items-center justify-between w-64 hover:border-primary/50 transition-colors"
                >
                    <span className="text-white font-bold">{selectedTicker}</span>
                    <ChevronDown className={`w-4 h-4 text-text-secondary transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
                </button>
                {dropdownOpen && (
                    <div className="absolute top-full left-0 mt-2 w-64 glass-card border border-white/10 rounded-xl overflow-hidden z-20">
                        {tickers.map((ticker) => (
                            <button
                                key={ticker}
                                onClick={() => {
                                    setSelectedTicker(ticker);
                                    setDropdownOpen(false);
                                }}
                                className={`w-full px-4 py-3 text-left hover:bg-white/5 transition-colors ${ticker === selectedTicker ? 'text-primary bg-primary/10' : 'text-white'
                                    }`}
                            >
                                {ticker}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            {/* Stock Info Card */}
            {stockData && (
                <div className="glass-card p-6 mb-6 flex justify-between items-center">
                    <div>
                        <h2 className="text-2xl font-bold text-white">{stockData.ticker}</h2>
                        <span className="text-xs text-text-secondary">NASDAQ</span>
                    </div>
                    <div className="text-right">
                        <div className="text-3xl font-mono text-white">${stockData.currentPrice.toFixed(2)}</div>
                        <div className={`text-lg font-bold flex items-center justify-end gap-1 ${isPositive ? 'text-primary' : 'text-red-400'}`}>
                            {isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                            {isPositive ? '+' : ''}{stockData.changePercent.toFixed(2)}%
                        </div>
                    </div>
                </div>
            )}

            {/* Chart */}
            <div className="glass-card p-6 h-96 w-full">
                {loading ? (
                    <div className="w-full h-full flex items-center justify-center">
                        <div className="text-text-secondary animate-pulse">Loading chart data...</div>
                    </div>
                ) : stockData?.candles && stockData.candles.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={stockData.candles}>
                            <defs>
                                <linearGradient id="colorStock" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor={isPositive ? "#10B981" : "#EF4444"} stopOpacity={0.3} />
                                    <stop offset="95%" stopColor={isPositive ? "#10B981" : "#EF4444"} stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
                            <XAxis dataKey="time" stroke="#94A3B8" fontSize={12} tickLine={false} axisLine={false} />
                            <YAxis domain={['auto', 'auto']} stroke="#94A3B8" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(val) => `$${val}`} />
                            <Tooltip
                                contentStyle={{ backgroundColor: '#1E293B', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                                itemStyle={{ color: '#fff' }}
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
                    <div className="w-full h-full flex items-center justify-center">
                        <div className="text-text-secondary">No chart data available</div>
                    </div>
                )}
            </div>

            {/* Stats Row */}
            {stockData && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
                    {[
                        { label: 'Open', value: `$${stockData.open.toFixed(2)}` },
                        { label: 'High', value: `$${stockData.high.toFixed(2)}` },
                        { label: 'Low', value: `$${stockData.low.toFixed(2)}` },
                        { label: 'Prev Close', value: `$${stockData.previousClose.toFixed(2)}` },
                    ].map((stat, i) => (
                        <div key={i} className="glass-card p-4 text-center">
                            <div className="text-xs text-text-secondary uppercase tracking-wider">{stat.label}</div>
                            <div className="text-lg font-mono text-white mt-1">{stat.value}</div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default StockAnalyticsView;
