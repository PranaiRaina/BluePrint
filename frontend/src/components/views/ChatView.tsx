import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { agentService } from '../../services/agent';
import { Send, Bot, User, Sparkles } from 'lucide-react';
import type { Session } from '@supabase/supabase-js';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ChatViewProps {
    session: Session;
    sessionId: string;
}

const ChatView: React.FC<ChatViewProps> = ({ session, sessionId }) => {
    const defaultMessage = { role: 'ai', content: "Hello. I'm Bloom, your advanced financial analyst. I have access to your uploaded documents and real-time market data. What would you like to deep dive into today?" };

    const [messages, setMessages] = useState([defaultMessage]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [loadingStatus, setLoadingStatus] = useState("Thinking...");

    useEffect(() => {
        const loadHistory = async () => {
            if (session?.user?.id) {
                // Reset to default on switch
                setMessages([defaultMessage]);

                if (sessionId && sessionId !== 'new') {
                    setIsLoading(true);
                    const history = await agentService.getHistory(sessionId, session);
                    if (history && history.length > 0) {
                        setMessages(history);
                    }
                    setIsLoading(false);
                }
            }
        };
        loadHistory();
    }, [session, sessionId]);

    const handleSend = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;

        const userQuery = input;

        // Add User Message
        const newMsgs = [...messages, { role: 'user', content: userQuery }];
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
                userQuery,
                session,
                session.user.id,
                {
                    onStatus: (status) => {
                        setLoadingStatus(status);
                    },
                    onToken: (token) => {
                        fullResponse += token;
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

    return (
        <div className="w-full h-screen max-h-screen pt-4 pb-4 px-4 flex flex-col max-w-5xl mx-auto">
            <div className="flex items-center gap-3 mb-6 p-4 border-b border-white/5">
                <div className="w-10 h-10 rounded-full bg-ai/20 flex items-center justify-center">
                    <Sparkles className="text-ai w-5 h-5" />
                </div>
                <div>
                    <h2 className="text-xl font-bold text-white">Deep Dive Analyst</h2>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto space-y-4 pr-2 custom-scrollbar">
                {messages.map((msg, i) => (
                    <motion.div
                        key={i}
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className={`flex gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
                    >
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${msg.role === 'ai' ? 'bg-ai/20 text-ai' : 'bg-white/10 text-white'}`}>
                            {msg.role === 'ai' ? <Bot className="w-4 h-4" /> : <User className="w-4 h-4" />}
                        </div>
                        <div className={`p-4 rounded-2xl max-w-[85%] text-sm leading-relaxed overflow-hidden min-h-[3.5rem] ${msg.role === 'ai'
                            ? 'bg-white/5 text-slate-200 border border-white/5'
                            : 'bg-primary/20 text-white border border-primary/20'
                            }`}>
                            {msg.role === 'ai' ? (
                                <div className="prose prose-invert prose-sm max-w-none prose-p:my-2 prose-headings:text-white prose-strong:text-primary prose-table:w-full prose-th:text-left prose-th:p-2 prose-td:p-2 prose-tr:border-b prose-tr:border-white/10 prose-thead:bg-white/5">
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                                    {msg.content.length === 0 && <span className="animate-pulse inline-block w-1.5 h-4 bg-ai/50 align-middle"></span>}
                                </div>
                            ) : (
                                msg.content
                            )}
                        </div>
                    </motion.div>
                ))}
                {isLoading && (
                    <div className="flex gap-4">
                        <div className="w-8 h-8 rounded-full bg-ai/20 flex items-center justify-center shrink-0">
                            <Bot className="w-4 h-4 text-ai animate-pulse" />
                        </div>
                        <div className="p-4 rounded-2xl bg-white/5 text-slate-400 border border-white/5 text-xs">
                            {loadingStatus}
                        </div>
                    </div>
                )}
            </div>

            <form onSubmit={handleSend} className="mt-4 relative">
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
