import type { Session } from '@supabase/supabase-js';

const API_Base = 'http://localhost:8001';

export interface AgentResponse {
    final_output: string;
    status: string;
}

export const agentService = {
    /**
     * Send a query to the Manager Agent.
     * @param query The user's natural language query.
     * @param session Supabase session for authentication token.
     * @param sessionId Optional session ID for conversation history.
     */
    calculate: async (query: string, session: Session | null, sessionId: string = 'default'): Promise<AgentResponse> => {
        try {
            const token = session?.access_token;

            const headers: HeadersInit = {
                'Content-Type': 'application/json',
            };

            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`${API_Base}/v1/agent/calculate`, {
                method: 'POST',
                headers,
                body: JSON.stringify({
                    query,
                    session_id: sessionId
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `API Error: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error("Agent API Error:", error);
            throw error;
        }
    },

    /**
     * Stream a chat query to the Manager Agent (SSE).
     */
    streamChat: async (
        query: string,
        session: Session | null,
        sessionId: string = 'default',
        callbacks: {
            onStatus: (status: string) => void;
            onToken: (token: string) => void;
            onComplete: () => void;
            onError: (error: string) => void;
        }
    ): Promise<void> => {
        try {
            const token = session?.access_token;
            const headers: HeadersInit = {
                'Content-Type': 'application/json',
            };
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`${API_Base}/v1/agent/chat/stream`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ query, session_id: sessionId })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `API Error: ${response.statusText}`);
            }

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();

            if (!reader) throw new Error("No reader available");

            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');

                // Keep the last line in the buffer if it's incomplete
                // If the chunk ended with \n, the last line will be empty, which is fine
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.trim() === '') continue;

                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));

                            if (data.type === 'token') {
                                callbacks.onToken(data.content);
                            } else if (data.type === 'status') {
                                callbacks.onStatus(data.content);
                            } else if (data.type === 'error') {
                                callbacks.onError(data.content);
                            } else if (data.type === 'end') {
                                // Stream finished gracefully
                            }
                        } catch (e) {
                            console.error("Error parsing SSE chunk", e);
                        }
                    }
                }
            }
            callbacks.onComplete();

        } catch (error) {
            console.error("Stream Error:", error);
            callbacks.onError(error instanceof Error ? error.message : String(error));
        }
    },

    /**
     * Upload a document for RAG ingestion.
     */
    upload: async (file: File, session: Session | null): Promise<any> => {
        try {
            const token = session?.access_token;
            const formData = new FormData();
            formData.append('file', file);

            const headers: HeadersInit = {};
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`${API_Base}/v1/agent/upload`, {
                method: 'POST',
                headers, // Do NOT set Content-Type for FormData, browser does it automatically with boundary
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Upload Error: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error("Upload API Error:", error);
            throw error;
        }
    },

    /**
     * Get list of uploaded documents.
     */
    getDocuments: async (session: Session | null): Promise<string[]> => {
        try {
            const token = session?.access_token;
            const headers: HeadersInit = {};
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`${API_Base}/v1/agent/documents`, {
                method: 'GET',
                headers
            });

            if (!response.ok) {
                return [];
            }

            const data = await response.json();
            return data.documents || [];
        } catch (error) {
            console.error("Fetch Documents Error:", error);
            return [];
        }
    },

    /**
     * Get real-time stock data for charting.
     * @param ticker Stock ticker symbol (e.g., "NVDA").
     * @param session Supabase session for authentication token.
     */
    getStockData: async (ticker: string, session: Session | null, timeRange: string = "3m"): Promise<any> => {
        try {
            const token = session?.access_token;
            const headers: HeadersInit = {};
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`${API_Base}/v1/agent/stock/${ticker.toUpperCase()}?time_range=${timeRange}`, {
                method: 'GET',
                headers
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `Stock API Error: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error("Stock API Error:", error);
            throw error;
        }
    },

    /**
     * Get chat history for the current session.
     */
    getHistory: async (sessionId: string, session: Session | null): Promise<any[]> => {
        try {
            const token = session?.access_token;
            const headers: HeadersInit = {};
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`${API_Base}/v1/agent/history?session_id=${sessionId}`, {
                method: 'GET',
                headers
            });

            if (!response.ok) {
                return [];
            }

            return await response.json();
        } catch (error) {
            console.error("Fetch History Error:", error);
            return [];
        }
    },

    /**
     * Delete a document.
     */
    deleteDocument: async (filename: string, session: Session | null): Promise<boolean> => {
        try {
            const token = session?.access_token;
            const headers: HeadersInit = {};
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`${API_Base}/v1/agent/documents/${filename}`, {
                method: 'DELETE',
                headers
            });

            if (!response.ok) {
                return false;
            }

            return true;
        } catch (error) {
            console.error("Delete Document Error:", error);
            return false;
        }
    },
    /**
     * Get list of chat sessions.
     */
    getSessions: async (session: Session | null): Promise<any[]> => {
        try {
            const token = session?.access_token;
            const headers: HeadersInit = {};
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`${API_Base}/v1/agent/sessions`, {
                method: 'GET',
                headers
            });

            if (!response.ok) {
                return [];
            }

            const data = await response.json();
            return data.sessions || [];
        } catch (error) {
            console.error("Fetch Sessions Error:", error);
            return [];
        }
    },

    /**
     * Create a new session.
     */
    createSession: async (title: string, session: Session | null): Promise<any> => {
        try {
            const token = session?.access_token;
            const headers: HeadersInit = {
                'Content-Type': 'application/json',
            };
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`${API_Base}/v1/agent/sessions`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ title })
            });

            if (!response.ok) {
                throw new Error("Failed to create session");
            }

            return await response.json();
        } catch (error) {
            console.error("Create Session Error:", error);
            return null;
        }
    },

    /**
     * Rename a session.
     */
    renameSession: async (sessionId: string, title: string, session: Session | null): Promise<boolean> => {
        try {
            const token = session?.access_token;
            const headers: HeadersInit = {
                'Content-Type': 'application/json',
            };
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`${API_Base}/v1/agent/sessions/${sessionId}`, {
                method: 'PATCH',
                headers,
                body: JSON.stringify({ title })
            });

            return response.ok;
        } catch (error) {
            console.error("Rename Session Error:", error);
            return false;
        }
    },

    /**
     * Delete a session.
     */
    deleteSession: async (sessionId: string, session: Session | null): Promise<boolean> => {
        try {
            const token = session?.access_token;
            const headers: HeadersInit = {};
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`${API_Base}/v1/agent/sessions/${sessionId}`, {
                method: 'DELETE',
                headers
            });

            return response.ok;
        } catch (error) {
            console.error("Delete Session Error:", error);
            return false;
        }
    }
};
