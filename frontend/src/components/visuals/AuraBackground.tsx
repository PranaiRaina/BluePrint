import React from 'react';
import { motion } from 'framer-motion';

const AuraBackground: React.FC = () => {
    return (
        <div className="fixed inset-0 w-full h-full overflow-hidden -z-10 pointer-events-none bg-background">
            {/* Primary Emerald Aura */}
            <motion.div
                animate={{
                    x: [0, 100, -100, 0],
                    y: [0, -100, 100, 0],
                    scale: [1, 1.2, 1, 1.2, 1],
                    opacity: [0.3, 0.5, 0.3]
                }}
                transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                className="absolute top-[20%] left-[20%] w-[500px] h-[500px] bg-primary/20 rounded-full blur-[120px]"
            />

            {/* AI Violet Aura */}
            <motion.div
                animate={{
                    x: [0, -150, 150, 0],
                    y: [0, 100, -100, 0],
                    opacity: [0.2, 0.4, 0.2]
                }}
                transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
                className="absolute top-[60%] right-[20%] w-[600px] h-[600px] bg-ai/10 rounded-full blur-[140px]"
            />

            {/* Deep Blue Depth Aura */}
            <motion.div
                animate={{
                    x: [0, 100, -50, 0],
                    y: [0, 50, -50, 0],
                    scale: [1, 0.8, 1]
                }}
                transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
                className="absolute top-[10%] right-[30%] w-[400px] h-[400px] bg-blue-500/10 rounded-full blur-[100px]"
            />

            {/* Ambient Noise/Texture Overlay for "Organic" feel */}
            <div className="absolute inset-0 opacity-[0.03] bg-[url('https://grainy-gradients.vercel.app/noise.svg')] mix-blend-overlay"></div>
        </div>
    );
};

export default AuraBackground;
