import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

interface TypewriterProps {
    text: string;
    speed?: number;
    className?: string;
    onComplete?: () => void;
}

const Typewriter: React.FC<TypewriterProps> = ({ text, speed = 50, className, onComplete }) => {
    const [displayedText, setDisplayedText] = useState('');
    const [showCursor, setShowCursor] = useState(true);

    useEffect(() => {
        let i = 0;
        setDisplayedText('');
        setShowCursor(true);

        const interval = setInterval(() => {
            i++;
            setDisplayedText(text.substring(0, i));

            if (i >= text.length) {
                clearInterval(interval);
                if (onComplete) onComplete();

                // Fade out cursor after 2 seconds
                setTimeout(() => {
                    setShowCursor(false);
                }, 2000);
            }
        }, speed);

        return () => { clearInterval(interval); };
    }, [text, speed, onComplete]);

    return (
        <motion.span className={className}>
            {displayedText}
            <motion.span
                animate={{ opacity: showCursor ? [1, 0, 1] : 0 }}
                transition={{
                    opacity: { duration: 0.8, repeat: showCursor ? Infinity : 0, ease: "linear" }
                }}
                className="inline-block w-[3px] h-[1em] bg-primary ml-1 align-middle"
            />
        </motion.span>
    );
};

export default Typewriter;
