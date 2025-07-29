"""
Agents for slides evaluation and presentation analysis on 14+ criteria
"""

from langchain_community.tools.tavily_search import TavilySearchResults
from slideguard.utils.file_manager import FileManager
from slideguard.utils.cache_manager import CacheManager

from textwrap import dedent
from crewai import Agent

class SlideGuardAgents():
    def __init__(self,
                 file_manager: FileManager,
                 cache_manager):
        self.tools = None


    def slide_evaluation_agent(self, 
                               role: str,
                               criteria):
        return 
        return Agent