import React, { useState, useRef } from 'react';
import { Upload, CheckCircle, FileText, Loader2, AlertCircle } from 'lucide-react';
import type { Session } from '@supabase/supabase-js';
import { agentService } from '../../services/agent';

interface UploadZoneProps {
    session: Session;
}

const UploadZone: React.FC<UploadZoneProps> = ({ session }) => {
    const [isDragging, setIsDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadedFiles, setUploadedFiles] = useState<string[]>([]);
    const [error, setError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Fetch documents on mount
    React.useEffect(() => {
        fetchDocuments();
    }, [session]);

    const fetchDocuments = async () => {
        const docs = await agentService.getDocuments(session);
        setUploadedFiles(docs);
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleUpload(files[0]);
        }
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            handleUpload(e.target.files[0]);
        }
    };

    const handleUpload = async (file: File) => {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            setError("Only PDF files are supported currently.");
            return;
        }

        setIsUploading(true);
        setError(null);

        try {
            await agentService.upload(file, session);
            // Refresh list from server to ensure it's actually there
            await fetchDocuments();
        } catch (err: any) {
            setError(err.message || "Upload failed");
        } finally {
            setIsUploading(false);
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        }
    };

    return (
        <div className="w-full max-w-4xl mx-auto pt-10">
            <h1 className="text-3xl font-bold text-white mb-2">Data Vault</h1>
            <p className="text-text-secondary mb-8">Securely upload financial documents for generic analysis.</p>

            <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`glass-card p-12 border-2 border-dashed rounded-3xl flex flex-col items-center justify-center text-center transition-all cursor-pointer group ${isDragging ? 'border-primary bg-primary/5' : 'border-white/10 hover:border-primary/50'
                    }`}
            >
                <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileSelect}
                    className="hidden"
                    accept=".pdf"
                />

                <div className={`w-20 h-20 rounded-full flex items-center justify-center mb-6 transition-transform ${isDragging ? 'scale-110 bg-primary/20' : 'bg-white/5 group-hover:scale-110'}`}>
                    {isUploading ? (
                        <Loader2 className="w-10 h-10 text-primary animate-spin" />
                    ) : (
                        <Upload className={`w-10 h-10 transition-colors ${isDragging ? 'text-primary' : 'text-primary group-hover:text-white'}`} />
                    )}
                </div>

                <h3 className="text-xl text-white font-medium mb-2">
                    {isUploading ? "Processing Document..." : "Drag & Drop Files"}
                </h3>
                <p className="text-text-secondary text-sm max-w-md">
                    {isUploading ? "Encryption and Vectorization in progress." : "Upload PDF statements. Protected by local encryption protocols."}
                </p>
                {error && (
                    <div className="mt-4 flex items-center gap-2 text-red-400 text-sm bg-red-500/10 px-4 py-2 rounded-lg">
                        <AlertCircle className="w-4 h-4" />
                        {error}
                    </div>
                )}
            </div>

            <div className="mt-8">
                <h4 className="text-white font-medium mb-4 flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-primary" />
                    Processed Documents
                </h4>
                {uploadedFiles.length === 0 ? (
                    <div className="text-white/50 text-sm italic">
                        No documents uploaded yet.
                    </div>
                ) : (
                    <div className="space-y-2">
                        {uploadedFiles.map((fname, i) => (
                            <div key={i} className="flex items-center gap-3 p-3 bg-white/5 rounded-lg border border-white/5">
                                <FileText className="w-5 h-5 text-ai" />
                                <span className="text-slate-200 text-sm">{fname}</span>
                                <span className="ml-auto text-xs text-primary bg-primary/10 px-2 py-1 rounded">Ready</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default UploadZone;
