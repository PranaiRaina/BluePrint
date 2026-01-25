import React from 'react';
import { Home, Database, TrendingUp, MessageSquare, Code } from 'lucide-react';
import { motion } from 'framer-motion';

interface NavbarProps {
    activeTab: 'overview' | 'vault' | 'market' | 'chat';
    setActiveTab: (tab: 'overview' | 'vault' | 'market' | 'chat') => void;
}

const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab }) => {
    const tabs = [
        { id: 'overview', label: 'Overview', icon: Home },
        { id: 'vault', label: 'Data Vault', icon: Database },
        { id: 'market', label: 'Market Pro', icon: TrendingUp },
        { id: 'chat', label: 'Deep Dive', icon: MessageSquare },
    ];

    return (
        <motion.nav
            initial={{ y: -100 }}
            animate={{ y: 0 }}
            className="fixed top-0 left-0 right-0 h-16 bg-background/50 backdrop-blur-xl border-b border-white/5 z-50 flex items-center justify-between px-6 shadow-lg shadow-black/20"
        >
            {/* Logo Area */}
            <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-ai flex items-center justify-center shadow-lg shadow-primary/20">
                    <Code className="text-white w-5 h-5" />
                </div>
                <span className="font-serif font-bold text-xl text-white tracking-wide">Bloom</span>
            </div>

            {/* Navigation Tabs */}
            <div className="flex items-center gap-1 bg-white/5 p-1 rounded-xl border border-white/5">
                {tabs.map((tab) => {
                    const isActive = activeTab === tab.id;
                    const Icon = tab.icon;

                    return (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id as any)}
                            className={`flex items-center gap-2 px-4 py-1.5 rounded-lg transition-all duration-300 relative ${isActive
                                    ? 'text-white'
                                    : 'text-text-secondary hover:text-white hover:bg-white/5'
                                }`}
                        >
                            {isActive && (
                                <motion.div
                                    layoutId="activeNavTab"
                                    className="absolute inset-0 bg-primary/20 border border-primary/50 rounded-lg shadow-[0_0_10px_rgba(16,185,129,0.3)]"
                                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                                />
                            )}
                            <Icon className={`w-4 h-4 relative z-10 ${isActive ? 'text-primary' : ''}`} />
                            <span className="text-sm font-medium relative z-10">{tab.label}</span>
                        </button>
                    );
                })}
            </div>

            {/* Status / Connect */}
            <div className="flex items-center gap-3">
                <div className="hidden md:flex flex-col items-end">
                    <span className="text-[10px] text-text-secondary uppercase tracking-wider font-bold">System Status</span>
                    <div className="flex items-center gap-1.5">
                        <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                        <span className="text-xs font-mono text-emerald-400">Online</span>
                    </div>
                </div>
                <div className="w-8 h-8 rounded-full bg-white/10 border border-white/10 flex items-center justify-center">
                    <span className="font-serif text-white text-xs">JD</span>
                </div>
            </div>
        </motion.nav>
    );
};

export default Navbar;
