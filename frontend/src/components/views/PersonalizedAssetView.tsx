import React, { useState, useEffect } from 'react';
import { AreaChart, Area, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { TrendingUp, TrendingDown, DollarSign, Calendar, Target, AlertTriangle, PieChart, Zap, FileBarChart, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Session } from '@supabase/supabase-js';
import { agentService, type StockData } from '../../services/agent';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface PersonalizedAssetViewProps {
    session: Session;
    ticker: string;
    quantity: number;
    avgPrice: number;
    buyDate?: string;
    totalPortfolioValue?: number;
    onClose?: () => void;
}

interface ReportData {
    ticker: string;
    report_date: string;
    market_report: string;
    news_report: string;
    fundamentals_report: string;
    sentiment_report: string;
}

const PersonalizedAssetView: React.FC<PersonalizedAssetViewProps> = ({
    session,
    ticker,
    quantity,
    avgPrice,
    buyDate,
    totalPortfolioValue = 0
}) => {
    const [stockData, setStockData] = useState<StockData | null>(null);
    const [loading, setLoading] = useState(true);
    const [hoverData, setHoverData] = useState<{ value: number; label?: string } | null>(null);

    // Report state
    const [reportData, setReportData] = useState<ReportData | null>(null);
    const [reportLoading, setReportLoading] = useState(false);
    const [reportProgress, setReportProgress] = useState<string[]>([]);
    const [reportChecked, setReportChecked] = useState(false);
    const [reportVisible, setReportVisible] = useState(false);

    // Reset report state when ticker changes
    useEffect(() => {
        setReportData(null);
        setReportProgress([]);
        setReportLoading(false);
        setReportChecked(false);
        setReportVisible(false);
    }, [ticker]);

    useEffect(() => {
        const fetchData = async () => {
            if (!ticker) return;
            setLoading(true);
            try {
                const data = await agentService.getStockData(ticker, session, '1y', buyDate);
                setStockData(data);
            } catch (error) {
                console.error('Failed to fetch stock data:', error);
            } finally {
                setLoading(false);
            }
        };
        void fetchData();
    }, [ticker, session, buyDate]);

    // Check for cached report on mount
    useEffect(() => {
        const checkCachedReport = async () => {
            if (!ticker || reportChecked) return;
            try {
                const token = session.access_token;
                const res = await fetch(`http://localhost:8001/v1/reports/${ticker.toUpperCase()}`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (res.ok) {
                    const data = await res.json() as ReportData;
                    setReportData(data);
                }
            } catch {
                // No cached report, that's fine
            } finally {
                setReportChecked(true);
            }
        };
        void checkCachedReport();
    }, [ticker, session, reportChecked]);

    // Generate report handler
    const handleGenerateReport = async (force = false) => {
        setReportLoading(true);
        setReportProgress([]);
        setReportData(null);

        try {
            const token = session.access_token;
            const url = `http://localhost:8001/v1/reports/${ticker.toUpperCase()}${force ? '?force=true' : ''}`;
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!res.ok) {
                setReportProgress(prev => [...prev, `❌ Error: ${res.statusText}`]);
                setReportLoading(false);
                return;
            }

            const reader = res.body?.getReader();
            if (!reader) { setReportLoading(false); return; }

            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() ?? '';

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const event = JSON.parse(line) as { type: string; content: string | ReportData };
                        if (event.type === 'status') {
                            setReportProgress(prev => [...prev, event.content as string]);
                        } else if (event.type === 'report') {
                            setReportData(event.content as ReportData);
                            setReportLoading(false);
                        } else if (event.type === 'error') {
                            setReportProgress(prev => [...prev, `❌ ${event.content as string}`]);
                            setReportLoading(false);
                        }
                    } catch {
                        // Skip malformed lines
                    }
                }
            }
        } catch (e) {
            console.error('Report generation failed:', e);
            setReportProgress(prev => [...prev, `❌ Network error: ${String(e)}`]);
            setReportLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center text-slate-400 gap-2">
                <div className="w-4 h-4 rounded-full border-2 border-primary border-t-transparent animate-spin" />
                Loading intelligence...
            </div>
        );
    }

    if (!stockData) return <div className="p-8 text-center text-slate-500">Asset data unavailable</div>;

    // --- DYNAMIC CALCULATIONS ---
    const activePrice = hoverData?.value ?? stockData.currentPrice;
    const currentVal = quantity * activePrice;
    const costBasis = quantity * avgPrice;
    const totalReturn = currentVal - costBasis;
    const returnPercent = costBasis !== 0 ? (totalReturn / costBasis) * 100 : 0;
    const isPositive = totalReturn >= 0;

    const weightPercent = totalPortfolioValue > 0 ? (costBasis / totalPortfolioValue) * 100 : 0;
    const isConcentrated = weightPercent > 20;

    const dividendYield = stockData.metrics?.dividendYield ?? 0;
    const estAnnualIncome = currentVal * (dividendYield / 100);
    const hasDividends = estAnnualIncome > 0;

    const daysHeld = buyDate
        ? Math.floor((new Date().getTime() - new Date(buyDate).getTime()) / (1000 * 60 * 60 * 24))
        : 0;

    const todaysReturn = stockData.change * quantity;
    const isTodayPositive = todaysReturn >= 0;

    const reportSections = [
        { title: '📈 Market Analysis', content: reportData?.market_report, borderColor: 'border-blue-500/20', bgColor: 'bg-blue-500/5' },
        { title: '📰 News Analysis', content: reportData?.news_report, borderColor: 'border-emerald-500/20', bgColor: 'bg-emerald-500/5' },
        { title: '📊 Fundamentals', content: reportData?.fundamentals_report, borderColor: 'border-purple-500/20', bgColor: 'bg-purple-500/5' },
        { title: '💬 Social Sentiment', content: reportData?.sentiment_report, borderColor: 'border-amber-500/20', bgColor: 'bg-amber-500/5' },
    ];

    return (
        <div className="w-full flex flex-col bg-[#0f172a] text-white">
            {/* Header */}
            <div className="flex justify-between items-start px-6 pt-6 pb-2">
                <div>
                    <div className="flex items-center gap-2">
                        <h1 className="text-3xl font-bold tracking-tight text-white">{ticker}</h1>
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-white/5 border border-white/10 text-slate-400">NASDAQ</span>
                    </div>
                    <p className="text-base text-slate-400 font-light">{stockData.name ?? ticker}</p>
                </div>
                <div className="text-right">
                    <div className="text-4xl font-mono font-bold tracking-tight">${activePrice.toFixed(2)}</div>
                    <div className={`text-lg font-medium flex items-center justify-end gap-2 ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                        <span>{isPositive ? '+' : ''}${totalReturn.toLocaleString(undefined, { maximumFractionDigits: 0 })} ({returnPercent.toFixed(2)}%)</span>
                    </div>
                    {hoverData && <div className="text-xs text-slate-500 font-mono mt-1">At: {hoverData.label}</div>}
                </div>
            </div>

            {/* Smart Alert */}
            {isConcentrated && (
                <div className="mx-6 mt-2 mb-2 px-3 py-2 bg-amber-500/10 border border-amber-500/20 rounded flex items-center gap-2 text-amber-200 text-sm">
                    <AlertTriangle className="w-4 h-4 text-amber-500" />
                    <span className="font-medium">Concentration Risk:</span>
                    <span className="text-amber-200/80">{weightPercent.toFixed(1)}% of portfolio.</span>
                </div>
            )}

            {/* Chart */}
            <div className="relative w-full h-[350px] border-y border-white/5 bg-gradient-to-b from-white/[0.02] to-transparent mb-4">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                        data={stockData.candles}
                        margin={{ top: 10, right: 0, left: 0, bottom: 0 }}
                        onMouseMove={(e) => {
                            if (e.activePayload?.[0]) {
                                const payload = (e.activePayload[0] as { payload: { value: number; time: string } }).payload;
                                setHoverData({ value: payload.value, label: payload.time });
                            }
                        }}
                        onMouseLeave={() => { setHoverData(null); }}
                    >
                        <defs>
                            <linearGradient id={`gradientColor-${ticker}`} x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor={isPositive ? '#10b981' : '#f43f5e'} stopOpacity={0.2} />
                                <stop offset="95%" stopColor={isPositive ? '#10b981' : '#f43f5e'} stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <Tooltip
                            content={<></>}
                            cursor={{ stroke: '#94a3b8', strokeWidth: 1, strokeDasharray: '4 4' }}
                        />
                        <ReferenceLine y={avgPrice} stroke="#94a3b8" strokeDasharray="3 3" opacity={0.3} />
                        <Area
                            type="monotone"
                            dataKey="value"
                            stroke={isPositive ? '#10b981' : '#f43f5e'}
                            strokeWidth={2}
                            fill={`url(#gradientColor-${ticker})`}
                            isAnimationActive={false}
                        />
                        <YAxis hide={true} domain={['dataMin - 2', 'dataMax + 2']} />
                    </AreaChart>
                </ResponsiveContainer>

                {!hoverData && (
                    <div className="absolute left-4 top-1/2 -translate-y-1/2 flex items-center pointer-events-none">
                        <span className="bg-[#0f172a]/80 backdrop-blur border border-white/10 text-slate-400 text-[10px] px-1.5 py-0.5 rounded">Avg: ${avgPrice.toFixed(2)}</span>
                    </div>
                )}
            </div>

            {/* Metrics Grid */}
            <div className="px-6 pb-6 grid grid-cols-2 md:grid-cols-4 gap-6">
                <div>
                    <div className="flex items-center gap-1.5 text-slate-500 text-[10px] uppercase tracking-wider mb-1">
                        <Target className="w-3 h-3" /> Cost Basis
                    </div>
                    <div className="text-xl font-light text-white">${costBasis.toLocaleString()}</div>
                    <div className="text-xs text-slate-600">{quantity} shares</div>
                </div>

                <div>
                    <div className="flex items-center gap-1.5 text-slate-500 text-[10px] uppercase tracking-wider mb-1">
                        <DollarSign className="w-3 h-3" /> Market Value
                    </div>
                    <div className="text-xl font-light text-white">${currentVal.toLocaleString()}</div>
                    {!hoverData && (
                        <div className={`text-xs ${isTodayPositive ? 'text-emerald-500' : 'text-rose-500'}`}>
                            {isTodayPositive ? '+' : ''}${todaysReturn.toFixed(0)} Today
                        </div>
                    )}
                </div>

                <div>
                    <div className="flex items-center gap-1.5 text-slate-500 text-[10px] uppercase tracking-wider mb-1">
                        <PieChart className="w-3 h-3" /> Weight
                    </div>
                    <div className="text-xl font-light text-white">{weightPercent.toFixed(1)}%</div>
                    <div className="text-xs text-slate-600">{weightPercent > 15 ? 'Heavy' : 'Balanced'}</div>
                </div>

                <div>
                    {hasDividends ? (
                        <div>
                            <div className="flex items-center gap-1.5 text-slate-500 text-[10px] uppercase tracking-wider mb-1">
                                <Zap className="w-3 h-3 text-amber-400" /> Est. Income
                            </div>
                            <div className="text-xl font-light text-amber-100">${estAnnualIncome.toFixed(0)}</div>
                            <div className="text-xs text-amber-500/60">{dividendYield.toFixed(2)}% Yield</div>
                        </div>
                    ) : (
                        <div>
                            <div className="flex items-center gap-1.5 text-slate-500 text-[10px] uppercase tracking-wider mb-1">
                                <Calendar className="w-3 h-3" /> Days Held
                            </div>
                            <div className="text-xl font-light text-white">{daysHeld}</div>
                            <div className="text-xs text-slate-600">Long-term</div>
                        </div>
                    )}
                </div>
            </div>

            {/* ── AI Report Section ── */}
            <div className="px-6 pb-8">
                <div className="border-t border-white/5 mb-5" />

                {/* Generate / View Button */}
                {!reportVisible && !reportLoading && (
                    <button
                        type="button"
                        onClick={() => {
                            if (reportData) {
                                setReportVisible(true);
                            } else {
                                setReportVisible(true);
                                void handleGenerateReport();
                            }
                        }}
                        className="w-full py-3.5 rounded-xl bg-gradient-to-r from-blue-600/20 to-purple-600/20 border border-blue-500/20 hover:border-blue-500/40 hover:from-blue-600/30 hover:to-purple-600/30 transition-all duration-300 flex items-center justify-center gap-3 group"
                    >
                        <FileBarChart className="w-5 h-5 text-blue-400 group-hover:scale-110 transition-transform" />
                        <span className="text-white font-medium">{reportData ? 'View AI Report' : 'Generate AI Report'}</span>
                        {!reportData && <span className="text-slate-500 text-xs">4 analysts</span>}
                        {reportData && <span className="text-emerald-500 text-xs">● cached</span>}
                    </button>
                )}

                {/* Progress */}
                <AnimatePresence>
                    {reportLoading && (
                        <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            className="overflow-hidden"
                        >
                            <div className="bg-white/5 rounded-xl border border-white/10 p-4 space-y-2">
                                {reportProgress.map((step, i) => (
                                    <motion.div
                                        key={i}
                                        initial={{ opacity: 0, x: -8 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        className="flex items-center gap-2 text-sm text-slate-300"
                                    >
                                        <span>{step}</span>
                                    </motion.div>
                                ))}
                                <div className="flex items-center gap-2 text-sm text-blue-400 pt-1">
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    <span>Processing...</span>
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Report Sections */}
                <AnimatePresence>
                    {reportData && reportVisible && (
                        <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="space-y-4"
                        >
                            <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-2">
                                    <FileBarChart className="w-4 h-4 text-blue-400" />
                                    <span className="text-sm font-medium text-white">AI Analyst Report</span>
                                    <span className="text-[10px] text-slate-500 font-mono">{reportData.report_date}</span>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => { setReportVisible(false); void handleGenerateReport(true); }}
                                    className="text-xs text-slate-500 hover:text-blue-400 transition-colors"
                                >
                                    ↻ Regenerate
                                </button>
                            </div>

                            {reportSections.map((section, i) => (
                                section.content ? (
                                    <motion.div
                                        key={section.title}
                                        initial={{ opacity: 0, y: 8 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: i * 0.08 }}
                                        className={`rounded-xl border ${section.borderColor} overflow-hidden`}
                                    >
                                        <div className={`px-4 py-2.5 border-b ${section.borderColor} ${section.bgColor}`}>
                                            <h3 className="text-white font-semibold text-xs tracking-wide">{section.title}</h3>
                                        </div>
                                        <div className="px-4 py-3 text-slate-300 text-sm leading-relaxed bg-white/[0.02] prose prose-invert prose-sm max-w-none prose-headings:text-white prose-strong:text-white prose-th:text-slate-300 prose-td:text-slate-400 prose-li:text-slate-300 prose-p:text-slate-300 prose-table:border-white/10 prose-th:border-white/10 prose-td:border-white/10 prose-hr:border-white/10">
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{section.content}</ReactMarkdown>
                                        </div>
                                    </motion.div>
                                ) : null
                            ))}
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            {/* Texture Overlay */}
            <div className="absolute inset-0 pointer-events-none opacity-[0.03]" style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")` }}></div>
        </div>
    );
};

export default PersonalizedAssetView;
