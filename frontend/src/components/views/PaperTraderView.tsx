import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Play, RotateCcw, TrendingUp, AlertCircle, Loader2 } from 'lucide-react';
import type { Session } from '@supabase/supabase-js';

interface PaperTraderViewProps {
    session: Session;
    activeSessionId?: string;
}

const PaperTraderView: React.FC<PaperTraderViewProps> = ({ }) => {

    // --- Backtester State ---
    const [backtestTicker, setBacktestTicker] = useState('NVDA');
    const [backtestDays, setBacktestDays] = useState(30);
    const [isBacktesting, setIsBacktesting] = useState(false);
    const [simulationLogs, setSimulationLogs] = useState<string[]>([]);
    const [simulationProgress, setSimulationProgress] = useState(0);
    const [simulationResults, setSimulationResults] = useState<any>(null);
    const [equityCurve, setEquityCurve] = useState<any[]>([]);

    // --- Backtester Logic ---

    const handleBacktest = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsBacktesting(true);
        setSimulationLogs([]);
        setSimulationProgress(0);
        setSimulationResults(null);
        setEquityCurve([]);

        try {
            // Use fetch directly for streaming response, similar to chat
            // Assuming the backend is running on localhost:8001 as per instructions
            // In production this should use an env var, but keeping it simple as per existing patterns
            const API_LOCATION = import.meta.env.VITE_API_URL ?? 'http://localhost:8001';

            const response = await fetch(`${API_LOCATION}/api/backtest`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker: backtestTicker, days: backtestDays })
            });

            if (!response.ok) throw new Error(response.statusText);

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            if (!reader) throw new Error("No reader");

            let buffer = '';

            // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() ?? ''; // Keep incomplete line

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.replace('data: ', '').trim();
                        if (dataStr === '[DONE]') break;

                        try {
                            const event = JSON.parse(dataStr);

                            if (event.type === 'log') {
                                setSimulationLogs(prev => [...prev, event.message]);
                            } else if (event.type === 'progress') {
                                // Progress update
                                const pct = Math.round((event.current / event.total) * 100);
                                setSimulationProgress(pct);
                                // Optional: Update equity curve live if provided
                                if (event.equity) {
                                    setEquityCurve(prev => [...prev, { time: event.date, value: event.equity }]);
                                }
                            } else if (event.type === 'result') {
                                setSimulationResults(event.data);
                            } else if (event.type === 'error') {
                                setSimulationLogs(prev => [...prev, `❌ Error: ${event.message}`]);
                            }
                        } catch (e) {
                            console.error("Error parsing SSE event:", e);
                        }
                    }
                }
            }

        } catch (error) {
            console.error("Backtest failed", error);
            setSimulationLogs(prev => [...prev, `❌ Error: ${error}`]);
        } finally {
            setIsBacktesting(false);
        }
    };

    return (
        <div className="w-full max-w-7xl mx-auto p-4 md:p-8 space-y-8 pb-32">

            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">
                        Agent Backtester
                    </h1>
                    <p className="text-slate-400 mt-1">
                        Simulate the AI Agent's performance on historical data of the market.
                    </p>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                {/* Left Column: Controls & Logs */}
                <div className="space-y-6">

                    {/* Control Panel */}
                    <div className="bg-white/5 border border-white/10 rounded-2xl p-6 backdrop-blur-xl">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <RotateCcw className="w-5 h-5 text-primary" />
                            Configuration
                        </h2>

                        <form onSubmit={handleBacktest} className="space-y-4">
                            <div>
                                <label htmlFor="backtest-ticker" className="block text-xs uppercase text-white/30 mb-1 ml-1">Ticker</label>
                                <input
                                    id="backtest-ticker"
                                    type="text"
                                    value={backtestTicker}
                                    onChange={e => { setBacktestTicker(e.target.value.toUpperCase()); }}
                                    className="w-full glass-input"
                                    placeholder="e.g. NVDA"
                                />
                            </div>
                            <div>
                                <label htmlFor="backtest-days" className="block text-xs uppercase text-white/30 mb-1 ml-1">Days</label>
                                <input
                                    id="backtest-days"
                                    type="number"
                                    value={backtestDays}
                                    onChange={e => { setBacktestDays(Number(e.target.value)); }}
                                    className="w-full glass-input"
                                    min={5}
                                    max={365}
                                />
                            </div>

                            <motion.button
                                whileHover={{ scale: 1.02 }}
                                whileTap={{ scale: 0.98 }}
                                type="submit"
                                disabled={isBacktesting}
                                className={`w-full py-3 rounded-xl font-medium flex items-center justify-center gap-2 transition-all
                                    ${isBacktesting
                                        ? 'bg-white/10 text-white/50 cursor-not-allowed'
                                        : 'bg-primary text-white hover:bg-primary/90 shadow-lg shadow-primary/20'}`}
                            >
                                {isBacktesting ? (
                                    <>
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        Running Simulation... {simulationProgress}%
                                    </>
                                ) : (
                                    <>
                                        <Play className="w-4 h-4" />
                                        Start Simulation
                                    </>
                                )}
                            </motion.button>
                        </form>
                    </div>

                    {/* Simulation Logs */}
                    <div className="bg-black/40 border border-white/10 rounded-2xl p-4 h-[400px] flex flex-col backdrop-blur-md">
                        <h3 className="text-xs uppercase text-white/40 mb-2 font-mono ml-1">Live Execution Logs</h3>
                        <div className="flex-1 overflow-y-auto custom-scrollbar font-mono text-xs space-y-1 p-2">
                            <AnimatePresence>
                                {simulationLogs.map((log, i) => (
                                    <motion.div
                                        key={i}
                                        initial={{ opacity: 0, x: -10 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        className={`break-words ${log.includes('❌') ? 'text-red-400' :
                                                log.includes('✅') ? 'text-green-400' :
                                                    log.includes('⚠️') ? 'text-yellow-400' :
                                                        log.includes('⚡') ? 'text-primary' :
                                                            'text-slate-400'
                                            }`}
                                    >
                                        <span className="opacity-30 mr-2">{new Date().toLocaleTimeString().split(' ')[0]}</span>
                                        {log}
                                    </motion.div>
                                ))}
                                <div id="log-end" />
                            </AnimatePresence>
                        </div>
                    </div>
                </div>

                {/* Right Column: Visualization & Results */}
                <div className="lg:col-span-2 space-y-6">

                    {/* Equity Curve Placeholder (or Recharts if desired) */}
                    <div className="bg-white/5 border border-white/10 rounded-2xl p-6 min-h-[300px] flex flex-col">
                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <TrendingUp className="w-5 h-5 text-green-400" />
                            Performance Curve
                        </h2>

                        {equityCurve.length > 0 ? (
                            <div className="flex-1 flex items-end gap-1 h-[200px] w-full px-4 border-b border-l border-white/10 pb-2">
                                {/* Simple CSS Bar Chart for Equity */}
                                {equityCurve.map((point, i) => {
                                    const min = Math.min(...equityCurve.map(p => p.value));
                                    const max = Math.max(...equityCurve.map(p => p.value));
                                    const range = max - min;
                                    const height = range === 0 ? 50 : ((point.value - min) / range) * 100;

                                    return (
                                        <div
                                            key={i}
                                            className="flex-1 bg-primary/20 hover:bg-primary/50 transition-colors rounded-t-sm relative group"
                                            style={{ height: `${Math.max(height, 5)}%` }}
                                        >
                                            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 bg-black/90 px-2 py-1 rounded text-xs text-white opacity-0 group-hover:opacity-100 whitespace-nowrap z-10 pointer-events-none">
                                                ${point.value.toLocaleString()} <br /> {point.time}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        ) : (
                            <div className="flex-1 flex items-center justify-center text-white/20 flex-col gap-2">
                                <TrendingUp className="w-12 h-12 opacity-20" />
                                <p>Run metrics will appear here</p>
                            </div>
                        )}
                    </div>

                    {/* Results Table */}
                    {simulationResults && simulationResults.length > 0 && (
                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="bg-white/5 border border-white/10 rounded-2xl p-6"
                        >
                            <h2 className="text-lg font-semibold text-white mb-4">Final Results</h2>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="text-left text-white/40 border-b border-white/10">
                                            <th className="pb-3 pl-2">Strategy</th>
                                            <th className="pb-3">Initial Cash</th>
                                            <th className="pb-3">Final Equity</th>
                                            <th className="pb-3">Return</th>
                                            <th className="pb-3 text-right pr-2">Total Trades</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {simulationResults.map((res: any, idx: number) => (
                                            <tr key={idx} className="hover:bg-white/5 transition-colors">
                                                <td className="py-4 pl-2 font-medium text-white">{res.name}</td>
                                                <td className="py-4 text-slate-400">${res.initial_cash.toLocaleString()}</td>
                                                <td className="py-4 font-mono font-medium text-white">${res.final_equity.toLocaleString()}</td>
                                                <td className={`py-4 font-bold ${res.return_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                    {res.return_pct > 0 ? '+' : ''}{res.return_pct.toFixed(2)}%
                                                </td>
                                                <td className="py-4 text-right pr-2">{res.trades}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </motion.div>
                    )}

                    {!simulationResults && !isBacktesting && (
                        <div className="bg-primary/5 border border-dashed border-primary/20 rounded-2xl p-6 flex items-start gap-4">
                            <AlertCircle className="w-6 h-6 text-primary shrink-0 mt-1" />
                            <div>
                                <h3 className="text-white font-medium mb-1">How it works</h3>
                                <p className="text-sm text-slate-400 leading-relaxed">
                                    This simulation downloads historical data for the selected ticker and replays it day-by-day.
                                    The deployed AI Agents (configured in the backend) will receive the data as if it were live
                                    and make buy/sell decisions. The results show how your current Agent logic would have performed.
                                </p>
                            </div>
                        </div>
                    )}

                </div>
            </div>
        </div>
    );
};

export default PaperTraderView;
