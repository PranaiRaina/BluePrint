import React, { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface LiveMessageProps {
    contentRef: React.MutableRefObject<string>;
    isStreaming: boolean;
}

/**
 * A component that pulls data from a Ref to update itself independently of the parent.
 * This prevents the massive ChatView from re-rendering on every character.
 */
const LiveMessage: React.FC<LiveMessageProps> = ({ contentRef, isStreaming }) => {
    const [displayedContent, setDisplayedContent] = useState('');
    const currentLengthRef = React.useRef(0);

    useEffect(() => {
        let animationFrameId: number;

        const update = () => {
            const fullContent = contentRef.current;

            // Check based on REF, not state (which is stale in closure)
            if (currentLengthRef.current < fullContent.length) {
                // Calculate chunk size based on lag to stay responsive but smooth
                const lag = fullContent.length - currentLengthRef.current;
                const chunkSize = lag > 50 ? 5 : (lag > 20 ? 3 : 1);

                const nextChunk = fullContent.slice(currentLengthRef.current, currentLengthRef.current + chunkSize);

                setDisplayedContent(prev => prev + nextChunk);
                currentLengthRef.current += nextChunk.length;
            }

            if (isStreaming || currentLengthRef.current < contentRef.current.length) {
                animationFrameId = requestAnimationFrame(update);
            }
        };

        animationFrameId = requestAnimationFrame(update);

        return () => {
            cancelAnimationFrame(animationFrameId);
        };
    }, [isStreaming, contentRef]);

    return (
        <div className="prose prose-invert max-w-none prose-p:leading-relaxed prose-code:text-primary/90 prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline hover:prose-a:text-blue-300">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {displayedContent}
            </ReactMarkdown>

        </div>
    );
};

export default LiveMessage;
