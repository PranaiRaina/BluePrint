import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, DollarSign, Activity, ShoppingCart, RefreshCw } from 'lucide-react';
import type { Session } from '@supabase/supabase-js';
import { agentService } from '../../services/agent';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

interface PaperTraderViewProps {
    session: Session;
}

const PaperTraderView: React.FC<PaperTraderViewProps> = ({ session }) => {
    // Existing State
    const [portfolios, setPortfolios] = useState<any[]>([]);
    const [activePortfolioId, setActivePortfolioId] = useState<string | null>(null);
    const [portfolioData, setPortfolioData] = useState<any>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [tradeType, setTradeType] = useState<'BUY' | 'SELL'>('BUY');
    const [tradeTicker, setTradeTicker] = useState('');
    const [tradeQty, setTradeQty] = useState(1);
    const [isTrading, setIsTrading] = useState(false);

    // New State for Backtesting & UI
    const [activeTab, setActiveTab] = useState<'TRADING' | 'BACKTEST'>('TRADING');
    const [backtestTicker, setBacktestTicker] = useState('AAPL');
    const [backtestDays, setBacktestDays] = useState(30);
    const [backtestResult, setBacktestResult] = useState<any>(null);
    const [isBacktesting, setIsBacktesting] = useState(false);
    const [simulationLogs, setSimulationLogs] = useState<string[]>([]);
    const [simulationProgress, setSimulationProgress] = useState(0);

    // Initial Load
    useEffect(() => {
        loadPortfolios();
    }, []);

    // Load details when active ID changes
    useEffect(() => {
        if (activePortfolioId) {
            loadPortfolioDetails(activePortfolioId);
            // Poll for updates every 10s
            const interval = setInterval(() => loadPortfolioDetails(activePortfolioId), 10000);
            return () => clearInterval(interval);
        }
    }, [activePortfolioId]);

    const loadPortfolios = async () => {
        setIsLoading(true);
        const data = await agentService.getPortfolios(session);
        setPortfolios(data);
        if (data.length > 0 && !activePortfolioId) {
            setActivePortfolioId(data[0].id);
        } else if (data.length === 0) {
            // Auto-create default if none
            await createDefaultPortfolio();
        }
        setIsLoading(false);
    };

    const createDefaultPortfolio = async () => {
        const newP = await agentService.createPortfolio("Main Strategy", session);
        if (newP) {
            setPortfolios([newP]);
            setActivePortfolioId(newP.id);
        }
    };

    const loadPortfolioDetails = async (id: string) => {
        const data = await agentService.getPortfolioDetails(id, session);
        if (data) setPortfolioData(data);
    };

    const handleTrade = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!activePortfolioId || !tradeTicker) return;

        setIsTrading(true);
        try {
            await agentService.executeTrade(
                activePortfolioId,
                tradeTicker.toUpperCase(),
                tradeType,
                Number(tradeQty),
                session
            );
            // Refresh data immediately
            await loadPortfolioDetails(activePortfolioId);
            setTradeTicker('');
            setTradeQty(1);
            alert("Trade Executed Successfully! 🚀");
        } catch (e: any) {
            alert(`Trade Failed: ${e.message}`);
        } finally {
            setIsTrading(false);
        }
    };

    const handleBacktest = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsBacktesting(true);
        setBacktestResult(null);
        setSimulationLogs([]);
        setSimulationProgress(0);

        try {
            const response = await fetch('http://localhost:8001/api/backtest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker: backtestTicker, days: backtestDays })
            });

            if (!response.ok) throw new Error(response.statusText);

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            if (!reader) throw new Error("No reader");

            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // Keep incomplete line

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.replace('data: ', '').trim();
                        if (dataStr === '[DONE]') break;

                        try {
                            const event = JSON.parse(dataStr);

                            if (event.type === 'log') {
                                setSimulationLogs(prev => [...prev, event.message]);
                            } else if (event.type === 'progress') {
                                const pct = (event.current / event.total) * 100;
                                setSimulationProgress(pct);
                                // Optional: Stream equity curve updates here if we want log updates
                            } else if (event.type === 'result') {
                                // Backend returns a list of results (one per trader).
                                // For now, we display the first one to avoid crashing.
                                const resultPayload = Array.isArray(event.data) ? event.data[0] : event.data;
                                setBacktestResult(resultPayload);
                            } else if (event.type === 'error') {
                                alert("Simulation Error: " + event.message);
                            }
                        } catch (e) {
                            console.error("Parse Error", e);
                        }
                    }
                }
            }

        } catch (err: any) {
            alert("Backtest Failed: " + err.message);
        } finally {
            setIsBacktesting(false);
        }
    };


    const toggleAgent = async (currentState: boolean) => {
        if (!activePortfolioId) return;
        try {
            await fetch(`http://localhost:8001/api/portfolios/${activePortfolioId}/toggle`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${session.access_token}`
                },
                body: JSON.stringify({ is_active: !currentState })
            });
            await loadPortfolioDetails(activePortfolioId);
        } catch (err: any) {
            alert("Failed to toggle agent: " + err.message);
        }
    };

    const createPortfolio = async () => {
        const name = prompt("Enter Portfolio Name:", "New Strategy");
        if (!name) return;
        try {
            await agentService.createPortfolio(name, session);
            loadPortfolios();
        } catch (err: any) {
            alert("Failed to create portfolio: " + err.message);
        }
    };

    const renamePortfolio = async (id: string, currentName: string) => {
        const newName = prompt("Enter new name:", currentName);
        if (!newName || newName === currentName) return;
        try {
            await fetch(`http://localhost:8001/api/portfolios/${id}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${session.access_token}`
                },
                body: JSON.stringify({ name: newName })
            });
            loadPortfolios();
        } catch (err: any) {
            alert("Failed to rename: " + err.message);
        }
    };

    const deletePortfolio = async (id: string) => {
        if (!confirm("Are you sure you want to delete this portfolio? This cannot be undone.")) return;
        try {
            await fetch(`http://localhost:8001/api/portfolios/${id}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${session.access_token}`
                }
            });
            setPortfolios(prev => prev.filter(p => p.id !== id));
            if (activePortfolioId === id) setActivePortfolioId(null);
        } catch (err: any) {
            alert("Failed to delete: " + err.message);
        }
    };

    // Render Loading State
    if (isLoading && portfolios.length === 0) {
        return <div className="p-10 text-center text-white/50 animate-pulse">Loading Trading System...</div>;
    }


    // Prepare Data for Render
    const overview = portfolioData?.overview || { total_equity: 0, total_value: 0, cash_balance: 0, is_active: false };
    const positions = portfolioData?.positions || [];
    const transactions = portfolioData?.transactions || [];
    const isProfitable = (overview.total_value || 0) >= 100000;

    return (
        <div className="w-full max-w-7xl mx-auto p-4 md:p-8 space-y-8 pb-32">

            {/* Header with Tabs */}
            <div className="flex flex-col md:flex-row items-center justify-between gap-4 mb-4">
                <div>
                    <h1 className="text-3xl font-serif font-bold text-white mb-2">
                        {activeTab === 'TRADING' ? 'Paper Trading' : 'Strategy Backtester'}
                    </h1>
                    <div className="flex items-center gap-2 text-sm">
                        <button
                            onClick={() => toggleAgent(overview.is_active)}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-full border transition-all ${overview.is_active
                                ? 'bg-green-500/10 border-green-500/50 text-green-400 hover:bg-green-500/20'
                                : 'bg-red-500/10 border-red-500/50 text-red-400 hover:bg-red-500/20'
                                }`}
                        >
                            <span className={`w-2 h-2 rounded-full ${overview.is_active ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></span>
                            <span className="font-mono font-bold">
                                Wolf Agent: {overview.is_active ? 'ON' : 'OFF'}
                            </span>
                        </button>
                    </div>
                </div>

                <div className="flex bg-white/5 p-1 rounded-xl">
                    <button
                        onClick={() => setActiveTab('TRADING')}
                        className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === 'TRADING' ? 'bg-primary text-black' : 'text-white/50 hover:text-white'
                            }`}
                    >
                        Live Trading
                    </button>
                    <button
                        onClick={() => setActiveTab('BACKTEST')}
                        className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === 'BACKTEST' ? 'bg-primary text-black' : 'text-white/50 hover:text-white'
                            }`}
                    >
                        Backtest
                    </button>
                </div>
            </div>

            {activeTab === 'TRADING' ? (
                /* LIVE TRADING UI */
                <div className="animate-in fade-in duration-500">
                    {/* Portfolio Selector */}
                    <div className="flex gap-2 mb-8 overflow-x-auto pb-2">
                        {portfolios.map(p => (
                            <div key={p.id} className="group relative">
                                <button
                                    onClick={() => setActivePortfolioId(p.id)}
                                    className={`px-4 py-2 pr-8 rounded-xl text-sm font-bold border transition-all whitespace-nowrap ${activePortfolioId === p.id
                                        ? 'bg-white/10 border-white/20 text-white'
                                        : 'bg-white/5 border-transparent text-white/50 hover:bg-white/10'
                                        }`}
                                >
                                    {p.name}
                                </button>
                                {/* Portfolio Actions (Hover) */}
                                {activePortfolioId === p.id && (
                                    <div className="absolute right-1 top-1/2 -translate-y-1/2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <button
                                            onClick={(e) => { e.stopPropagation(); renamePortfolio(p.id, p.name); }}
                                            className="p-1 hover:bg-white/20 rounded-md text-white/50 hover:text-white"
                                            title="Rename"
                                        >
                                            <RefreshCw className="w-3 h-3" />
                                        </button>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); deletePortfolio(p.id); }}
                                            className="p-1 hover:bg-red-500/20 rounded-md text-white/50 hover:text-red-400"
                                            title="Delete"
                                        >
                                            <TrendingDown className="w-3 h-3 rotate-45" /> {/* Use X icon if available, or this as temp */}
                                        </button>
                                    </div>
                                )}
                            </div>
                        ))}
                        <button
                            onClick={() => createPortfolio()}
                            className="px-4 py-2 rounded-xl text-sm font-bold border border-dashed border-white/20 text-white/30 hover:text-white hover:border-white/50 transition-all"
                        >
                            +
                        </button>
                    </div>

                    {/* Summary Cards */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="glass-card p-6 relative overflow-hidden group">
                            <div className="absolute top-0 right-0 p-4 opacity-50 group-hover:scale-110 transition-transform">
                                <DollarSign className="w-12 h-12 text-primary/20" />
                            </div>
                            <p className="text-sm font-medium text-white/50 mb-1">Total Equity (Net Liq)</p>
                            <h2 className="text-4xl font-mono font-bold text-white tracking-tighter">
                                ${overview.total_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </h2>
                            <div className={`mt-2 flex items-center gap-2 text-sm ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
                                {isProfitable ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                                <span>{isProfitable ? '+' : ''}${(overview.total_value - 100000).toLocaleString()} (All Time)</span>
                            </div>
                        </div>

                        <div className="glass-card p-6">
                            <p className="text-sm font-medium text-white/50 mb-1">Buying Power (Cash)</p>
                            <h2 className="text-4xl font-mono font-bold text-white tracking-tighter">
                                ${Number(overview.cash_balance).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </h2>
                        </div>
                    </div>

                    {/* Holdings Table */}
                    <div className="glass-card p-6 mt-6">
                        <div className="flex items-center justify-between mb-6">
                            <h3 className="text-xl font-bold text-white">Current Positions</h3>
                            <RefreshCw
                                className="w-4 h-4 text-white/30 hover:text-white cursor-pointer transition-colors"
                                onClick={() => activePortfolioId && loadPortfolioDetails(activePortfolioId)}
                            />
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-left border-collapse">
                                <thead>
                                    <tr className="text-xs text-white/40 border-b border-white/5 uppercase tracking-wider">
                                        <th className="pb-3 pl-2">Ticker</th>
                                        <th className="pb-3 text-right">Qty</th>
                                        <th className="pb-3 text-right">Avg Cost</th>
                                        <th className="pb-3 text-right">Price</th>
                                        <th className="pb-3 text-right">Market Value</th>
                                        <th className="pb-3 text-right">Return</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-white/5">
                                    {positions.length === 0 ? (
                                        <tr>
                                            <td colSpan={6} className="py-8 text-center text-white/20 italic">
                                                No active positions. Make a trade to start!
                                            </td>
                                        </tr>
                                    ) : (
                                        positions.map((pos: any) => (
                                            <tr key={pos.ticker} className="group hover:bg-white/5 transition-colors">
                                                <td className="py-4 pl-2 font-bold text-white">{pos.ticker}</td>
                                                <td className="py-4 text-right font-mono text-slate-300">{pos.quantity}</td>
                                                <td className="py-4 text-right font-mono text-slate-400">${Number(pos.avg_cost).toFixed(2)}</td>
                                                <td className="py-4 text-right font-mono text-white">${Number(pos.current_price).toFixed(2)}</td>
                                                <td className="py-4 text-right font-mono text-white font-bold">${Number(pos.market_value).toFixed(2)}</td>
                                                <td className={`py-4 text-right font-mono font-bold ${pos.unrealized_pl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                    {pos.unrealized_pl >= 0 ? '+' : ''}{Number(pos.unrealized_pl).toFixed(2)} ({Number(pos.unrealized_pl_percent).toFixed(2)}%)
                                                </td>
                                            </tr>
                                        ))
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* Recent Transactions */}
                    <div className="glass-card p-6 mt-6 opacity-80 hover:opacity-100 transition-opacity">
                        <h3 className="text-lg font-bold text-white mb-4">Recent Transactions</h3>
                        <div className="space-y-2">
                            {transactions.map((tx: any) => (
                                <div key={tx.id} className="py-2 border-b border-white/5 last:border-0">
                                    <div className="flex items-center justify-between text-sm">
                                        <div className="flex items-center gap-3">
                                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${tx.type === 'BUY' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                                                {tx.type}
                                            </span>
                                            <span className="text-white font-bold">{tx.ticker}</span>
                                            <span className="text-white/50 text-xs">{new Date(tx.executed_at).toLocaleString()}</span>
                                        </div>
                                        <div className="font-mono text-white/70">
                                            {tx.quantity} @ ${Number(tx.price_per_share).toFixed(2)}
                                        </div>
                                    </div>
                                    {/* Reasoning Display */}
                                    {tx.reasoning && (
                                        <div className="mt-1 ml-14 text-xs text-white/40 italic flex items-start gap-1">
                                            <span className="text-primary/40">↳</span> "{tx.reasoning}"
                                        </div>
                                    )}
                                </div>
                            ))}
                            {transactions.length === 0 && <p className="text-white/20 text-sm italic">No transactions yet.</p>}
                        </div>
                    </div>
                </div>

            ) : (
                /* BACKTEST UI */
                <div className="animate-in fade-in duration-500 space-y-6">
                    <div className="glass-card p-8 text-center bg-gradient-to-b from-white/5 to-transparent">
                        <h2 className="text-2xl font-serif text-white mb-2">Configure Simulation</h2>
                        <p className="text-white/50 mb-6">Run the "Wolf" agent on historical data to verify its strategy.</p>

                        <form onSubmit={handleBacktest} className="flex flex-col md:flex-row gap-4 max-w-2xl mx-auto">
                            <div className="flex-1">
                                <label className="block text-xs uppercase text-white/30 mb-1 ml-1">Ticker</label>
                                <input
                                    type="text"
                                    value={backtestTicker}
                                    onChange={e => setBacktestTicker(e.target.value.toUpperCase())}
                                    className="glass-input w-full px-4 py-3 text-lg font-mono font-bold"
                                    placeholder="AAPL"
                                    required
                                />
                            </div>
                            <div className="w-32">
                                <label className="block text-xs uppercase text-white/30 mb-1 ml-1">Days</label>
                                <input
                                    type="number"
                                    value={backtestDays}
                                    onChange={e => setBacktestDays(Number(e.target.value))}
                                    className="glass-input w-full px-4 py-3 text-lg font-mono"
                                    min="1"
                                    max="365"
                                    required
                                />
                            </div>
                            <button
                                type="submit"
                                disabled={isBacktesting}
                                className="px-8 py-3 mt-auto bg-primary text-black font-bold rounded-xl hover:bg-primary/90 disabled:opacity-50 transition-all"
                            >
                                {isBacktesting ? 'Running Simulation...' : 'Start Backtest'}
                            </button>
                        </form>
                    </div>

                    {/* LIVE SIMULATION TERMINAL */}
                    {(isBacktesting || simulationLogs.length > 0) && !backtestResult && (
                        <div className="glass-card p-6 font-mono text-sm bg-black/80 border-white/10">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-green-400 font-bold flex items-center gap-2">
                                    <span className="animate-pulse">_</span> Live Simulation Log
                                </h3>
                                <div className="text-xs text-white/50">{Math.round(simulationProgress)}% Complete</div>
                            </div>

                            {/* Progress Bar */}
                            <div className="w-full h-1 bg-white/10 rounded-full mb-4 overflow-hidden">
                                <div
                                    className="h-full bg-green-500 transition-all duration-300 ease-out"
                                    style={{ width: `${simulationProgress}%` }}
                                />
                            </div>

                            <div className="h-64 overflow-y-auto custom-scrollbar flex flex-col-reverse space-y-1 space-y-reverse">
                                {simulationLogs.slice().reverse().map((log, i) => (
                                    <div key={i} className={`pb-1 border-b border-white/5 last:border-0 ${log.includes(' Bought ') ? 'text-green-300' : log.includes(' Sold ') ? 'text-red-300' : 'text-white/70'}`}>
                                        <span className="text-white/30 mr-2">[{new Date().toLocaleTimeString()}]</span>
                                        {log}
                                        {/* Auto-scroll anchor */}
                                        {i === 0 && <div id="log-end" />}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {backtestResult && (
                        <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-6">
                            {backtestResult.error ? (
                                <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-xl text-red-200 text-center">
                                    ⚠️ Simulation Error: {backtestResult.error}
                                </div>
                            ) : (
                                <>
                                    {/* Key Metrics */}
                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                        <div className="glass-card p-4 text-center">
                                            <div className="text-xs text-white/50 uppercase">Final Equity</div>
                                            <div className="text-2xl font-mono font-bold text-white">
                                                ${backtestResult.final_equity.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                                            </div>
                                        </div>
                                        <div className="glass-card p-4 text-center">
                                            <div className="text-xs text-white/50 uppercase">Return</div>
                                            <div className={`text-2xl font-mono font-bold ${backtestResult.return_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                {backtestResult.return_pct.toFixed(2)}%
                                            </div>
                                        </div>
                                        <div className="glass-card p-4 text-center">
                                            <div className="text-xs text-white/50 uppercase">Trades Executed</div>
                                            <div className="text-2xl font-mono font-bold text-white">
                                                {backtestResult.trades}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Chart */}
                                    <div className="glass-card p-6 h-96">
                                        <h3 className="text-white font-bold mb-4">Equity Curve</h3>
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart data={backtestResult.equity_curve}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                                                <XAxis
                                                    dataKey="time"
                                                    stroke="#ffffff50"
                                                    fontSize={12}
                                                    tickFormatter={(val) => val.split(' ')[0]}
                                                />
                                                <YAxis
                                                    domain={['auto', 'auto']}
                                                    stroke="#ffffff50"
                                                    fontSize={12}
                                                    tickFormatter={(val) => `$${Math.round(val)}`}
                                                />
                                                <Tooltip
                                                    contentStyle={{ backgroundColor: '#000', borderColor: '#333', color: '#fff' }}
                                                    labelStyle={{ color: '#888' }}
                                                />
                                                <Line
                                                    type="monotone"
                                                    dataKey="equity"
                                                    stroke="#10b981"
                                                    strokeWidth={2}
                                                    dot={false}
                                                    activeDot={{ r: 6 }}
                                                />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>

                                    {/* Trade Log */}
                                    <div className="glass-card p-6">
                                        <h3 className="text-white font-bold mb-4">Trade Log & Reasoning</h3>
                                        <div className="space-y-3 max-h-96 overflow-y-auto pr-2 custom-scrollbar">
                                            {backtestResult.history && backtestResult.history.slice().reverse().map((tx: any, i: number) => (
                                                <div key={i} className="py-3 border-b border-white/5 last:border-0 hover:bg-white/5 px-2 rounded-lg transition-colors">
                                                    <div className="flex items-center justify-between text-sm mb-1">
                                                        <div className="flex items-center gap-3">
                                                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${tx.action === 'BUY' ? 'bg-green-500/10 text-green-400' :
                                                                    tx.action === 'SELL' ? 'bg-red-500/10 text-red-400' :
                                                                        'bg-yellow-500/10 text-yellow-400'
                                                                }`}>
                                                                {tx.action}
                                                            </span>
                                                            <span className="text-white font-mono text-xs">{tx.time}</span>
                                                        </div>
                                                        <div className="font-mono text-white/70">
                                                            {tx.qty} @ ${Number(tx.price).toFixed(2)}
                                                        </div>
                                                    </div>
                                                    {tx.reasoning && (
                                                        <div className="ml-2 pl-3 border-l-2 border-primary/20 text-xs text-white/60 italic">
                                                            "{tx.reasoning}"
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                            {(!backtestResult.history || backtestResult.history.length === 0) && (
                                                <p className="text-center text-white/30 italic py-4">No trades executed in this period.</p>
                                            )}
                                        </div>
                                    </div>
                                </>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default PaperTraderView;
