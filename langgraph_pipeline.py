
from typing import Dict, List, Any
from langgraph.graph import Graph
from langchain_community.chat_models import ChatOpenAI
from langchain_core.documents import Document
import base_config as bc
import advanced_config as ac
from datetime import datetime

import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('DiscordDigest')

class MessageProcessor:
    def preprocess(self, messages: List[Dict]) -> List[Document]:
        """Preprocess messages into documents."""
        logger.debug(f"Starting preprocessing of {len(messages)} messages")
        docs = []
        for msg in messages:
            if len(msg['content']) >= ac.PREPROCESSING_CONFIG['min_message_length']:
                if msg['author'] not in ac.PREPROCESSING_CONFIG['excluded_authors']:
                    docs.append(Document(
                        page_content=msg['content'],
                        metadata={
                            'author': msg['author'],
                            'channel_id': msg['channel_id'],
                            'timestamp': msg['timestamp']
                        }
                    ))
        return docs

    def analyze(self, docs: List[Document]) -> Dict[str, List[Document]]:
        """Group documents by channel and analyze patterns."""
        logger.debug(f"Starting analysis of {len(docs)} documents")
        channel_docs = {}
        for doc in docs:
            channel_id = doc.metadata['channel_id']
            if channel_id not in channel_docs:
                channel_docs[channel_id] = []
            channel_docs[channel_id].append(doc)
        return channel_docs

    def summarize(self, channel_docs: Dict[str, List[Document]]) -> Dict[str, str]:
        """Generate summaries for each channel."""
        logger.debug(f"Starting summarization for {len(channel_docs)} channels")
        llm = ChatOpenAI(
            temperature=bc.OPENAI_CONFIG['TEMPERATURE'],
            model=bc.OPENAI_CONFIG['MODEL']
        )
        summaries = {}
        
        for channel_id, docs in channel_docs.items():
            messages = "\n".join([f"{doc.metadata['author']}: {doc.page_content}" 
                                for doc in docs])
            
            response = llm.predict(
                ac.SUMMARY_TEMPLATES['channel'].format(
                    channel_id=channel_id,
                    messages=messages
                )
            )
            summaries[channel_id] = response
            
        return summaries

    def format_digest(self, summaries: Dict[str, str]) -> str:
        """Format the final digest."""
        now = datetime.now()
        digest = f"Discord Digest - {now.strftime('%Y-%m-%d')}\n\n"
        
        for channel_id, summary in summaries.items():
            digest += f"Channel {channel_id}:\n"
            digest += f"{summary}\n\n"
            
        return digest

def create_pipeline() -> Graph:
    """Create the LangGraph pipeline."""
    processor = MessageProcessor()
    
    # Define the graph
    graph = Graph()
    
    # Add nodes
    graph.add_node("preprocessor", processor.preprocess)
    graph.add_node("analyzer", processor.analyze)
    graph.add_node("summarizer", processor.summarize)
    graph.add_node("formatter", processor.format_digest)
    
    # Connect nodes
    graph.add_edge("preprocessor", "analyzer")
    graph.add_edge("analyzer", "summarizer")
    graph.add_edge("summarizer", "formatter")
    
    return graph
