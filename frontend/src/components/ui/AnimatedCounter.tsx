import React, { useEffect, useRef } from 'react';
import { useSpring, useMotionValue } from 'framer-motion';

interface AnimatedCounterProps {
    value: number;
    prefix?: string;
    suffix?: string;
    decimals?: number;
    className?: string;
}

const AnimatedCounter: React.FC<AnimatedCounterProps> = ({
    value,
    prefix = '',
    suffix = '',
    decimals = 2,
    className = ''
}) => {
    // 1. Create a MotionValue to store the number
    const motionValue = useMotionValue(value);

    // 2. Use a Spring for smooth physics-based animation
    const springValue = useSpring(motionValue, {
        damping: 30, // Higher = less bounce, more "smooth braking"
        stiffness: 100
    });

    // 3. Keep a ref to the display element
    const ref = useRef<HTMLSpanElement>(null);

    // 4. Update the MotionNumber when the prop 'value' changes
    useEffect(() => {
        motionValue.set(value);
    }, [value, motionValue]);

    // 5. Subscribe to the spring changes and update text content directly
    useEffect(() => {
        // Initialize with current spring value immediately on mount/ref availability
        if (ref.current) {
            ref.current.textContent = `${prefix}${springValue.get().toFixed(decimals)}${suffix}`;
        }

        const unsubscribe = springValue.on("change", (latest) => {
            if (ref.current) {
                ref.current.textContent = `${prefix}${latest.toFixed(decimals)}${suffix}`;
            }
        });
        return () => { unsubscribe(); };
    }, [springValue, decimals, prefix, suffix]);

    return (
        <span className={className}>
            {/* Invisible placeholder to reserve width and avoid layout shift */}
            <span className="invisible">{prefix}{value.toFixed(decimals)}{suffix}</span>
            <span ref={ref} className="absolute inset-0 text-right" />
        </span>
    );
};

export default AnimatedCounter;
