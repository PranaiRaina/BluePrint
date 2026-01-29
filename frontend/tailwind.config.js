/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                background: '#0F172A', // Deep Navy
                surface: '#1E293B',    // Slate 800
                primary: {
                    DEFAULT: '#10B981',  // Emerald
                    glow: '#34D399',
                },
                ai: {
                    DEFAULT: '#8B5CF6',  // Violet
                    glow: '#A78BFA',
                },
                text: {
                    primary: '#F8FAFC', // Slate 50
                    secondary: '#94A3B8', // Slate 400
                }
            },
            fontFamily: {
                sans: ['Inter', 'sans-serif'],
                serif: ['Playfair Display', 'serif'],
                mono: ['JetBrains Mono', 'monospace'],
            },
            animation: {
                'pulse-glow': 'pulse-glow 3s infinite',
                'lift': 'lift 0.8s cubic-bezier(0.4, 0, 0.2, 1) forwards',
                'fadeIn': 'fadeIn 0.3s ease-in-out',
            },
            keyframes: {
                'pulse-glow': {
                    '0%, 100%': { boxShadow: '0 0 15px rgba(139, 92, 246, 0.1)' },
                    '50%': { boxShadow: '0 0 30px rgba(139, 92, 246, 0.3)' },
                },
                'lift': {
                    '0%': { transform: 'translateY(0)' },
                    '100%': { transform: 'translateY(-30vh)' }
                },
                'fadeIn': {
                    '0%': { opacity: '0', transform: 'translateY(-10px)' },
                    '100%': { opacity: '1', transform: 'translateY(0)' }
                }
            }
        },
    },
    plugins: [],
}
