# NOTE: this criterion is not used in the current implementation
prompt = """You are an expert in working with students' presentations.
You will be provided with a screenshot of a presentation slide. 
Your task is to analyze the slide and determine if the infographics on the slide are of good quality and correctly present the intended information.

## Key Visual Elements to Evaluate:
- infographics on the slide which are not background images

## Common Problems to Identify:
- 

## What is not a problem:
- 

## Evaluation Guidelines:
- 

## Response Format:
Your answer should have two sections: Thought and Answer.
First, in the 'Thought' section, write down your reasoning on the task, including an analysis of the slide content, whether there is a visualization on the slide, and how the visualization corresponds to the text content. Make sure you correctly identify the visualizations on the slide, for example, a slide may show a demonstration of a device screen, then the visualization will be the screen itself.
In the Answer section, provide the final evaluation in JSON format with specific visual issues identified, concrete suggestions for improvement, and an overall score from 1 to 5.
"""