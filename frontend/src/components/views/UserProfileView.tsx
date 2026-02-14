import React, { useState, useRef } from 'react';
import { Mail, CreditCard, LayoutDashboard, Target, Lock } from 'lucide-react';
import type { Session } from '@supabase/supabase-js';
import StrategySettings from '../profile/StrategySettings';

interface UserProfileViewProps {
    session: Session;
    onAnalyze?: (ticker: string) => void;
    onViewAnalysis?: () => void;
}

const UserProfileView: React.FC<UserProfileViewProps> = ({ session }) => {
    const user = session.user;
    const email = user.email ?? 'No Email';

    // Section Refs for Scrolling
    const overviewRef = useRef<HTMLDivElement>(null);
    const strategyRef = useRef<HTMLDivElement>(null);
    const securityRef = useRef<HTMLDivElement>(null);

    const [activeSection, setActiveSection] = useState('overview');

    const scrollToSection = (sectionId: string, ref: React.RefObject<HTMLDivElement>) => {
        setActiveSection(sectionId);
        ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };

    const navItems = [
        { id: 'overview', label: 'Overview', icon: LayoutDashboard, ref: overviewRef },
        { id: 'strategy', label: 'Strategy', icon: Target, ref: strategyRef },
        { id: 'security', label: 'Security & Billing', icon: Lock, ref: securityRef },
    ];

    return (
        <div className="w-full h-full flex">
            {/* Left Side Navigation (Fixed) */}
            <div className="w-64 fixed h-[calc(100vh-4rem)] top-16 left-0 border-r border-white/5 bg-black/20 backdrop-blur-sm p-6 hidden md:block overflow-y-auto">
                <div className="mb-8">
                    <h2 className="text-xs text-slate-500 font-bold uppercase tracking-widest mb-4">On This Page</h2>
                    <div className="space-y-1">
                        {navItems.map((item) => (
                            <button
                                key={item.id}
                                onClick={() => { scrollToSection(item.id, item.ref); }}
                                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 group ${activeSection === item.id
                                    ? 'bg-primary/10 text-primary'
                                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                                    }`}
                            >
                                <item.icon className={`w-4 h-4 ${activeSection === item.id ? 'text-primary' : 'text-slate-500 group-hover:text-slate-300'}`} />
                                {item.label}
                                {activeSection === item.id && (
                                    <div className="ml-auto w-1.5 h-1.5 rounded-full bg-primary shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
                                )}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Mini Profile Summary in Nav */}
                <div className="p-4 rounded-xl bg-white/5 border border-white/5">
                    <div className="text-xs text-slate-500 mb-2">Current Plan</div>
                    <div className="text-white font-bold text-sm mb-1">Pro Member</div>
                    <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden mb-2">
                        <div className="w-3/4 h-full bg-primary" />
                    </div>
                    <div className="text-[10px] text-slate-400">Renews Feb 28, 2026</div>
                </div>
            </div>

            {/* Main Content Area (Scrollable) */}
            <div className="flex-1 ml-0 md:ml-64 p-8 md:p-12 pb-32 max-w-5xl mx-auto">
                <h1 className="text-4xl font-serif font-bold text-white mb-2">My Profile</h1>
                <p className="text-slate-400 mb-10">Manage your family office settings, portfolio strategy, and security.</p>

                {/* 1. Overview Section */}
                <div ref={overviewRef} className="scroll-mt-24">
                    <div className="glass-card p-8 rounded-3xl border border-white/10 flex items-center gap-6">
                        <div className="w-20 h-20 rounded-full bg-gradient-to-br from-primary to-ai flex items-center justify-center text-3xl font-serif text-white shadow-xl shadow-primary/20">
                            {email.substring(0, 2).toUpperCase()}
                        </div>
                        <div>
                            <h2 className="text-2xl font-bold text-white mb-1">Welcome back, Rishi</h2>
                            <div className="flex items-center gap-2 text-text-secondary mb-3">
                                <Mail className="w-4 h-4" />
                                <span>{email}</span>
                            </div>
                            <div className="flex gap-2">
                                <span className="px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 text-xs font-mono border border-emerald-500/20">
                                    Verified Investor
                                </span>
                            </div>
                        </div>
                        <button className="ml-auto px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-sm font-medium text-white transition-colors border border-white/10">
                            Edit Profile
                        </button>
                    </div>
                </div>

                <hr className="border-t border-dashed border-white/10 my-12" />

                {/* 2. Strategy Section */}
                <div ref={strategyRef} className="scroll-mt-24">
                    <StrategySettings session={session} />
                </div>

                <hr className="border-t border-dashed border-white/10 my-12" />

                {/* 3. Security & Billing */}
                <div ref={securityRef} className="scroll-mt-24">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400">
                            <Lock className="w-5 h-5" />
                        </div>
                        <h2 className="text-2xl font-bold text-white">Security & Billing</h2>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Security */}
                        <div className="glass-card p-6 rounded-2xl border border-white/10">
                            <h3 className="text-lg font-bold text-white mb-4">Security Settings</h3>
                            <div className="space-y-4">
                                <div className="flex justify-between items-center p-3 hover:bg-white/5 rounded-lg transition-colors cursor-pointer group">
                                    <div>
                                        <div className="text-white text-sm font-medium">Password</div>
                                        <div className="text-xs text-slate-500">Last changed 3 months ago</div>
                                    </div>
                                    <button className="text-xs text-primary group-hover:underline">Update</button>
                                </div>
                                <div className="flex justify-between items-center p-3 hover:bg-white/5 rounded-lg transition-colors cursor-pointer group">
                                    <div>
                                        <div className="text-white text-sm font-medium">2-Factor Auth</div>
                                        <div className="text-xs text-emerald-400">Enabled</div>
                                    </div>
                                    <button className="text-xs text-primary group-hover:underline">Configure</button>
                                </div>
                            </div>
                        </div>

                        {/* Billing */}
                        <div className="glass-card p-6 rounded-2xl border border-white/10">
                            <div className="flex items-center gap-2 mb-4">
                                <CreditCard className="w-5 h-5 text-purple-400" />
                                <h3 className="text-lg font-bold text-white">Billing Method</h3>
                            </div>
                            <div className="p-4 bg-gradient-to-br from-purple-500/10 to-blue-500/10 border border-purple-500/20 rounded-xl">
                                <div className="flex justify-between items-start mb-2">
                                    <span className="text-white font-mono text-sm">•••• 4242</span>
                                    <span className="text-xs text-white/50">Exp 12/28</span>
                                </div>
                                <div className="text-xs text-purple-300">Next billing date: Feb 28, 2026</div>
                            </div>
                            <div className="mt-4 flex gap-2">
                                <button className="flex-1 py-2 rounded-lg bg-white/5 text-xs text-white hover:bg-white/10 transition-colors">History</button>
                                <button className="flex-1 py-2 rounded-lg bg-white/5 text-xs text-white hover:bg-white/10 transition-colors">Edit</button>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Bottom Spacer */}
                <div className="h-24" />
            </div>
        </div>
    );
};

export default UserProfileView;
