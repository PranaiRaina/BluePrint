import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { MessageSquare, Plus, Trash2, ChevronLeft, ChevronRight } from 'lucide-react';
import type { Session } from '@supabase/supabase-js';
import { agentService, type ChatSession } from '../../services/agent';

interface SidebarProps {
    session: Session;
    className?: string;
    activeSessionId: string;
    onSessionSelect: (session: ChatSession) => void;
    onNewChat: () => void;
    refreshTrigger: number;
    isCollapsed: boolean;
    onToggle: () => void;
}

export type { ChatSession };

const Sidebar: React.FC<SidebarProps> = ({
    session,
    className = '',
    activeSessionId,
    onSessionSelect,
    onNewChat,
    refreshTrigger,
    isCollapsed,
    onToggle
}) => {
    const [sessions, setSessions] = useState<ChatSession[]>([]);
    const [isLoading, setIsLoading] = useState(false);


    // Expose a refresh method or listen to events if needed, but simple prop trigger is easiest
    // For now, we load on mount. 

    const loadSessions = React.useCallback(async () => {
        setIsLoading(true);
        const list = await agentService.getSessions(session);
        setSessions(list);
        setIsLoading(false);
    }, [session]);

    // Initial Load
    React.useEffect(() => {
        void loadSessions();
    }, [loadSessions, refreshTrigger]);

    const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
        e.stopPropagation();
        if (confirm("Delete this chat?")) {
            const success = await agentService.deleteSession(sessionId, session);
            if (success) {
                setSessions(prev => prev.filter(s => s.session_id !== sessionId));
                if (activeSessionId === sessionId) {
                    onNewChat(); // Go to new chat if current deleted
                }
            }
        }
    };

    const handleNewChat = () => {
        onNewChat();
        // Optimistically add to list? No, new entries appear after creation.
        // Actually, creating a new chat usually happens when first message sent OR explicit create.
        // For this UI, "New Chat" just clears the view. Backend creates session on msg or explicit call.
    };

    // Grouping logic (Today, Yesterday, etc)
    const groupedSessions = (sessions || []).reduce<Record<string, ChatSession[]>>((groups, s) => {
        // Handle UTC strings from backend (YYYY-MM-DD HH:MM:SS) by forcing UTC interpretation
        const parseDate = (str: string) => {
            if (!str) return new Date();
            let safe = str.replace(' ', 'T');
            if (!safe.endsWith('Z') && !safe.includes('+')) safe += 'Z';
            return new Date(safe);
        };

        const date = parseDate(s.updated_at || s.created_at);
        const today = new Date();
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);

        let key = 'Older';

        // Check if date is today (or future, to handle timezone discrepencies)
        const isToday = date.toDateString() === today.toDateString();
        // user requested "Today", "Previous 7 Days", "Older". 
        // "Yesterday" falls into "Previous 7 Days".
        // Ensure "Previous 7 Days" covers everything from Yesterday back to 7 days ago.
        const isPrevious7Days = date > new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000) && !isToday;

        if (isToday) key = 'Today';
        else if (isPrevious7Days) key = 'Previous 7 Days';
        // else Older

        if (Object.prototype.hasOwnProperty.call(groups, key)) {
            groups[key].push(s);
        } else {
            groups[key] = [s];
        }
        return groups;
    }, {});

    const groupOrder = ['Today', 'Previous 7 Days', 'Older'];

    return (
        <motion.div
            animate={{ width: isCollapsed ? 64 : 260 }}
            transition={{ duration: 0.15, ease: "linear" }}
            className={`flex flex-col h-[calc(100vh-64px)] bg-black/80 backdrop-blur-xl border-r border-white/10 transition-all duration-150 ease-linear overflow-hidden ${className}`}
        >
            {/* Header / Toggle */}
            <div className="p-4 flex items-center justify-between border-b border-white/5">
                {!isCollapsed && <span className="text-sm font-medium text-slate-400 whitespace-nowrap">History</span>}
                <button
                    onClick={onToggle}
                    className="p-1 hover:bg-white/10 rounded text-slate-400 transition-colors"
                >
                    {isCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
                </button>
            </div>

            {/* New Chat Button */}
            <div className="p-3">
                <button
                    onClick={handleNewChat}
                    className={`w-full flex items-center gap-2 p-3 rounded-xl border border-white/10 hover:border-primary/50 hover:bg-white/5 transition-all group ${isCollapsed ? 'justify-center' : ''}`}
                >
                    <Plus className="w-5 h-5 text-primary group-hover:scale-110 transition-transform" />
                    {!isCollapsed && <span className="text-sm font-medium text-white whitespace-nowrap">New Chat</span>}
                </button>
            </div>

            {/* Session List */}
            <div className="flex-1 overflow-y-auto overflow-x-hidden p-2 space-y-4 custom-scrollbar">
                {isLoading && !isCollapsed && (
                    <div className="text-center text-xs text-slate-500 py-4">Loading...</div>
                )}

                {!isLoading && sessions.length === 0 && !isCollapsed && (
                    <div className="text-center text-xs text-slate-500 py-4">No history yet.</div>
                )}

                {groupOrder.map(group => {
                    const groupSessions = groupedSessions[group] || [];
                    if (groupSessions.length === 0) return null;

                    if (isCollapsed) {
                        // When collapsed, we merge everything or just show them in order? 
                        // To keep it simple, we just render the sessions without group headers, iterate anyway
                    }

                    return (
                        <div key={group}>
                            {!isCollapsed && <h3 className="px-3 text-xs font-semibold text-slate-500 mb-2 whitespace-nowrap">{group}</h3>}
                            <div className="space-y-1">
                                {groupSessions.map(session => (
                                    <button
                                        key={session.session_id}
                                        onClick={() => { onSessionSelect(session); }}
                                        title={isCollapsed ? session.title : undefined}
                                        className={`group w-full text-left p-2 rounded-lg text-sm flex items-center gap-3 transition-colors relative 
                                            ${activeSessionId === session.session_id ? 'bg-primary/10 text-white' : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'}
                                            ${isCollapsed ? 'justify-center' : ''}
                                        `}
                                    >
                                        <MessageSquare size={16} className={`shrink-0 ${activeSessionId === session.session_id ? 'text-primary' : 'opacity-50'}`} />

                                        {!isCollapsed && (
                                            <>
                                                <span className="truncate flex-1">{session.title || "Untitled Chat"}</span>
                                                {/* Delete Action (Hover only) */}
                                                <div
                                                    role="button"
                                                    tabIndex={0}
                                                    onClick={(e) => { void handleDelete(e, session.session_id); }}
                                                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { void handleDelete(e as unknown as React.MouseEvent, session.session_id); } }}
                                                    className="absolute right-2 opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 rounded text-red-400 transition-all"
                                                >
                                                    <Trash2 size={12} />
                                                </div>
                                            </>
                                        )}
                                    </button>
                                ))}
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Footer / User Profile snippet could go here */}
        </motion.div>
    );
};

export default Sidebar;
