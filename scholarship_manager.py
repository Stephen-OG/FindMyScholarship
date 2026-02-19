# import asyncio

# from agents import Runner, gen_trace_id, trace

# from scholarship_agents.crawler_agent import UniversityResult, crawler_agent

# # from .agents.crawler_agent import CrawlerResult, crawler_agent
# from scholarship_agents.school_domain_agent import MultipleSchoolsAndDomains, search_agent


# class ScholarshipManager:
#     async def run(self, query: str):
#         """Run the deep research process, yielding the status updates and the final report"""
#         trace_id = gen_trace_id()
#         with trace("Research trace", trace_id=trace_id):
#             print(f"View trace: https://platform.openai.com/traces/trace?trace_id={trace_id}")
#             yield f"View trace: https://platform.openai.com/traces/trace?trace_id={trace_id}"
#             print("Starting research...")
#             await asyncio.sleep(1)
#             search_plan = await self.find__school_domain(query)
#             yield f"✅ School/s search results: {search_plan.schools}"
#             print(f"✅ School/s search results: {search_plan.schools}")

#             # print("Crawling...")
#             # await asyncio.sleep(1)
#             # crawler = await self.domain_crawler(search_plan)
#             # yield f"✅ School/s domain crawler results: {crawler}"

#             print("Crawling...")
#             await asyncio.sleep(1)
#             crawler = await self.domain_crawler(search_plan)
#             yield f"✅ School/s domain crawler results: {crawler}"
#             print(f"✅ School/s domain crawler results: {crawler}")

#     async def find__school_domain(self, query: str) -> MultipleSchoolsAndDomains:
#         print("Planning searches...")
#         result = await Runner.run(search_agent, f"Query: {query}")
#         # print(f"Will perform {result.final_output} searches")
#         return result.final_output_as(MultipleSchoolsAndDomains)

#     # async def domain_crawler(self, search_data: MultipleSchoolsAndDomains) -> CrawlerResult:
#     #     print("Start crawling...")
#     #     result = await Runner.run(crawler_agent, f"Schools and Domains: {search_data}")
#     #     #print(f"Will perform {result.final_output} searches")
#     #     return result.final_output_as(CrawlerResult)

#     async def domain_crawler(
#         self, search_data: MultipleSchoolsAndDomains
#     ) -> UniversityResult:
#         print("Start crawling...")
#         result = await Runner.run(crawler_agent, f"Schools and Domains: {search_data}")
#         # print(f"Will perform {result.final_output} searches")
#         return result.final_output_as(UniversityResult)
