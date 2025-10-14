from agents import Runner, trace, gen_trace_id
from school_domain_agent import MultipleSchoolsAndDomains, search_agent
import asyncio

class SchorlashipManager:
    async def run(self, query: str):
        """ Run the deep research process, yielding the status updates and the final report"""
        trace_id = gen_trace_id()
        with trace("Research trace", trace_id=trace_id):
            print(f"View trace: https://platform.openai.com/traces/trace?trace_id={trace_id}")
            yield f"View trace: https://platform.openai.com/traces/trace?trace_id={trace_id}"
            print("Starting research...")
            await asyncio.sleep(1)
            search_plan = await self.find__school_domain(query)
            yield f"✅ Planned {search_plan.schools} searches. Starting..." 
            yield f"🎓 Report ready for query: {query}"
            yield f"result {search_plan}"
        

    async def find__school_domain(self, query: str) -> MultipleSchoolsAndDomains:
        print("Planning searches...")
        result = await Runner.run(search_agent, f"Query: {query}")
        print(f"Will perform {result.final_output} searches")
        return result.final_output_as(MultipleSchoolsAndDomains)


