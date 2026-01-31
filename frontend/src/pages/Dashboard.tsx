import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Brain, Zap } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import Navbar from '../components/layout/Navbar';
import Sidebar, { type ChatSession } from '../components/layout/Sidebar';
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
    // Session Management
    const [currentSessionId, setCurrentSessionId] = useState<string>('new');
    const [initialChatQuery, setInitialChatQuery] = useState('');
    const [refreshSidebar, setRefreshSidebar] = useState(0);
    const lastSavedMetadata = React.useRef<string>("");

    const handleNewChat = () => {
        setCurrentSessionId('new');
        setInitialChatQuery('');
        setIsLifted(false);
        setQuery('');
        setLoadingStage(0);
        setMockInsight(null);
        setExtractedTickers([]); // <--- Clear previous tickers
        setActiveTab('overview');
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
        setCurrentSessionId(session.session_id);
        setInitialChatQuery('');

        // Only switch to chat tab if we are currently in Overview (Home)
        if (activeTab === 'overview') {
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
            ? (JSON.parse(session.metadata) as { extractedTickers?: string[] }).extractedTickers || []
            : extractTickers(session.title);

        lastSavedMetadata.current = JSON.stringify({ extractedTickers: safeTickers });
    };

    const [query, setQuery] = useState('');
    const [isLifted, setIsLifted] = useState(false);
    const [loadingStage, setLoadingStage] = useState(0);
    const [mockInsight, setMockInsight] = useState<{ hard: { score: string, yield: string, conf: string }, soft: { source: string, quote: string, strategy: string } } | null>(null);
    const [extractedTickers, setExtractedTickers] = useState<string[]>([]);





    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query) return;
        setIsLifted(true);
        setLoadingStage(1);

        try {
            // Instant Transition
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

            // Create Session if New
            let activeSession = currentSessionId;
            if (activeSession === 'new') {
                const newTitle = query.length > 30 ? query.substring(0, 30) + '...' : query;
                const newSess = await agentService.createSession(newTitle, session);
                if (newSess?.session_id) {
                    activeSession = newSess.session_id;
                    setCurrentSessionId(activeSession);
                    setRefreshSidebar(prev => prev + 1);
                }
            }

            // Redirect to Chat View with Query
            setInitialChatQuery(query);
            setActiveTab('chat');
            setLoadingStage(0); // Reset dashboard loading state as we are leaving
            // setQuery(''); // Do NOT clear search bar yet, wait for chat to pick it up? 
            // Actually ChatView takes initialQuery prop. 
            // But we need to define the onTickers callback passed to ChatView?
            // Wait, Dashboard passes initialQuery to ChatView, and ChatView calls agentService.streamChat.
            // So ChatView needs to be updated to accept onTickers callback or handle it internally?
            // Actually, Dashboard holds the `extractedTickers` state which drives `StockAnalyticsView`.
            // So ChatView needs to Bubble up the tickers to Dashboard.

            // Let's check ChatView. For now, since I can't see ChatView, I assume I need to pass a callback to it.
            // But I cannot edit ChatView in this tool call.
            // So I will assume ChatView needs an update.

            setQuery(''); // Clear search bar

        } catch (error) {
            console.error(error);
            setLoadingStage(0); // Reset on error
            alert("Agent failed to respond. Is the backend running on port 8001?");
        }
    };

    const data = mockInsight ?? {
        hard: { score: "---", yield: "---", conf: "---" },
        soft: { source: "---", quote: "---", strategy: "---" }
    };

    // Auto-save session state (debounced)
    useEffect(() => {
        if (currentSessionId && currentSessionId !== 'new') {
            const newMetadataObj = { extractedTickers };
            const newMetadataStr = JSON.stringify(newMetadataObj);

            // Only save if different from what we last loaded/saved
            if (newMetadataStr !== lastSavedMetadata.current) {
                const timeoutId = setTimeout(() => {
                    agentService.updateSession(currentSessionId, { metadata: newMetadataStr }, session).then(() => {
                        setRefreshSidebar(prev => prev + 1);
                        lastSavedMetadata.current = newMetadataStr;
                    });
                }, 1000); // Debounce 1s
                return () => { clearTimeout(timeoutId); };
            }
        }
    }, [extractedTickers, currentSessionId, session]);


    const handleTabChange = (tab: 'overview' | 'market' | 'vault' | 'chat' | 'stocks') => {
        if (tab === 'overview') {
            // If we have an active session, go to Chat view instead of resetting
            if (currentSessionId !== 'new') {
                setActiveTab('chat');
                return;
            }

            // Only reset if we are truly in 'new' session state (or explicit reset)
            setInitialChatQuery('');
            setIsLifted(false);
            setQuery('');
            setLoadingStage(0);
            setMockInsight(null);
        }
        setActiveTab(tab);
    };

    return (
        <div className="min-h-screen bg-background relative selection:bg-primary/30">
            {/* Global Background Glow */}
            <div className="fixed top-0 left-0 w-full h-full bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/5 via-background to-background pointer-events-none z-0" />

            {/* --- Navigation --- */}
            <Navbar activeTab={activeTab} setActiveTab={handleTabChange} session={session} />

            <div className="pt-16 h-screen relative overflow-hidden">

                {/* Sidebar - Fixed, Overlay on Expand */}
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

                <div
                    className={`w-full h-full relative z-10 flex flex-col items-center pl-0 transition-all duration-150 ease-linear ${activeTab === 'chat' ? 'overflow-hidden' : 'overflow-y-auto'}`}
                    style={{ paddingLeft: isSidebarCollapsed ? '64px' : '260px' }}
                >
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
                                                e.target.style.height = `${String(Math.min(e.target.scrollHeight, 150))}px`;
                                            }}
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter' && !e.shiftKey) {
                                                    e.preventDefault();
                                                    void handleSearch(e);
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

                    {/* --- Other Views (Persistent Mounting) --- */}
                    <div className="w-full relative h-full">
                        <div className={`w-full h-full ${activeTab === 'vault' ? 'block' : 'hidden'}`}>
                            <UploadZone session={session} />
                        </div>
                        <div className={`w-full h-full ${activeTab === 'chat' ? 'block' : 'hidden'}`}>
                            <ChatView session={session} sessionId={currentSessionId} initialQuery={initialChatQuery} onTickers={setExtractedTickers} />
                        </div>
                        {/* Keep StockAnalyticsView mounted to preserve chart state/data */}
                        <div className={`w-full h-full ${activeTab === 'stocks' ? 'block' : 'hidden'}`}>
                            <StockAnalyticsView session={session} tickers={extractedTickers} />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
