import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Brain, Zap } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import Navbar from '../components/layout/Navbar';
import UploadZone from '../components/views/UploadZone';
import ChatView from '../components/views/ChatView';
import StockAnalyticsView from '../components/views/StockAnalyticsView';
import Typewriter from '../components/ui/Typewriter';

import type { Session } from '@supabase/supabase-js';
import { agentService } from '../services/agent';

interface DashboardProps {
    session: Session;
}

const Dashboard: React.FC<DashboardProps> = ({ session }) => {
    const [activeTab, setActiveTab] = useState<'overview' | 'market' | 'vault' | 'chat' | 'stocks'>('overview');

    const [query, setQuery] = useState('');
    const [isLifted, setIsLifted] = useState(false);
    const [loadingStage, setLoadingStage] = useState(0); // 0: Idle, 1: Reading, 2: Computing, 3: Done
    const [mockInsight, setMockInsight] = useState<{ hard: { score: string, yield: string, conf: string }, soft: { source: string, quote: string, strategy: string } } | null>(null);
    const [extractedTickers, setExtractedTickers] = useState<string[]>([]);

    // Company name to ticker mapping for common stocks
    const COMPANY_TO_TICKER: Record<string, string> = {
        // Tech Giants
        'apple': 'AAPL', 'microsoft': 'MSFT', 'google': 'GOOGL', 'alphabet': 'GOOGL',
        'amazon': 'AMZN', 'meta': 'META', 'facebook': 'META', 'nvidia': 'NVDA',
        'tesla': 'TSLA', 'netflix': 'NFLX', 'adobe': 'ADBE', 'salesforce': 'CRM',
        'oracle': 'ORCL', 'intel': 'INTC', 'amd': 'AMD', 'ibm': 'IBM',
        'cisco': 'CSCO', 'qualcomm': 'QCOM', 'broadcom': 'AVGO',
        // AI & Cloud
        'palantir': 'PLTR', 'snowflake': 'SNOW', 'datadog': 'DDOG', 'crowdstrike': 'CRWD',
        'servicenow': 'NOW', 'splunk': 'SPLK', 'twilio': 'TWLO', 'okta': 'OKTA',
        'cloudflare': 'NET', 'mongodb': 'MDB', 'elastic': 'ESTC',
        // Finance
        'jpmorgan': 'JPM', 'goldman': 'GS', 'morgan stanley': 'MS', 'visa': 'V',
        'mastercard': 'MA', 'paypal': 'PYPL', 'square': 'SQ', 'block': 'SQ',
        'coinbase': 'COIN', 'robinhood': 'HOOD',
        // Retail & Consumer
        'walmart': 'WMT', 'costco': 'COST', 'target': 'TGT', 'nike': 'NKE',
        'starbucks': 'SBUX', 'mcdonalds': 'MCD', 'disney': 'DIS', 'coca-cola': 'KO',
        'pepsi': 'PEP', 'pepsico': 'PEP',
        // Healthcare
        'johnson': 'JNJ', 'pfizer': 'PFE', 'moderna': 'MRNA', 'unitedhealth': 'UNH',
        // Automotive
        'ford': 'F', 'gm': 'GM', 'general motors': 'GM', 'rivian': 'RIVN', 'lucid': 'LCID',
        // Energy
        'exxon': 'XOM', 'chevron': 'CVX', 'shell': 'SHEL',
        // Other
        'uber': 'UBER', 'lyft': 'LYFT', 'airbnb': 'ABNB', 'doordash': 'DASH',
        'zoom': 'ZM', 'spotify': 'SPOT', 'snap': 'SNAP', 'snapchat': 'SNAP',
        'twitter': 'TWTR', 'pinterest': 'PINS', 'roblox': 'RBLX',
        'draftkings': 'DKNG', 'peloton': 'PTON', 'shopify': 'SHOP', 'etsy': 'ETSY',
        'c3': 'AI', 'c3.ai': 'AI', 'soundhound': 'SOUN',
    };

    // Helper to extract stock tickers from text
    const extractTickers = (text: string): string[] => {
        const lowerText = text.toLowerCase();
        const foundTickers: string[] = [];

        // 1. Check for company names in the text
        for (const [companyName, ticker] of Object.entries(COMPANY_TO_TICKER)) {
            if (lowerText.includes(companyName)) {
                foundTickers.push(ticker);
            }
        }

        // 2. Also check for direct ticker mentions (e.g., $NVDA or NVDA)
        const tickerRegex = /\$?([A-Z]{2,5})\b/g;
        const upperText = text.toUpperCase();
        let match;
        while ((match = tickerRegex.exec(upperText)) !== null) {
            const ticker = match[1];
            // Only add if it's a known ticker (exists as a value in our mapping)
            const knownTickers = Object.values(COMPANY_TO_TICKER);
            if (knownTickers.includes(ticker) && !foundTickers.includes(ticker)) {
                foundTickers.push(ticker);
            }
        }

        return [...new Set(foundTickers)]; // Deduplicate
    };



    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query) return;
        setIsLifted(true);
        setLoadingStage(1);

        try {
            // Stage 1: Scanning (Visual)
            await new Promise(r => setTimeout(r, 800));
            // Instead of stage 2, we jump to showing the card (Stage 3) but empty
            setLoadingStage(3);

            // Initial empty state
            setMockInsight({
                hard: { score: "Calculating...", yield: "---", conf: "---" },
                soft: {
                    source: "Agent Analysis",
                    quote: "",
                    strategy: ""
                }
            });

            // Extract stock tickers immediately
            const tickersFromQuery = extractTickers(query);
            setExtractedTickers(tickersFromQuery);

            let fullResponse = "";
            let displayedResponse = "";

            // Smooth Typewriter Effect
            const typeWriter = setInterval(() => {
                if (displayedResponse.length < fullResponse.length) {
                    const lag = fullResponse.length - displayedResponse.length;
                    const chunkSize = lag > 50 ? 5 : (lag > 20 ? 3 : 2);

                    const nextChunk = fullResponse.slice(displayedResponse.length, displayedResponse.length + chunkSize);
                    displayedResponse += nextChunk;

                    setMockInsight(prev => ({
                        hard: prev?.hard || { score: "...", yield: "...", conf: "..." },
                        soft: {
                            source: "Agent Analysis",
                            quote: displayedResponse.substring(0, 150) + "...",
                            strategy: displayedResponse
                        }
                    }));
                }
            }, 20);

            // Stream Chat
            await agentService.streamChat(
                query,
                session,
                session.user.id,
                {
                    onStatus: (status) => {
                        // Optional: Store status somewhere if we want to show it
                    },
                    onToken: (token) => {
                        fullResponse += token;
                    },
                    onComplete: () => {
                        clearInterval(typeWriter);
                        // Final sync
                        setMockInsight({
                            hard: { score: "Calculated", yield: "Dynamic", conf: "High" },
                            soft: {
                                source: "Agent Analysis",
                                quote: fullResponse.substring(0, 150) + (fullResponse.length > 150 ? "..." : ""),
                                strategy: fullResponse
                            }
                        });
                        setLoadingStage(4); // Streaming Complete
                    },
                    onError: (err) => {
                        console.error(err);
                        clearInterval(typeWriter);
                        alert("Stream encountered an error.");
                    }
                }
            );

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
            <Navbar activeTab={activeTab} setActiveTab={setActiveTab} session={session} />

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
                                        className="relative w-full glass-input text-lg py-4 pl-12 pr-28 shadow-2xl font-light tracking-wide bg-black/40 backdrop-blur-xl border-white/10 focus:border-primary/50 resize-none overflow-y-auto no-scrollbar min-h-[56px] max-h-[200px]"
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


                        </motion.div>

                        {/* Dynamic Zones */}
                        <AnimatePresence>
                            {loadingStage > 0 && (
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

                                        <div className="prose prose-invert max-w-none prose-p:text-slate-200 prose-p:text-lg prose-p:leading-relaxed prose-strong:text-primary prose-headings:text-white prose-table:w-full prose-th:text-left prose-th:p-2 prose-td:p-2 prose-tr:border-b prose-tr:border-white/10 prose-thead:bg-white/5">
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                {data.soft.strategy}
                                            </ReactMarkdown>
                                        </div>

                                        <div className="mt-8 pt-6 border-t border-white/10 flex items-center justify-end">
                                            {loadingStage < 4 ? (
                                                <div className="flex items-center gap-3 text-ai font-mono text-xs bg-ai/5 px-3 py-1.5 rounded-full border border-ai/10">
                                                    <div className="w-1.5 h-1.5 bg-ai rounded-full animate-ping" />
                                                    {loadingStage === 1 ? "SCANNING..." : "THINKING..."}
                                                </div>
                                            ) : (
                                                <span className="text-xs font-mono text-primary">✓ Complete</span>
                                            )}
                                        </div>
                                    </div>

                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                )}

                {/* --- Other Views --- */}
                {/* --- Other Views (Persistent Mounting) --- */}
                <div className="w-full relative">
                    <div className={activeTab === 'vault' ? 'block' : 'hidden'}>
                        <UploadZone session={session} />
                    </div>
                    <div className={activeTab === 'chat' ? 'block' : 'hidden'}>
                        <ChatView session={session} />
                    </div>
                    {/* Keep StockAnalyticsView mounted to preserve chart state/data */}
                    <div className={activeTab === 'stocks' ? 'block' : 'hidden'}>
                        <StockAnalyticsView session={session} tickers={extractedTickers} />
                    </div>
                </div>

            </div>
        </div>
    );
};

export default Dashboard;
