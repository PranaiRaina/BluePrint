import React from 'react';
import { motion } from 'framer-motion';
import { Upload, FileText, CheckCircle } from 'lucide-react';

const UploadZone: React.FC = () => {
    return (
        <div className="w-full max-w-4xl mx-auto pt-10">
            <h1 className="text-3xl font-bold text-white mb-2">Data Vault</h1>
            <p className="text-text-secondary mb-8">Securely upload financial documents for generic analysis.</p>

            <div className="glass-card p-12 border-2 border-dashed border-white/10 rounded-3xl flex flex-col items-center justify-center text-center hover:border-primary/50 transition-colors cursor-pointer group">
                <div className="w-20 h-20 rounded-full bg-white/5 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                    <Upload className="w-10 h-10 text-primary group-hover:text-white transition-colors" />
                </div>
                <h3 className="text-xl text-white font-medium mb-2">Drag & Drop Files</h3>
                <p className="text-text-secondary text-sm max-w-md">
                    Upload PDF statements, Excel sheets, or CSV content.
                    <br />Protected by local encryption protocols.
                </p>
            </div>

            <div className="mt-8">
                <h4 className="text-white font-medium mb-4 flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-primary" />
                    Processed Documents
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {['Bob_Jones_Report.pdf', 'Q3_Market_Analysis.pdf', 'Tech_Sector_Trends_2024.pdf'].map((file, i) => (
                        <motion.div
                            key={i}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: i * 0.1 }}
                            className="glass-input p-4 flex items-center gap-3 hover:bg-white/10 transition-colors"
                        >
                            <FileText className="text-ai w-5 h-5" />
                            <span className="text-sm text-text-secondary">{file}</span>
                            <span className="ml-auto text-xs font-mono text-emerald-400">Indexed</span>
                        </motion.div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default UploadZone;
