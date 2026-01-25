import React from 'react';
import { motion } from 'framer-motion';
import { Sparkles, ArrowRight } from 'lucide-react';

interface AuthProps {
    onLogin: () => void;
}

const Auth: React.FC<AuthProps> = ({ onLogin }) => {
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
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary to-ai flex items-center justify-center shadow-lg shadow-primary/20">
                        <Sparkles className="text-white w-8 h-8" />
                    </div>
                </div>

                <h1 className="text-4xl font-sans font-bold mb-2 bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
                    BoostUp
                </h1>
                <p className="text-text-secondary mb-8 text-lg">
                    Agentic Financial Intelligence
                </p>

                <div className="space-y-4">
                    <button
                        onClick={onLogin}
                        className="w-full glass-input hover:bg-white/10 flex items-center justify-center gap-3 group transition-all"
                    >
                        <img src="https://www.svgrepo.com/show/355037/google.svg" alt="Google" className="w-5 h-5" />
                        <span className="font-medium">Continue with Google</span>
                        <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity translate-x-[-10px] group-hover:translate-x-0" />
                    </button>

                    <button
                        onClick={onLogin}
                        className="w-full glass-input hover:bg-white/10 flex items-center justify-center gap-3 group transition-all"
                    >
                        <img src="https://www.svgrepo.com/show/355118/microsoft.svg" alt="Microsoft" className="w-5 h-5" />
                        <span className="font-medium">Continue with Microsoft</span>
                    </button>
                </div>

                <p className="mt-8 text-xs text-text-secondary/50">
                    Secure Enterprise Connection • 256-bit Encryption
                </p>
            </motion.div>
        </div>
    );
};

export default Auth;
