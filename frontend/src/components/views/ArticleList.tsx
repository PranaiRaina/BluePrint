import React, { useEffect, useState } from 'react';
import { AlertTriangle, TrendingUp, TrendingDown, Zap, Info } from 'lucide-react';
import type { Session } from '@supabase/supabase-js';

interface Article {
    title: string;
    link: string;
    sentiment: 'Positive' | 'Negative' | 'Neutral';
    score?: number;
}

interface ArticlesData {
    ticker: string;
    overall_sentiment: 'Bullish' | 'Bearish' | 'Neutral' | 'Unknown';
    articles: Article[];
    counts: {
        Positive: number;
        Negative: number;
        Neutral: number;
    };
    error?: string;
}

interface AnalystData {
    ticker: string;
    recommendation: 'Strong Buy' | 'Buy' | 'Hold' | 'Sell' | 'Strong Sell';
    consensusScore: number;
    totalAnalysts: number;
    buy?: number;
    strongBuy?: number;
    hold?: number;
    sell?: number;
    strongSell?: number;
    error?: string;
}

interface ArticleListProps {
    session: Session | null;
    ticker: string;
}

// Signal divergence detection
type DivergenceType = 'value_opportunity' | 'caution_hype' | 'aligned_bullish' | 'aligned_bearish' | 'neutral' | null;

interface DivergenceInfo {
    type: DivergenceType;
    title: string;
    message: string;
    icon: React.ReactNode;
    colorClass: string;
}

const getDivergenceInfo = (
    analystRec: string | undefined,
    newsSentiment: string
): DivergenceInfo | null => {
    if (!analystRec) return null;

    // Normalize to handle API casing (API returns "STRONG BUY", frontend logic was "Strong Buy")
    const rec = analystRec.toUpperCase();

    // Check for Bullish ratings (Strong Buy, Buy)
    const analystBullish = ['STRONG BUY', 'BUY'].includes(rec);

    // Check for Bearish ratings (Sell, Strong Sell)
    const analystBearish = ['SELL', 'STRONG SELL'].includes(rec);

    const newsBullish = newsSentiment === 'Bullish';
    const newsBearish = newsSentiment === 'Bearish';

    // Bullish analyst + Bearish news = Potential Value
    if (analystBullish && newsBearish) {
        return {
            type: 'value_opportunity',
            title: 'Signal Divergence Detected',
            message: 'Analysts are bullish despite negative news. This could indicate a potential value opportunity if fundamentals remain strong.',
            icon: <Zap className="w-5 h-5" />,
            colorClass: 'border-amber-500/50 bg-amber-500/10 text-amber-400'
        };
    }

    // Bearish analyst + Bullish news = Caution
    if (analystBearish && newsBullish) {
        return {
            type: 'caution_hype',
            title: 'Signal Divergence Detected',
            message: 'News sentiment is positive but analysts are bearish. Exercise caution — could be hype over fundamentals.',
            icon: <AlertTriangle className="w-5 h-5" />,
            colorClass: 'border-orange-500/50 bg-orange-500/10 text-orange-400'
        };
    }

    // Aligned bullish
    if (analystBullish && newsBullish) {
        return {
            type: 'aligned_bullish',
            title: 'Strong Conviction Signal',
            message: 'Both analysts and news sentiment align bullish. Strong momentum signal.',
            icon: <TrendingUp className="w-5 h-5" />,
            colorClass: 'border-green-500/50 bg-green-500/10 text-green-400'
        };
    }

    // Aligned bearish
    if (analystBearish && newsBearish) {
        return {
            type: 'aligned_bearish',
            title: 'Strong Avoid Signal',
            message: 'Both analysts and news sentiment align bearish. Consider avoiding or reviewing position.',
            icon: <TrendingDown className="w-5 h-5" />,
            colorClass: 'border-red-500/50 bg-red-500/10 text-red-400'
        };
    }

    return null;
};

