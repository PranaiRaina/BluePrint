import React, { useState } from 'react';
import { Home, Database, TrendingUp, LogOut, ChevronDown, User } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Session } from '@supabase/supabase-js';
import { supabase } from '../../lib/supabase';

interface NavbarProps {
    activeTab: 'overview' | 'market' | 'vault' | 'chat' | 'stocks';
    setActiveTab: (tab: 'overview' | 'market' | 'vault' | 'chat' | 'stocks') => void;
    session: Session | null;
}

const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab, session }) => {
    const [userMenuOpen, setUserMenuOpen] = useState(false);

    // Reordered: Vault (left), Home (middle), Stock Analytics (right)
    const tabs = [
        { id: 'vault', label: 'Vault', icon: Database },
        { id: 'overview', label: 'Home', icon: Home },
        { id: 'stocks', label: 'Stock Analytics', icon: TrendingUp },
    ];

    const handleSignOut = async () => {
        await supabase.auth.signOut();
    };

    // Get user initials from email
    const getUserInitials = () => {
        if (!session?.user?.email) return 'U';
        const email = session.user.email;
        return email.substring(0, 2).toUpperCase();
    };

    return (
        <motion.nav
            initial={{ y: -100 }}
            animate={{ y: 0 }}
            className="fixed top-0 left-0 right-0 h-16 bg-background/50 backdrop-blur-xl border-b border-white/5 z-50 flex items-center justify-between px-6 shadow-lg shadow-black/20"
        >
            {/* Logo Area */}
            <div className="flex items-center gap-3">
                <img src="/logo.png" alt="BluePrint" className="w-8 h-8 rounded-lg" />
                <span className="font-serif font-bold text-xl text-white tracking-wide">BluePrint</span>
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

            {/* User Menu with Sign Out */}
            <div className="relative">
                <button
                    onClick={() => setUserMenuOpen(!userMenuOpen)}
                    className="flex items-center gap-3 hover:bg-white/5 px-3 py-2 rounded-lg transition-colors"
                >
                    <div className="hidden md:flex flex-col items-end">
                        <span className="text-xs text-text-secondary truncate max-w-[150px]">
                            {session?.user?.email || 'User'}
                        </span>
                        <div className="flex items-center gap-1.5">
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                            <span className="text-xs font-mono text-emerald-400">Online</span>
                        </div>
                    </div>
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-ai flex items-center justify-center">
                        <span className="font-serif text-white text-xs">{getUserInitials()}</span>
                    </div>
                    <ChevronDown className={`w-4 h-4 text-text-secondary transition-transform ${userMenuOpen ? 'rotate-180' : ''}`} />
                </button>

                {/* Dropdown Menu */}
                <AnimatePresence>
                    {userMenuOpen && (
                        <motion.div
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            className="absolute top-full right-0 mt-2 w-48 glass-card border border-white/10 rounded-xl overflow-hidden z-50"
                        >
                            <div className="p-3 border-b border-white/10">
                                <div className="flex items-center gap-2">
                                    <User className="w-4 h-4 text-text-secondary" />
                                    <span className="text-sm text-white truncate">{session?.user?.email || 'User'}</span>
                                </div>
                            </div>
                            <button
                                onClick={handleSignOut}
                                className="w-full px-3 py-3 text-left hover:bg-red-500/10 transition-colors flex items-center gap-2 text-red-400"
                            >
                                <LogOut className="w-4 h-4" />
                                <span className="text-sm">Sign Out</span>
                            </button>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </motion.nav>
    );
};

export default Navbar;
