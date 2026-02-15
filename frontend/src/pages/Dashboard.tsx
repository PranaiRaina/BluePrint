import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Brain, Zap } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import Navbar from '../components/layout/Navbar';
import Sidebar, { type ChatSession } from '../components/layout/Sidebar';
import UploadZone from '../components/views/UploadZone';
import ChatView from '../components/views/ChatView';
import UserProfileView from '../components/views/UserProfileView';
import StockAnalyticsView from '../components/views/StockAnalyticsView';
import PortfolioAnalysisView from '../components/views/PortfolioAnalysisView';
import StocksView from '../components/views/StocksView';
import Typewriter from '../components/ui/Typewriter';

import type { Session } from '@supabase/supabase-js';
import { agentService } from '../services/agent';

interface DashboardProps {
    session: Session;
}

const Dashboard: React.FC<DashboardProps> = ({ session }) => {
    const [activeTab, setActiveTab] = useState<'overview' | 'market' | 'vault' | 'chat' | 'stocks' | 'profile' | 'analytics' | 'simulation'>('overview');

    // Helper to generate a unique session ID
    const generateId = () => {
        try {
            return crypto.randomUUID();
        } catch {
            return `s_${Date.now().toString()}_${Math.random().toString(36).substring(2, 9)}`;
        }
    };
    // Session Management
    const [currentSessionId, setCurrentSessionId] = useState<string>(() => generateId());
    const [initialChatQuery, setInitialChatQuery] = useState('');
    const [chatKey, setChatKey] = useState(0);
    const [refreshSidebar, setRefreshSidebar] = useState(0);
    const lastSavedMetadata = React.useRef<string>("");

    const handleNewChat = () => {
        setCurrentSessionId(generateId());
        setInitialChatQuery('');
        setQuery('');
        setLoadingStage(0);
        setMockInsight(null);
        setExtractedTickers([]); // <--- Clear previous tickers
        setChatKey(prev => prev + 1); // Force ChatView remount
        setActiveTab('overview'); // Switch to overview for fresh start
    };

    // Helper to extract stock tickers from text (Simplified Fallback)
    const extractTickers = (text: string): string[] => {
        // Only check for direct ticker mentions (e.g., $NVDA or NVDA)
        // This is mainly a fallback for old sessions without metadata
        const tickerRegex = /\$?([A-Z]{2,5})\b/g;
        const foundTickers: string[] = [];
        let match;
        while ((match = tickerRegex.exec(text)) !== null) {
            foundTickers.push(match[1]);
        }
        return [...new Set(foundTickers)];
    };


    const handleSessionSelect = (session: ChatSession) => {
        const isNewSession = session.session_id !== currentSessionId;

        setCurrentSessionId(session.session_id);
        setInitialChatQuery('');

        if (isNewSession) {
            setChatKey(prev => prev + 1);
        }

        // Always switch to chat tab when a session is selected
        if (activeTab !== 'chat') {
            setActiveTab('chat');
        }

        // Restore state from metadata
        if (session.metadata) {
            try {
                const meta = JSON.parse(session.metadata) as { extractedTickers?: string[] };
                if (meta.extractedTickers) {
                    setExtractedTickers(meta.extractedTickers);
                } else {
                    setExtractedTickers([]);
                }
            } catch (e) {
                console.error("Failed to parse session metadata", e);
                setExtractedTickers([]);
            }
        } else {
            // Fallback for sessions with no metadata (old sessions):
            // Try to extract tickers from the session title
            console.log("No metadata found, inferring tickers from title:", session.title);
            const tickersFromTitle = extractTickers(session.title);
            setExtractedTickers(tickersFromTitle);
        }

        // Update baseline so we don't auto-save immediately
        const safeTickers = session.metadata
            ? (JSON.parse(session.metadata) as { extractedTickers?: string[] } | null)?.extractedTickers ?? []
            : extractTickers(session.title);

        lastSavedMetadata.current = JSON.stringify({ extractedTickers: safeTickers });
    };

    const [query, setQuery] = useState('');
    const [loadingStage, setLoadingStage] = useState(0);
    const [mockInsight, setMockInsight] = useState<{ hard: { score: string, yield: string, conf: string }, soft: { source: string, quote: string, strategy: string } } | null>(null);
    const [extractedTickers, setExtractedTickers] = useState<string[]>([]);


    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        if (!query) return;
        try {
            // Start process
            setLoadingStage(3);

            // Generate a fresh session ID for this new search
            const newSessionId = generateId();
            setCurrentSessionId(newSessionId);

            // Initial empty state
            setMockInsight({
                hard: { score: "Calculating...", yield: "---", conf: "---" },
                soft: {
                    source: "Agent Analysis",
                    quote: "",
                    strategy: ""
                }
            });
            setInitialChatQuery(query);
            setChatKey(prev => prev + 1); // Force ChatView remount
            setActiveTab('chat');
            setLoadingStage(0);
            setQuery('');

        } catch (error) {
            console.error(error);
            setLoadingStage(0);
            alert("Agent failed to respond. Is the backend running on port 8001?");
        }
    };

    const data = mockInsight ?? {
        hard: { score: "---", yield: "---", conf: "---" },
        soft: { source: "---", quote: "---", strategy: "---" }
    };

    // Auto-save session state (debounced)
    useEffect(() => {
        if (currentSessionId) {
            const newMetadataObj = { extractedTickers };
            const newMetadataStr = JSON.stringify(newMetadataObj);

            // Only save if different from what we last loaded/saved
            if (newMetadataStr !== lastSavedMetadata.current) {
                const timeoutId = setTimeout(() => {
                    void agentService.updateSession(currentSessionId, { metadata: newMetadataStr }, session).then(() => {
                        setRefreshSidebar(prev => prev + 1);
                        lastSavedMetadata.current = newMetadataStr;
                    });
                }, 1000); // Debounce 1s
                return () => { clearTimeout(timeoutId); };
            }
        }
    }, [extractedTickers, currentSessionId, session]);


    const handleTabChange = (tab: 'overview' | 'market' | 'vault' | 'chat' | 'stocks' | 'profile' | 'analytics' | 'simulation') => {
        // Fix: Removed aggressive redirect that breaks Home tab navigation
        setActiveTab(tab);
    };

    return (
        <div className="min-h-screen bg-background relative selection:bg-primary/30">
            {/* Global Background Glow */}
            <div className="fixed top-0 left-0 w-full h-full bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/5 via-background to-background pointer-events-none z-0" />

            {/* --- Navigation --- */}
            <Navbar activeTab={activeTab} setActiveTab={handleTabChange} session={session} />

            <div className="pt-16 h-screen relative overflow-hidden">

                {/* Sidebar - Fixed, Overlay on Expand (Hidden on Profile/Analytics) */}
                {activeTab !== 'profile' && activeTab !== 'analytics' && (
                    <Sidebar
                        session={session}
                        activeSessionId={currentSessionId}
                        onSessionSelect={handleSessionSelect}
                        onNewChat={handleNewChat}
                        refreshTrigger={refreshSidebar}
                        className="fixed left-0 top-16 bottom-0 z-50 hidden md:flex shrink-0 border-r border-white/10 bg-black/80 backdrop-blur-xl"
                        isCollapsed={isSidebarCollapsed}
                        onToggle={() => { setIsSidebarCollapsed(!isSidebarCollapsed); }}
                    />
                )}

                <motion.div
                    className={`w-full h-full relative z-10 flex flex-col items-center pl-0 ${activeTab === 'chat' ? 'overflow-hidden' : 'overflow-y-auto'}`}
                    animate={{ paddingLeft: (activeTab === 'profile' || activeTab === 'analytics') ? 0 : (isSidebarCollapsed ? 64 : 260) }}
                    transition={{ duration: 0.15, ease: "linear" }}
                >
                    <AnimatePresence>
                        {/* --- Overview View --- */}
                        {activeTab === 'overview' && (
                            <motion.div
                                key="overview"
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -10, transition: { duration: 0.2 } }}
                                className="flex flex-col items-center w-full max-w-7xl px-4"
                            >
                                {/* Hero / Header Section */}
                                <motion.div
                                    layout
                                    className="w-full max-w-4xl px-4 z-10 flex flex-col items-center transition-all duration-700 mt-[30vh]"
                                >
                                    <Typewriter
                                        text="Let your wealth grow organically."
                                        className="font-serif font-bold text-transparent bg-clip-text bg-gradient-to-r from-white to-slate-200 mb-8 text-center tracking-tight text-5xl md:text-7xl min-h-[1.2em]"
                                    />

                                    <motion.form
                                        layoutId="active-search-bar"
                                        onSubmit={handleSearch}
                                        className="w-full relative max-w-2xl"
                                        initial={{ borderRadius: "24px" }}
                                    >
                                        <div className="relative group">
                                            <div className={`absolute -inset-1 bg-gradient-to-r from-primary to-ai rounded-2xl blur opacity-25 group-hover:opacity-60 transition duration-1000 group-hover:duration-200 ${loadingStage > 0 && loadingStage < 3 ? 'animate-pulse' : ''}`}></div>
                                            <textarea
                                                value={query}
                                                onChange={(e) => {
                                                    setQuery(e.target.value);
                                                    // Auto-resize textarea
                                                    e.target.style.height = 'auto';
                                                    e.target.style.height = `${String(Math.min(e.target.scrollHeight, 150))}px`;
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
                                    </motion.form>
                                </motion.div>

                                {/* Dynamic Zones (Partial Response Demo) */}
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
                            </motion.div>
                        )}

                        {/* --- Stocks View --- */}
                        {/* NOTE: Removed from AnimatePresence so report generation persists across tab switches */}

                    </AnimatePresence >

                    {/* --- Chat View (Persistent) --- */}
                    < div className={`w-full h-full ${activeTab === 'chat' ? 'block' : 'hidden'}`}>
                        <ChatView
                            key={`chat_${String(chatKey)}`}
                            session={session}
                            sessionId={currentSessionId}
                            initialQuery={initialChatQuery}
                            onTickers={setExtractedTickers}
                            onSessionCreated={() => { setRefreshSidebar(prev => prev + 1); }}
                        />
                    </div >

                    {/* --- Other Views (Persistent Mounting) --- */}
                    < div className="w-full relative h-full hidden" >
                        {/* Hidden container for persistent views if needed, but we are using conditional rendering for animation now. 
                            However, StockAnalyticsView MUST persist. 
                        */}
                    </div >

                    <div className={`w-full h-full ${activeTab === 'vault' ? 'block' : 'hidden'}`}>
                        {/* Vault needs to be outside AnimatePresence if we don't animate it, or inside. 
                            For now, keeping it here. 
                         */}
                        {activeTab === 'vault' && <UploadZone session={session} />}
                    </div>

                    <div className={`w-full h-full ${activeTab === 'profile' ? 'block' : 'hidden'}`}>
                        {activeTab === 'profile' && <UserProfileView session={session} onAnalyze={(ticker) => {
                            setInitialChatQuery(`Analyze ${ticker} stock - give me a comprehensive research report including recent news, financials, and your recommendation.`);
                            setCurrentSessionId(generateId());
                            setChatKey(prev => prev + 1);
                            setActiveTab('chat');
                        }} onViewAnalysis={() => { setActiveTab('analytics'); }} />}
                    </div>

                    <div className={`w-full h-full ${activeTab === 'simulation' ? 'block' : 'hidden'}`}>
                        <StocksView session={session} onViewAnalysis={() => { setActiveTab('analytics'); }} isSidebarOpen={!isSidebarCollapsed} />
                    </div>

                    <div className={`w-full h-full ${activeTab === 'stocks' ? 'block' : 'hidden'}`}>
                        <StockAnalyticsView session={session} tickers={extractedTickers} />
                    </div>

                    {/* Analytics Full Page View */}
                    <div className={`w-full h-full ${activeTab === 'analytics' ? 'block' : 'hidden'}`}>
                        {activeTab === 'analytics' && (
                            <PortfolioAnalysisView
                                session={session}
                                onBack={() => { setActiveTab('simulation'); }}
                            />
                        )}
                    </div>
                </motion.div >
            </div >
        </div >
    );
};

export default Dashboard;
