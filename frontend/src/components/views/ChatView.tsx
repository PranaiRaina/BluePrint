import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { agentService, type Message } from '../../services/agent';
import { Send, Bot } from 'lucide-react';
import type { Session } from '@supabase/supabase-js';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import LiveMessage from '../ui/LiveMessage'; // Import the new component
import Typewriter from '../ui/Typewriter';

interface ChatViewProps {
    session: Session;
    sessionId: string;
    initialQuery?: string;
    onTickers?: (tickers: string[]) => void;
    onSessionCreated?: () => void;
}
const getUserInitials = (email?: string) => {
    if (!email) return 'U';
    return email.substring(0, 2).toUpperCase();
};

const ChatView: React.FC<ChatViewProps> = ({ session, sessionId, initialQuery, onTickers, onSessionCreated }) => {

    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isHistoryLoading, setIsHistoryLoading] = useState(false);
    const [loadingStatus, setLoadingStatus] = useState("Thinking...");

    // Ref to hold the current streaming content without triggering re-renders
    const streamContentRef = useRef("");

    const messagesEndRef = React.useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, isLoading, isHistoryLoading]);



    useEffect(() => {
        let isStale = false;
        const loadHistory = async () => {
            if (!session?.user?.id || !sessionId) return;

            // Reset messages only if truly necessary (e.g. initial render or genuine switch)
            setMessages([]);
            setIsHistoryLoading(true);

            try {
                const history = await agentService.getHistory(sessionId, session);

                if (isStale) return;

                // Only load history if we don't have a pending initial auto-query.
                // For sidebar selections, initialQuery will be empty ('').
                if (!initialQuery) {
                    setMessages(history);
                }
            } catch (e) {
                console.error("Failed to load history", e);
            } finally {
                if (!isStale) {
                    setIsHistoryLoading(false);
                }
            }
        };

        void loadHistory();

        return () => {
            isStale = true;
        };
    }, [sessionId, initialQuery, session]);

    const processQuery = React.useCallback(async (text: string) => {
        if (!text.trim()) return;

        // Reset stream Ref
        streamContentRef.current = "";

        // UI Update: Add user message and empty AI placeholder
        setMessages(prev => [
            ...prev,
            { role: 'user' as const, content: text },
            { role: 'ai' as const, content: '' }
        ]);

        setInput('');
        setIsLoading(true);
        setLoadingStatus("Thinking...");

        try {
            await agentService.streamChat(
                text,
                session,
                sessionId || 'new',
                {
                    onStatus: (status) => {
                        setLoadingStatus(status);
                    },
                    onToken: (token) => {
                        // Update ref directly - NO RE-RENDER triggered here
                        streamContentRef.current += token;
                    },
                    onTickers: (tickers) => {
                        if (onTickers) onTickers(tickers);
                    },
                    onComplete: () => {
                        // Final consistency update
                        setMessages(prev => {
                            const lastMsg = prev[prev.length - 1];
                            if (lastMsg?.role === 'ai') {
                                return [
                                    ...prev.slice(0, -1),
                                    { ...lastMsg, content: streamContentRef.current }
                                ];
                            }
                            return prev;
                        });
                        setIsLoading(false);
                        setLoadingStatus("Thinking...");
                        if (onSessionCreated) onSessionCreated();
                    },
                    onError: (err) => {
                        console.error(err);
                        setMessages(prev => {
                            const lastMsg = prev[prev.length - 1];
                            const errorMessage = err || "An unknown error occurred";
                            const errorMsg = `\n\n ** Error:** ${errorMessage} `;
                            if (lastMsg?.role === 'ai') {
                                return [
                                    ...prev.slice(0, -1),
                                    { ...lastMsg, content: streamContentRef.current + errorMsg }
                                ];
                            }
                            return prev;
                        });
                        setIsLoading(false);
                    }
                }
            );
        } catch (error) {
            console.error(error);
            setIsLoading(false);
        }
    }, [session, sessionId, onTickers]);

    const handleSend = async (e: React.FormEvent) => {
        e.preventDefault();
        if (input.trim() && !isLoading) {
            await processQuery(input);
        }
    };

    // Auto-Send Initial Query
    const hasSentInitial = React.useRef(false);
    useEffect(() => {
        if (!initialQuery) {
            hasSentInitial.current = false;
            return;
        }

        if (initialQuery && !hasSentInitial.current) {
            hasSentInitial.current = true;
            void processQuery(initialQuery);
        }
    }, [initialQuery, processQuery]);

    return (
        <div className="w-full h-full pt-4 pb-4 px-4 flex flex-col max-w-5xl mx-auto">
            <div className="flex items-center gap-3 mb-6 p-4 border-b border-white/5 shrink-0">
                <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center overflow-hidden">
                    <img src="/logo.png" alt="BluePrint" className="w-8 h-8 object-contain" />
                </div>
                <div>
                    <Typewriter
                        key={`title-${sessionId}`}
                        text="BluePrint Agent"
                        speed={50}
                        className="text-xl font-bold text-white font-serif tracking-wide"
                    />
                </div>
            </div>

            <div className="flex-1 overflow-y-auto space-y-4 pr-2 custom-scrollbar">
                {isHistoryLoading && (
                    <div className="flex items-center justify-center h-full">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                    </div>
                )}
                {!isHistoryLoading && messages.map((msg, i) => (
                    <motion.div
                        key={i}
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className={`flex gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                    >
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${msg.role === 'ai' ? 'bg-ai/20 text-ai' : 'bg-gradient-to-br from-primary to-ai text-white'}`}>
                            {msg.role === 'ai' ? <Bot className="w-4 h-4" /> : <span className="font-serif text-xs">{getUserInitials(session.user.email)}</span>}
                        </div>
                        <div className={`p-4 rounded-2xl max-w-[85%] w-fit text-sm leading-relaxed overflow-hidden ${msg.role === 'ai'
                            ? 'bg-white/5 text-slate-200 border border-white/5'
                            : 'bg-primary/20 text-white border border-primary/20'
                            }`}>
                            {msg.role === 'ai' ? (
                                <>
                                    {/* If this is the LAST message and we are loading, use LiveMessage */}
                                    {isLoading && i === messages.length - 1 ? (
                                        <div className="relative">
                                            <LiveMessage
                                                contentRef={streamContentRef}
                                                isStreaming={isLoading}
                                            />
                                            <div className="mt-4 flex items-center justify-center gap-3 text-sm font-mono text-ai/70 bg-ai/5 px-6 py-4 rounded-lg border border-ai/10">
                                                <div className="w-2 h-2 bg-ai rounded-full animate-ping shrink-0" />
                                                <span>{loadingStatus}</span>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="prose prose-invert prose-sm max-w-none prose-p:my-2 prose-headings:text-white prose-strong:text-primary prose-table:w-full prose-th:text-left prose-th:p-2 prose-td:p-2 prose-tr:border-b prose-tr:border-white/10 prose-thead:bg-white/5">
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                                        </div>
                                    )}
                                </>
                            ) : (
                                msg.content
                            )}
                        </div>
                    </motion.div>
                ))}
                <div ref={messagesEndRef} />
            </div>

            <motion.form
                onSubmit={handleSend}
                className="mt-4 relative shrink-0"
            >
                <input
                    type="text"
                    value={input}
                    onChange={(e) => { setInput(e.target.value); }}
                    placeholder="Ask complex questions about your data..."
                    className="w-full glass-input pr-12 !py-4"
                    disabled={isLoading}
                />
                <button
                    type="submit"
                    className="absolute right-2 top-2 bottom-2 p-2 bg-ai/20 text-ai hover:bg-ai hover:text-white rounded-lg transition-all disabled:opacity-50"
                    disabled={isLoading}
                >
                    <Send className="w-5 h-5" />
                </button>
            </motion.form>
        </div>
    );
};

export default ChatView;
