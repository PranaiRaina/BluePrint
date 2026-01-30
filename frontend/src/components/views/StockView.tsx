import React from 'react';
import { TrendingUp, TrendingDown, RefreshCcw } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const StockView: React.FC = () => {
    const data = [
        { time: '9:30', value: 150 },
        { time: '10:00', value: 155 },
        { time: '10:30', value: 153 },
        { time: '11:00', value: 158 },
        { time: '11:30', value: 162 },
        { time: '12:00', value: 160 },
        { time: '12:30', value: 165 },
    ];

    return (
        <div className="w-full max-w-5xl mx-auto pt-10 px-4">
            <div className="flex justify-between items-end mb-8">
                <div>
                    <h1 className="text-3xl font-bold text-white mb-2">Market Pro</h1>
                    <p className="text-text-secondary">Real-time market signals and alpha generation.</p>
                </div>
                <button className="neon-button flex items-center gap-2 text-sm">
                    <RefreshCcw className="w-4 h-4" /> Sync Data
                </button>
            </div>

            {/* Tickers */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                {[
                    { sym: 'NVDA', price: '824.50', change: '+2.4%', up: true },
                    { sym: 'AAPL', price: '182.10', change: '-0.5%', up: false },
                    { sym: 'MSFT', price: '415.20', change: '+1.1%', up: true },
                ].map((stock, i) => (
                    <div key={i} className="glass-card p-4 flex justify-between items-center">
                        <div>
                            <h3 className="text-lg font-bold text-white">{stock.sym}</h3>
                            <span className="text-xs text-text-secondary">NASDAQ</span>
                        </div>
                        <div className="text-right">
                            <div className="text-xl font-mono text-white">${stock.price}</div>
                            <div className={`text-sm font-bold flex items-center justify-end gap-1 ${stock.up ? 'text-primary' : 'text-red-400'}`}>
                                {stock.up ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                {stock.change}
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Main Chart */}
            <div className="glass-card p-6 h-96 w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data}>
                        <defs>
                            <linearGradient id="colorStock" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#10B981" stopOpacity={0.3} />
                                <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
                        <XAxis dataKey="time" stroke="#94A3B8" fontSize={12} tickLine={false} axisLine={false} />
                        <YAxis domain={['auto', 'auto']} stroke="#94A3B8" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(val: unknown) => `$${String(val)}`} />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#1E293B', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                            itemStyle={{ color: '#fff' }}
                        />
                        <Area type="monotone" dataKey="value" stroke="#10B981" strokeWidth={2} fillOpacity={1} fill="url(#colorStock)" />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default StockView;
