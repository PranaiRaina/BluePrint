import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Send, Bot, User, Sparkles } from 'lucide-react';

const ChatView: React.FC = () => {
    const [messages, setMessages] = useState([
        { role: 'ai', content: "Hello. I'm Bloom, your advanced financial analyst. I have access to your uploaded documents and real-time market data. What would you like to deep dive into today?" }
    ]);
    const [input, setInput] = useState('');

    const handleSend = (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim()) return;

        const newMsgs = [...messages, { role: 'user', content: input }];
        setMessages(newMsgs);
        setInput('');

        // Mock AI Response
        setTimeout(() => {
            setMessages(prev => [...prev, {
                role: 'ai',
                content: "I've analyzed the correlation between your 'Tech_Sector_Trends' document and current NVDA movements. It appears your exposure is optimal, though a 5% hedge could reduce downside risk."
            }]);
        }, 1500);
    };

    return (
        <div className="w-full h-screen max-h-screen pt-4 pb-4 px-4 flex flex-col max-w-5xl mx-auto">
            <div className="flex items-center gap-3 mb-6 p-4 border-b border-white/5">
                <div className="w-10 h-10 rounded-full bg-ai/20 flex items-center justify-center">
                    <Sparkles className="text-ai w-5 h-5" />
                </div>
                <div>
                    <h2 className="text-xl font-bold text-white">Deep Dive Analyst</h2>
                    <p className="text-xs text-emerald-400">Online • Context Output: High</p>
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
                        <div className={`p-4 rounded-2xl max-w-[80%] text-sm leading-relaxed ${msg.role === 'ai'
                                ? 'bg-white/5 text-slate-200 border border-white/5'
                                : 'bg-primary/20 text-white border border-primary/20'
                            }`}>
                            {msg.content}
                        </div>
                    </motion.div>
                ))}
            </div>

            <form onSubmit={handleSend} className="mt-4 relative">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ask complex questions about your data..."
                    className="w-full glass-input pr-12 !py-4"
                />
                <button
                    type="submit"
                    className="absolute right-2 top-2 bottom-2 p-2 bg-ai/20 text-ai hover:bg-ai hover:text-white rounded-lg transition-all"
                >
                    <Send className="w-5 h-5" />
                </button>
            </form>
        </div>
    );
};

export default ChatView;
