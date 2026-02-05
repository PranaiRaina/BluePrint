
import React from 'react';
import { ShieldAlert } from 'lucide-react';
import { motion } from 'framer-motion';

const DisclaimerFooter: React.FC = () => {
    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="mt-4 flex flex-col gap-2 rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-4 text-xs text-yellow-200/80 shadow-sm"
        >
            <div className="flex items-center gap-2 font-semibold text-yellow-400">
                <ShieldAlert className="h-4 w-4" />
                <span>Not Financial Advice</span>
            </div>
            <p className="leading-relaxed opacity-90">
                This content is for informational purposes only and should not be construed as financial, legal, or investment advice.
                All data is simulated or aggregated for demonstration. Please consult a qualified professional before making investment decisions.
            </p>
        </motion.div>
    );
};

export default DisclaimerFooter;
