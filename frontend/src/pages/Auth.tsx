import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, ArrowRight, Loader2 } from 'lucide-react';
import { supabase } from '../lib/supabase';

const Auth: React.FC = () => {
    const [loading, setLoading] = useState(false);

    const handleLogin = async (provider: 'google' | 'azure') => {
        try {
            setLoading(true);
            const { error } = await supabase.auth.signInWithOAuth({
                provider: provider,
                options: {
                    redirectTo: window.location.origin
                }
            });
            if (error) throw error;
        } catch (error) {
            console.error('Error logging in:', error);
            alert('Error logging in. Please check console for details.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
            {/* Background Ambient Glow removed in favor of global Aura */}

            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.8 }}
                className="glass-card p-8 md:p-12 w-full max-w-md relative z-10 text-center"
            >
                <div className="flex justify-center mb-6">
                    <img src="/logo.png" alt="BluePrint" className="w-20 h-20 rounded-2xl shadow-lg shadow-primary/20" />
                </div>

                <h1 className="text-4xl font-sans font-bold mb-2 bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
                    BluePrint
                </h1>
                <p className="text-text-secondary mb-8 text-lg">
                    Agentic Financial Intelligence
                </p>

                <div className="space-y-4">
                    <button
                        onClick={() => handleLogin('google')}
                        disabled={loading}
                        className="w-full glass-input hover:bg-white/10 flex items-center justify-center gap-3 group transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : (
                            <>
                                <img src="https://www.svgrepo.com/show/355037/google.svg" alt="Google" className="w-5 h-5" />
                                <span className="font-medium">Continue with Google</span>
                                <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity translate-x-[-10px] group-hover:translate-x-0" />
                            </>
                        )}
                    </button>

                    <div className="relative">
                        <div className="absolute inset-0 flex items-center">
                            <span className="w-full border-t border-white/10" />
                        </div>
                        <div className="relative flex justify-center text-xs uppercase">
                            <span className="bg-[#0f172a] px-2 text-text-secondary">Or continue with email</span>
                        </div>
                    </div>

                    <div className="space-y-3">
                        <input
                            type="email"
                            placeholder="name@company.com"
                            className="w-full glass-input bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-white placeholder:text-white/20 focus:outline-none focus:border-primary/50 transition-colors"
                        />
                        <button
                            disabled
                            className="w-full bg-primary/20 text-primary border border-primary/20 rounded-lg px-4 py-3 font-medium opacity-50 cursor-not-allowed hover:bg-primary/30 transition-colors"
                        >
                            Continue with Email
                        </button>
                    </div>
                </div>

                <p className="mt-8 text-xs text-text-secondary/50">
                    Secure Enterprise Connection • 256-bit Encryption
                </p>
            </motion.div>
        </div>
    );
};

export default Auth;
