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
    }
};
