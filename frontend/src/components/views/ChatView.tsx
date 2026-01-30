import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { agentService } from '../../services/agent';
import { Send, Bot, Sparkles } from 'lucide-react';
import type { Session } from '@supabase/supabase-js';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ChatViewProps {
    session: Session;
    sessionId: string;
    initialQuery?: string;
    onTickers?: (tickers: string[]) => void;
}

const getUserInitials = (email?: string) => {
    if (!email) return 'U';
    return email.substring(0, 2).toUpperCase();
};

const ChatView: React.FC<ChatViewProps> = ({ session, sessionId, initialQuery, onTickers }) => {

    const [messages, setMessages] = useState<any[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isHistoryLoading, setIsHistoryLoading] = useState(false);
    const [loadingStatus, setLoadingStatus] = useState("Thinking...");

    const messagesEndRef = React.useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, isLoading, isHistoryLoading]);

    useEffect(() => {
        const loadHistory = async () => {
            if (session?.user?.id) {
                // If we have an initial query, we don't want to reset to default
                // because processQuery will be running (or has run) to add the user message.
                if (!initialQuery) {
                    setMessages([]);
                }

                if (sessionId && sessionId !== 'new') {
                    setIsHistoryLoading(true);
                    try {
                        const history = await agentService.getHistory(sessionId, session);
                        if (history && history.length > 0) {
                            if (!initialQuery) {
                                setMessages(history);
                            }
                        }
                    } catch (e) {
                        console.error("Failed to load history", e);
                    } finally {
                        setIsHistoryLoading(false);
                    }
                }
            }
        };
        loadHistory();
    }, [session, sessionId, initialQuery]);

    const processQuery = async (text: string) => {
        if (!text.trim()) return;

        // Add User Message
        const newMsgs = [...messages, { role: 'user', content: text }];
        setMessages(newMsgs);
        setInput('');
        setIsLoading(true);
        setLoadingStatus("Thinking...");

        // Add Empty AI Message Placeholder
        setMessages(prev => [...prev, { role: 'ai', content: '' }]);

        let fullResponse = "";
        let displayedResponse = "";

        // Smooth Typewriter Effect
        // We capture the stream in fullResponse, and update state from displayedResponse incrementally
        const typeWriter = setInterval(() => {
            if (displayedResponse.length < fullResponse.length) {
                // Determine chunk size based on lag to prevent falling too far behind
                const lag = fullResponse.length - displayedResponse.length;
                const chunkSize = lag > 50 ? 5 : (lag > 20 ? 3 : 2);

                const nextChunk = fullResponse.slice(displayedResponse.length, displayedResponse.length + chunkSize);
                displayedResponse += nextChunk;

                setMessages(prev => {
                    const lastMsg = prev[prev.length - 1];
                    if (lastMsg?.role === 'ai') {
                        return [
                            ...prev.slice(0, -1),
                            { ...lastMsg, content: displayedResponse }
                        ];
                    }
                    return prev;
                });
            }
        }, 20);

        try {
            await agentService.streamChat(
                text,
                session,
                sessionId || 'new', // Ensure valid session
                {
                    onStatus: (status) => {
                        setLoadingStatus(status);
                    },
                    onToken: (token) => {
                        fullResponse += token;
                    },
                    onTickers: (tickers) => {
                        if (onTickers) onTickers(tickers);
                    },
                    onComplete: () => {
                        clearInterval(typeWriter);
                        // Ensure final synchronization
                        setMessages(prev => {
                            const lastMsg = prev[prev.length - 1];
                            if (lastMsg?.role === 'ai') {
                                return [
                                    ...prev.slice(0, -1),
                                    { ...lastMsg, content: fullResponse }
                                ];
                            }
                            return prev;
                        });
                        setIsLoading(false);
                        setLoadingStatus("Thinking...");
                    },
                    onError: (err) => {
                        console.error(err);
                        clearInterval(typeWriter);
                        setMessages(prev => {
                            const lastMsg = prev[prev.length - 1];
                            const errorMsg = "\n\n[Error encountered]";
                            if (lastMsg?.role === 'ai') {
                                return [
                                    ...prev.slice(0, -1),
                                    { ...lastMsg, content: lastMsg.content + errorMsg }
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
            clearInterval(typeWriter);
            setIsLoading(false);
        }
    };

    const handleSend = async (e: React.FormEvent) => {
        e.preventDefault();
        if (input.trim() && !isLoading) {
            await processQuery(input);
        }
    };

    // Auto-Send Initial Query
    const hasSentInitial = React.useRef(false);
    useEffect(() => {
        if (initialQuery && !hasSentInitial.current) {
            hasSentInitial.current = true;
            processQuery(initialQuery);
        }
    }, [initialQuery]);

    return (
        <div className="w-full h-full pt-4 pb-4 px-4 flex flex-col max-w-5xl mx-auto">
            <div className="flex items-center gap-3 mb-6 p-4 border-b border-white/5 shrink-0">
                <div className="w-10 h-10 rounded-full bg-ai/20 flex items-center justify-center">
                    <Sparkles className="text-ai w-5 h-5" />
                </div>
                <div>
                    <h2 className="text-xl font-bold text-white">BluePrint Agent</h2>
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
                            {msg.role === 'ai' ? <Bot className="w-4 h-4" /> : <span className="font-serif text-xs">{getUserInitials(session?.user?.email)}</span>}
                        </div>
                        <div className={`p-4 rounded-2xl max-w-[85%] w-fit text-sm leading-relaxed overflow-hidden ${msg.role === 'ai'
                            ? 'bg-white/5 text-slate-200 border border-white/5'
                            : 'bg-primary/20 text-white border border-primary/20'
                            }`}>
                            {msg.role === 'ai' ? (
                                <div className="prose prose-invert prose-sm max-w-none prose-p:my-2 prose-headings:text-white prose-strong:text-primary prose-table:w-full prose-th:text-left prose-th:p-2 prose-td:p-2 prose-tr:border-b prose-tr:border-white/10 prose-thead:bg-white/5">
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                                    {isLoading && i === messages.length - 1 && (
                                        <div className="mt-2 flex items-center gap-2 text-xs font-mono text-ai/70 bg-ai/5 px-2 py-1 rounded border border-ai/10">
                                            <div className="w-1.5 h-1.5 bg-ai rounded-full animate-ping shrink-0" />
                                            <span>{loadingStatus}</span>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                msg.content
                            )}
                        </div>
                    </motion.div>
                ))}
                <div ref={messagesEndRef} />
            </div>

            <form onSubmit={handleSend} className="mt-4 relative shrink-0">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
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
            </form>
        </div>
    );
};

export default ChatView;
