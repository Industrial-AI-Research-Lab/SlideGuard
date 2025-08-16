import asyncio
import base64
import json
import os
from pprint import pprint


from dotenv import load_dotenv
from langfuse import get_client, Langfuse
from openinference.instrumentation.crewai import CrewAIInstrumentor
from openinference.instrumentation.litellm import LiteLLMInstrumentor

from slideguard.crew.evaluator import SlideGuardEvaluator
from crewai.tools import tool

from slideguard.criteria import DECK_CRITERIA_INFO, SLIDE_CRITERIA_INFO
from slideguard.schemes import Criteria


def encode_image_to_base64(image_path):
    """Convert local image to base64 string"""
    with open(image_path, "rb") as image_file:
        image_str =base64.b64encode(image_file.read()).decode('utf-8')
    
    return f"data:image/png;base64,{image_str}"


@tool("Add image to content")
def process_local_image(image_url: str) -> str:
    """Convert local image to base64 format for multimodal processing."""
    try:
        with open(image_url, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        return f"data:image/jpeg;base64,{base64_image}"
    except Exception as e:
        return f"Error: {str(e)}"
    

async def main():
    load_dotenv()

    for key, value in os.environ.items():
        print(f"{key}: {value}")

    if False:
        langfuse_client = None
    else:
        langfuse_client: Langfuse = get_client()

        if langfuse_client.auth_check():
            print("Langfuse client is authenticated and ready!")
        else:
            print("Authentication failed. Please check your credentials and host.")

        CrewAIInstrumentor().instrument(skip_dep_check=True)
        LiteLLMInstrumentor().instrument()

    # presentation_path = "resources/slidedecks/test_one_slide.pdf"
    presentation_path = "resources/slidedecks/30_EN_Matveeva_Thesis.pdf"

    evaluator = SlideGuardEvaluator()

    evaluation = await evaluator.evaluate_presentation(
        presentation_path=presentation_path,
        # slide_criterias=[Criteria.slide_visual_arrangement],
        # slide_criterias=[Criteria.slide_type, Criteria.slide_description, Criteria.slide_visual_arrangement],
        # deck_criterias=[Criteria.deck_storytelling],
        slide_criterias=list(SLIDE_CRITERIA_INFO.keys()),
        deck_criterias=list(DECK_CRITERIA_INFO.keys()),
        langfuse_client=langfuse_client
    )

    # pprint(evaluation.model_dump())

    with open("evaluation.json", "w") as f:
        # Use model_dump() with mode='json' to ensure proper serialization of nested BaseModel objects
        evaluation_dict = evaluation.model_dump(mode='json')
        f.write(json.dumps(evaluation_dict, indent=4))
    
    print("Evaluation saved to evaluation.json")

    # pprint(evaluation)

    # slide_deck_images = evaluator.agents.file_manager.process_presentation(presentation_path)

    # criterias = [
    #     Criteria.slide_type,
    #     Criteria.slide_description,
    #     Criteria.slide_visual_arrangement
    # ]

    # slide_type_agent = evaluator.agents.create_agent(Criteria.slide_type)
    # slide_description_agent = evaluator.agents.create_agent(Criteria.slide_description)
    # slide_visual_arrangement_agent = evaluator.agents.create_agent(Criteria.slide_visual_arrangement)

    # agents = [slide_type_agent, slide_description_agent, slide_visual_arrangement_agent]

    # async def func(task: Task, inputs: List[Dict[str, Any]]):
    #     crew = Crew(agents=agents, tasks=[task], verbose=True)
    #     results = await crew.kickoff_for_each_async(inputs)
    #     return results
    
    # tasks = [
    #     Task(
    #         name=Criteria.slide_type.value,
    #         description=dedent("""
    #             Analyze this slide image.                
    #             ```image {slide_image_path} ```
    #         """),
    #         agent=slide_type_agent,
    #         output_pydantic=SlideType,
    #         guardrail=evaluator.agents._make_pydantic_guardrail(SlideType),
    #         max_retries=3,
    #         expected_output="JSON in the described format."
    #     ),
    #     Task(
    #         name=Criteria.slide_description.value,
    #         description=dedent("""
    #             Analyze this slide image.                
    #             ```image {slide_image_path} ```
    #         """),
    #         agent=slide_description_agent,
    #         output_pydantic=SlideDescription,
    #         guardrail=evaluator.agents._make_pydantic_guardrail(SlideDescription),
    #         max_retries=3,
    #         expected_output="JSON in the described format."
    #     )
    # ]
    # ins = [slide.model_dump() for slide in slide_deck_images.slides]
    # atasks = [func(task, ins) for task in tasks]
    # results = await asyncio.gather(*atasks)

    # for task, deck_results in zip(tasks, results):
    #     print(f"xxxxxxxxxxx Task: {task.name} xxxxxxxxxxx")
    #     for i, result in enumerate(deck_results):
    #         print(f"=================== {i} ===================")
    #         pprint(result.pydantic)
    
    # import sys
    # sys.exit()

    # # Execute crew within a Langfuse span, capturing inputs and outputs
    # async def compute(inputs: List[Tuple[int, SlideImage]]) -> AsyncIterable[Tuple[int, BaseModel]]:
    #     ins = [in_.model_dump() for _, in_ in inputs]
    #     results = await crew.kickoff_for_each_async(ins)
    #     for (i, _), result in zip(inputs, results):
    #         yield (i, result.pydantic)


    # if langfuse_client:
    #     with langfuse_client.start_as_current_span(name="slideguard-crewai-trace") as span:
    #         entities = await evaluator.cache_manager.compute_with_cache(
    #             deck_name=presentation_path,
    #             criteria_id="slide_type",
    #             inputs=slide_deck_images.slides,
    #             func=compute
    #         )

    #         span.update_trace(
    #             input=slide_deck_images.model_dump_json(),
    #             output=str([r.model_dump_json() for r in entities]),
    #             tags=["slideguard", "crewai"],
    #         )
        
    #     langfuse_client.flush()
    # else:
    #     entities = await evaluator.cache_manager.compute_with_cache(
    #         deck_name=presentation_path,
    #         criteria_id="slide_type",
    #         inputs=slide_deck_images.slides,
    #         func=compute
    #     )

    # print(entities)


if __name__ == "__main__":
    asyncio.run(main())

