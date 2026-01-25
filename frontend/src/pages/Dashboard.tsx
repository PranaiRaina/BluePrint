import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Brain, Zap, TrendingUp } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

import Navbar from '../components/layout/Navbar';
import UploadZone from '../components/views/UploadZone';
import ChatView from '../components/views/ChatView';
import Typewriter from '../components/ui/Typewriter';

import type { Session } from '@supabase/supabase-js';
import { agentService } from '../services/agent';

interface DashboardProps {
    session: Session;
}

const Dashboard: React.FC<DashboardProps> = ({ session }) => {
    const [activeTab, setActiveTab] = useState<'overview' | 'market' | 'vault' | 'chat'>('overview');

    const [query, setQuery] = useState('');
    const [isLifted, setIsLifted] = useState(false);
    const [loadingStage, setLoadingStage] = useState(0); // 0: Idle, 1: Reading, 2: Computing, 3: Done
    const [mockInsight, setMockInsight] = useState<{ hard: { score: string, yield: string, conf: string }, soft: { source: string, quote: string, strategy: string } } | null>(null);



    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query) return;
        setIsLifted(true);
        setLoadingStage(1);

        try {
            // Stage 1: Scanning (Visual)
            await new Promise(r => setTimeout(r, 800));
            setLoadingStage(2);

            // Stage 2: Computing (Real API Call)
            const response = await agentService.calculate(query, session);

            // Allow time for "Computing" animation if API was too fast
            await new Promise(r => setTimeout(r, 500));

            // Parse Agent Output
            // Since the agent returns text, we'll try to display it intelligently.
            // Ideally, we'd prompt the agent for JSON, but for now we put the text in the "strategy" field
            setMockInsight({
                hard: { score: "Calculated", yield: "Dynamic", conf: "High" },
                soft: {
                    source: "Agent Analysis",
                    quote: response.final_output.substring(0, 150) + (response.final_output.length > 150 ? "..." : ""),
                    strategy: response.final_output
                }
            });

            setLoadingStage(3);
        } catch (error) {
            console.error(error);
            setLoadingStage(0); // Reset on error
            alert("Agent failed to respond. Is the backend running on port 8001?");
        }
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
                                    <textarea
                                        value={query}
                                        onChange={(e) => {
                                            setQuery(e.target.value);
                                            // Auto-resize textarea
                                            e.target.style.height = 'auto';
                                            e.target.style.height = Math.min(e.target.scrollHeight, 150) + 'px';
                                        }}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter' && !e.shiftKey) {
                                                e.preventDefault();
                                                handleSearch(e);
                                            }
                                        }}
                                        placeholder="ask me anything..."
                                        rows={1}
                                        className="relative w-full glass-input text-lg py-4 pl-12 pr-28 shadow-2xl font-light tracking-wide bg-black/40 backdrop-blur-xl border-white/10 focus:border-primary/50 resize-none overflow-hidden min-h-[56px]"
                                    />
                                    <Search className="absolute left-4 top-5 text-text-secondary w-5 h-5" />

                                    <button
                                        type="submit"
                                        className="absolute right-2 top-2 neon-button !rounded-xl !px-6 h-10 flex items-center gap-2 group-hover:bg-ai/30 transition-all"
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
                                        {loadingStage === 1 && "SCANNING DOCUMENTS (RAG)..."}
                                        {loadingStage === 2 && "RUNNING AGENT ANALYSIS..."}
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
                                    className="w-full max-w-3xl mt-12 pb-12"
                                >
                                    {/* Single Response Card */}
                                    <div className="glass-card p-8 group hover:border-ai/30 transition-colors">
                                        <div className="flex items-center gap-3 mb-6">
                                            <div className="p-2 bg-ai/10 rounded-lg">
                                                <Brain className="text-ai w-5 h-5" />
                                            </div>
                                            <h2 className="font-serif font-bold text-xl text-white">Agent Response</h2>
                                        </div>

                                        <div className="prose prose-invert max-w-none prose-p:text-slate-200 prose-p:text-lg prose-p:leading-relaxed prose-strong:text-primary prose-headings:text-white">
                                            <ReactMarkdown>
                                                {data.soft.strategy}
                                            </ReactMarkdown>
                                        </div>

                                        <div className="mt-8 pt-6 border-t border-white/10 flex items-center justify-between">
                                            <div className="flex items-center gap-4">
                                                <button className="text-xs text-text-secondary hover:text-white flex items-center gap-2 transition-colors">
                                                    <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/e/eb/Wolfram_Language_Logo.svg/1200px-Wolfram_Language_Logo.svg.png" className="w-4 h-4 opacity-50 grayscale group-hover:grayscale-0 transition-all" alt="Wolfram" />
                                                    Wolfram Alpha
                                                </button>
                                                <span className="text-white/20">|</span>
                                                <span className="text-xs text-text-secondary flex items-center gap-1">
                                                    <Zap className="w-3 h-3 text-ai" />
                                                    Gemini 2.5 Flash
                                                </span>
                                            </div>
                                            <span className="text-xs font-mono text-primary">✓ Complete</span>
                                        </div>
                                    </div>

                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                )}

                {/* --- Other Views --- */}
                <div className="w-full">
                    {activeTab === 'market' && (
                        <div className="w-full max-w-7xl px-4 mt-8">
                            <h2 className="text-2xl font-serif font-bold text-white mb-6">Market Intelligence</h2>
                            <div className="glass-card p-8 text-center">
                                <TrendingUp className="w-12 h-12 text-primary mx-auto mb-4" />
                                <p className="text-slate-300 text-lg">
                                    Stock Analysis is now integrated into the main <strong>Home</strong> search.
                                    <br />
                                    Try asking: <em>"Analyze AAPL"</em> or <em>"Compare NVDA vs AMD"</em>
                                </p>
                            </div>
                        </div>
                    )}
                    {activeTab === 'vault' && <UploadZone />}
                    {activeTab === 'chat' && <ChatView session={session} />}
                </div>

            </div>
        </div>
    );
};

export default Dashboard;
