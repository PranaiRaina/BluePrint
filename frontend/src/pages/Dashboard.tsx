import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Brain, Zap, TrendingUp, BarChart3 } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

import Navbar from '../components/layout/Navbar';
import UploadZone from '../components/views/UploadZone';
import StockView from '../components/views/StockView';
import ChatView from '../components/views/ChatView';
import Typewriter from '../components/ui/Typewriter';
import Ticker from '../components/ui/Ticker';

const Dashboard: React.FC = () => {
    const [activeTab, setActiveTab] = useState<'overview' | 'vault' | 'market' | 'chat'>('overview');

    // Overview State
    const [query, setQuery] = useState('');
    const [isLifted, setIsLifted] = useState(false);
    const [loadingStage, setLoadingStage] = useState(0); // 0: Idle, 1: Reading, 2: Computing, 3: Done
    const [riskLevel, setRiskLevel] = useState(50);
    const [mockInsight, setMockInsight] = useState<{ hard: { score: string, yield: string, conf: string }, soft: { source: string, quote: string, strategy: string } } | null>(null);

    // Dynamic Chart Data based on Risk Level
    const getChartData = () => {
        const baseGrowth = 1 + (riskLevel / 100) * 0.15; // 0% to 15% extra growth factor
        const volatility = (riskLevel / 100) * 2000;

        return [
            { name: '2024', value: 4000 },
            { name: '2025', value: 4000 * Math.pow(baseGrowth, 1) + (Math.random() * volatility - volatility / 2) },
            { name: '2026', value: 4000 * Math.pow(baseGrowth, 2) + (Math.random() * volatility - volatility / 2) },
            { name: '2027', value: 4000 * Math.pow(baseGrowth, 3) + (Math.random() * volatility - volatility / 2) },
            { name: '2028', value: 4000 * Math.pow(baseGrowth, 4) + (Math.random() * volatility - volatility / 2) },
            { name: '2029', value: 4000 * Math.pow(baseGrowth, 5) + (Math.random() * volatility - volatility / 2) },
            { name: '2030', value: 4000 * Math.pow(baseGrowth, 6) }
        ].map(d => ({ ...d, value: Math.round(d.value) }));
    };

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        if (!query) return;
        setIsLifted(true);
        setLoadingStage(1);

        // Simulate Agentic Steps
        setTimeout(() => setLoadingStage(2), 1500); // Computing

        setTimeout(() => {
            // Generate Context-Aware Mock Data
            const lowerQ = query.toLowerCase();
            if (lowerQ.includes('debt') || lowerQ.includes('loan')) {
                setMockInsight({
                    hard: { score: "Med (5.8)", yield: "4.2%", conf: "98%" },
                    soft: {
                        source: "Credit_Report_2024.pdf",
                        quote: "Auto loan APR at 7.5% is eroding checking account gains.",
                        strategy: "Aggressive pay-down of 7.5% loan outperforms expected market returns (6%)."
                    }
                });
            } else if (lowerQ.includes('invest') || lowerQ.includes('stock') || lowerQ.includes('wealth')) {
                setMockInsight({
                    hard: { score: "High (8.2)", yield: "12.4%", conf: "85%" },
                    soft: {
                        source: "Market_Analysis_Q3.pdf",
                        quote: "Tech sector showing strong breakout signals in mid-cap options.",
                        strategy: "Shift 15% of bonds to high-growth ETFs to capture upside."
                    }
                });
            } else {
                setMockInsight({
                    hard: { score: "Low (3.2)", yield: "7.8%", conf: "94%" },
                    soft: {
                        source: "Bob_Jones_Report.pdf",
                        quote: "High cash reserves detected (>20%). Recommended shifting $15k into high-yield bonds.",
                        strategy: "Reducing debt load on the 7% auto loan serves better long-term ROI."
                    }
                });
            }
            setLoadingStage(3);
        }, 3000); // Done
    };

    const data = mockInsight || {
        hard: { score: "---", yield: "---", conf: "---" },
        soft: { source: "---", quote: "---", strategy: "---" }
    };

    return (
        <div className="min-h-screen bg-background relative selection:bg-primary/30">
            {/* Global Background Glow */}
            <div className="fixed top-0 left-0 w-full h-full bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/5 via-background to-background pointer-events-none z-0" />

            {/* --- Navigation --- */}
            <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />

            <div className="pt-16 relative z-10 flex flex-col items-center">
                {/* Live Ticker */}
                <Ticker />

                {/* --- Overview View --- */}
                {activeTab === 'overview' && (
                    <div className="flex flex-col items-center w-full w-full max-w-7xl px-4">
                        {/* Hero / Header Section */}
                        <motion.div
                            layout
                            className={`w-full max-w-4xl px-4 z-10 flex flex-col items-center transition-all duration-700 ${isLifted ? 'mt-8' : 'mt-[25vh]'}`}
                        >
                            {!isLifted ? (
                                <Typewriter
                                    text="Let your wealth grow organically."
                                    className="font-serif font-bold text-transparent bg-clip-text bg-gradient-to-r from-white to-slate-200 mb-8 text-center tracking-tight text-5xl md:text-7xl min-h-[1.2em]"
                                />
                            ) : (
                                <motion.h1
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    className="font-serif font-bold text-white mb-6 text-center tracking-tight text-3xl"
                                >
                                    Financial Intelligence Agent
                                </motion.h1>
                            )}

                            <form onSubmit={handleSearch} className="w-full relative max-w-2xl">
                                <div className="relative group">
                                    <div className={`absolute -inset-1 bg-gradient-to-r from-primary to-ai rounded-2xl blur opacity-25 group-hover:opacity-60 transition duration-1000 group-hover:duration-200 ${loadingStage > 0 && loadingStage < 3 ? 'animate-pulse' : ''}`}></div>
                                    <input
                                        type="text"
                                        value={query}
                                        onChange={(e) => setQuery(e.target.value)}
                                        placeholder="ask me anything..."
                                        className="relative w-full glass-input text-lg py-4 pl-12 pr-20 shadow-2xl font-light tracking-wide bg-black/40 backdrop-blur-xl border-white/10 focus:border-primary/50"
                                    />
                                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-text-secondary w-5 h-5" />

                                    <button
                                        type="submit"
                                        className="absolute right-2 top-2 bottom-2 neon-button !rounded-xl !px-6 flex items-center gap-2 group-hover:bg-ai/30 transition-all"
                                    >
                                        <span className="text-sm font-semibold tracking-wide">RUN</span>
                                        <Zap className="w-3 h-3 fill-current" />
                                    </button>
                                </div>
                            </form>

                            {/* Loading Indicators */}
                            <AnimatePresence>
                                {loadingStage > 0 && loadingStage < 3 && (
                                    <motion.div
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0 }}
                                        className="mt-6 flex items-center gap-3 text-ai font-mono text-sm bg-ai/10 px-4 py-2 rounded-full border border-ai/20"
                                    >
                                        <div className="w-2 h-2 bg-ai rounded-full animate-ping" />
                                        {loadingStage === 1 && "SCANNING SECURE DOCUMENTS..."}
                                        {loadingStage === 2 && "RUNNING WOLFRAM COMPUTATIONS..."}
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </motion.div>

                        {/* Dynamic Zones */}
                        <AnimatePresence>
                            {loadingStage === 3 && (
                                <motion.div
                                    initial={{ opacity: 0, y: 40 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.8, delay: 0.2 }}
                                    className="w-full mt-12 pb-12 grid grid-cols-1 md:grid-cols-3 gap-6"
                                >
                                    {/* Zone 1: Hard Data (Wolfram) */}
                                    <div className="glass-card p-6 flex flex-col gap-4 group hover:border-primary/30 transition-colors">
                                        <div className="flex items-center gap-3 mb-2">
                                            <div className="p-2 bg-primary/10 rounded-lg">
                                                <BarChart3 className="text-primary w-5 h-5" />
                                            </div>
                                            <h2 className="font-serif font-bold text-xl text-white">Analysis</h2>
                                        </div>

                                        <div className="space-y-4">
                                            <div className="flex justify-between items-end border-b border-white/5 pb-2">
                                                <span className="text-text-secondary text-sm">Risk Score</span>
                                                <span className="font-mono text-xl text-primary font-bold">{data.hard.score}</span>
                                            </div>
                                            <div className="flex justify-between items-end border-b border-white/5 pb-2">
                                                <span className="text-text-secondary text-sm">Est. Yield</span>
                                                <span className="font-mono text-xl text-white font-bold">{data.hard.yield}</span>
                                            </div>
                                            <div className="flex justify-between items-end border-b border-white/5 pb-2">
                                                <span className="text-text-secondary text-sm">Confidence</span>
                                                <span className="font-mono text-xl text-ai font-bold">{data.hard.conf}</span>
                                            </div>
                                        </div>

                                        <div className="mt-auto pt-4">
                                            <button className="text-xs text-text-secondary hover:text-white flex items-center gap-1 transition-colors">
                                                <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/e/eb/Wolfram_Language_Logo.svg/1200px-Wolfram_Language_Logo.svg.png" className="w-4 h-4 opacity-50 block grayscale group-hover:grayscale-0 transition-all" alt="Wolfram" />
                                                Verified Computation
                                            </button>
                                        </div>
                                    </div>

                                    {/* Zone 2: Soft Data (RAG Insights) */}
                                    <div className="glass-card p-6 flex flex-col gap-4 group hover:border-ai/30 transition-colors">
                                        <div className="flex items-center gap-3 mb-2">
                                            <div className="p-2 bg-ai/10 rounded-lg">
                                                <Brain className="text-ai w-5 h-5" />
                                            </div>
                                            <h2 className="font-serif font-bold text-xl text-white">Agent Insights</h2>
                                        </div>

                                        <div className="space-y-3">
                                            <div className="p-4 bg-white/5 rounded-xl text-sm leading-relaxed border-l-2 border-primary">
                                                <p className="text-text-secondary mb-2 text-xs uppercase tracking-wider font-bold">
                                                    Source: <span className="text-white">{data.soft.source}</span>
                                                </p>
                                                <p className="text-slate-200 italic">
                                                    "{data.soft.quote}"
                                                </p>
                                            </div>
                                            <div className="p-4 bg-ai/5 rounded-xl text-sm leading-relaxed border-l-2 border-ai">
                                                <p className="text-white font-medium">
                                                    <span className="text-ai">Strategy:</span> {data.soft.strategy}
                                                </p>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Zone 3: Future View (Interactive Chart) */}
                                    <div className="glass-card p-6 md:col-span-1 lg:col-span-1 flex flex-col group hover:border-blue-500/30 transition-colors">
                                        <div className="flex items-center gap-3 mb-4">
                                            <div className="p-2 bg-blue-500/10 rounded-lg">
                                                <TrendingUp className="text-blue-400 w-5 h-5" />
                                            </div>
                                            <h2 className="font-serif font-bold text-xl text-white">Projection</h2>
                                        </div>

                                        <div className="h-48 w-full mt-2">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <AreaChart data={getChartData()}>
                                                    <defs>
                                                        <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                                                            <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.3} />
                                                            <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0} />
                                                        </linearGradient>
                                                    </defs>
                                                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} vertical={false} />
                                                    <XAxis dataKey="name" stroke="#94A3B8" fontSize={10} tickLine={false} axisLine={false} dy={10} />
                                                    <YAxis stroke="#94A3B8" fontSize={10} tickLine={false} axisLine={false} tickFormatter={(val) => `$${val}`} />
                                                    <Tooltip
                                                        contentStyle={{ backgroundColor: '#0F172A', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', boxShadow: '0 10px 30px -10px rgba(0,0,0,0.5)' }}
                                                        itemStyle={{ color: '#fff' }}
                                                    />
                                                    <Area type="monotone" dataKey="value" stroke="#8B5CF6" strokeWidth={3} fillOpacity={1} fill="url(#colorValue)" />
                                                </AreaChart>
                                            </ResponsiveContainer>
                                        </div>

                                        <div className="mt-4">
                                            <div className="flex justify-between text-xs text-text-secondary mb-3 font-mono">
                                                <span>CONSERVATIVE</span>
                                                <span className="text-ai">AGGRESSIVE ({riskLevel}%)</span>
                                            </div>
                                            <input
                                                type="range"
                                                min="0"
                                                max="100"
                                                value={riskLevel}
                                                onChange={(e) => setRiskLevel(Number(e.target.value))}
                                                className="w-full h-1.5 bg-white/10 rounded-lg appearance-none cursor-pointer accent-ai hover:accent-ai/80 transition-all"
                                            />
                                        </div>
                                    </div>

                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                )}

                {/* --- Other Views --- */}
                <div className="w-full">
                    {activeTab === 'vault' && <UploadZone />}
                    {activeTab === 'market' && <StockView />}
                    {activeTab === 'chat' && <ChatView />}
                </div>

            </div>
        </div>
    );
};

export default Dashboard;