const ArticleList: React.FC<ArticleListProps> = ({ session, ticker }) => {
    const [data, setData] = useState<ArticlesData | null>(null);
    const [analystData, setAnalystData] = useState<AnalystData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!ticker || !session) return;

        const fetchData = async () => {
            setLoading(true);
            setError(null);

            try {
                // Fetch articles and analyst data in parallel
                const [articlesRes, analystRes] = await Promise.all([
                    fetch(`http://localhost:8001/v1/agent/articles/${ticker}`, {
                        headers: { Authorization: `Bearer ${session.access_token}` },
                    }),
                    fetch(`http://localhost:8001/v1/agent/analyst/${ticker}`, {
                        headers: { Authorization: `Bearer ${session.access_token}` },
                    })
                ]);

                if (!articlesRes.ok) {
                    throw new Error(`Failed to fetch articles: ${articlesRes.status}`);
                }

                const articlesResult = await articlesRes.json();
                setData(articlesResult);

                if (analystRes.ok) {
                    const analystResult = await analystRes.json();
                    if (!analystResult.error) {
                        setAnalystData(analystResult);
                    }
                }
            } catch (err: any) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [ticker, session]);

    const getSentimentColor = (sentiment: string) => {
        switch (sentiment) {
            case 'Positive':
                return 'bg-green-500/20 text-green-400 border-green-500/30';
            case 'Negative':
                return 'bg-red-500/20 text-red-400 border-red-500/30';
            default:
                return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
        }
    };

    const getOverallColor = (overall: string) => {
        switch (overall) {
            case 'Bullish':
                return 'text-green-400';
            case 'Bearish':
                return 'text-red-400';
            default:
                return 'text-gray-400';
        }
    };

    const getAnalystColor = (rec: string) => {
        const r = rec?.toUpperCase() || '';
        switch (r) {
            case 'STRONG BUY':
            case 'BUY':
                return 'text-green-400';
            case 'SELL':
            case 'STRONG SELL':
                return 'text-red-400';
            default:
                return 'text-yellow-400';
        }
    };

    if (loading) {
        return (
            <div className="mt-6 glass-card p-6">
                <div className="flex items-center justify-center">
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white"></div>
                    <span className="ml-3 text-text-secondary">Loading articles...</span>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="mt-6 glass-card p-6">
                <div className="text-red-400 text-center">{error}</div>
            </div>
        );
    }

    if (!data || data.articles.length === 0) {
        return (
            <div className="mt-6 glass-card p-6">
                <div className="text-text-secondary text-center">No articles found for {ticker}</div>
            </div>
        );
    }

    const divergence = getDivergenceInfo(analystData?.recommendation, data.overall_sentiment);

    return (
        <div className="mt-6">
            {/* Signal Divergence Alert */}
            {divergence && (
                <div className={`mb-4 p-4 rounded-xl border ${divergence.colorClass} transition-all animate-fadeIn`}>
                    <div className="flex items-start gap-3">
                        <div className="flex-shrink-0 mt-0.5">
                            {divergence.icon}
                        </div>
                        <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                                <h4 className="font-semibold">{divergence.title}</h4>
                            </div>
                            <div className="flex items-center gap-4 text-sm mb-2">
                                <span>
                                    Expert: <span className={`font-bold ${getAnalystColor(analystData?.recommendation || '')}`}>
                                        {analystData?.recommendation}
                                    </span>
                                </span>
                                <span className="text-white/30">|</span>
                                <span>
                                    News: <span className={`font-bold ${getOverallColor(data.overall_sentiment)}`}>
                                        {data.overall_sentiment}
                                    </span>
                                </span>
                            </div>
                            <p className="text-sm opacity-80">{divergence.message}</p>
                        </div>
                    </div>
                </div>
            )}

            {/* Header with overall sentiment */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <h3 className="text-lg font-semibold text-white">News Sentiment ({ticker})</h3>
                    {analystData && !analystData.error && (
                        <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/5 text-xs text-text-secondary">
                            <Info className="w-3 h-3" />
                            <span>Expert: </span>
                            <span className={`font-semibold ${getAnalystColor(analystData.recommendation)}`}>
                                {analystData.recommendation}
                            </span>
                            <span className="text-white/30 mx-1">·</span>
                            <span>{analystData.totalAnalysts} analysts</span>
                        </div>
                    )}
                </div>
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 text-sm">
                        <span className="text-green-400">● {data.counts.Positive}</span>
                        <span className="text-gray-400">● {data.counts.Neutral}</span>
                        <span className="text-red-400">● {data.counts.Negative}</span>
                    </div>
                    <span className={`font-bold ${getOverallColor(data.overall_sentiment)}`}>
                        {data.overall_sentiment}
                    </span>
                </div>
            </div>

            {/* Articles list */}
            <div className="glass-card divide-y divide-white/10 max-h-80 overflow-y-auto">
                {data.articles.map((article, index) => (
                    <a
                        key={index}
                        href={article.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block p-4 hover:bg-white/5 transition-colors"
                    >
                        <div className="flex items-start gap-3">
                            <span
                                className={`px-2 py-0.5 text-xs font-medium rounded border ${getSentimentColor(
                                    article.sentiment
                                )}`}
                            >
                                {article.sentiment}
                            </span>
                            <p className="text-sm text-white leading-relaxed flex-1">{article.title}</p>
                        </div>
                    </a>
                ))}
            </div>
        </div>
    );
};

export default ArticleList;
