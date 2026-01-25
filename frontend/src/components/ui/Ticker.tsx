import React from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown } from 'lucide-react';

const Ticker: React.FC = () => {
    const stocks = [
        { sym: 'NVDA', val: '824.50', chg: '+2.4%', up: true },
        { sym: 'AAPL', val: '182.10', chg: '-0.5%', up: false },
        { sym: 'BTC', val: '64,230', chg: '+1.8%', up: true },
        { sym: 'TSLA', val: '175.40', chg: '-1.2%', up: false },
        { sym: 'AMD', val: '180.20', chg: '+3.1%', up: true },
        { sym: 'GOOGL', val: '145.30', chg: '+0.4%', up: true },
        { sym: 'ETH', val: '3,450', chg: '+1.1%', up: true },
    ];

    return (
        <div className="w-full bg-background border-b border-white/5 overflow-hidden py-1 relative z-40">
            <div className="absolute top-0 left-0 w-20 h-full bg-gradient-to-r from-background to-transparent z-10" />
            <div className="absolute top-0 right-0 w-20 h-full bg-gradient-to-l from-background to-transparent z-10" />

            <motion.div
                className="flex items-center gap-12 whitespace-nowrap w-max"
                animate={{ x: [0, -1000] }}
                transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
            >
                {/* Duplicate the array to create seamless loop effect */}
                {[...stocks, ...stocks, ...stocks].map((stock, i) => (
                    <div key={i} className="flex items-center gap-2">
                        <span className="font-mono font-bold text-xs text-slate-300">{stock.sym}</span>
                        <div className={`flex items-center gap-1 text-xs ${stock.up ? 'text-primary' : 'text-red-400'}`}>
                            <span>{stock.val}</span>
                            {stock.up ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                            <span>{stock.chg}</span>
                        </div>
                    </div>
                ))}
            </motion.div>
        </div>
    );
};

export default Ticker;
