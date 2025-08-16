from pydantic import BaseModel, Field
from slideguard.criteria.base import CriterionInfo
from slideguard.criteria.slide_types import generate_slide_helper_type_prompt

# Generate prompt dynamically from slide type manager
prompt = generate_slide_helper_type_prompt()

class SlideType(BaseModel):
    slide_type: list[str] = Field(description="List of slide types that are most suitable for the slide")

def get_slide_helper_type_prompt(schema_format: str = "{schema_format}", 
                               description: str = "{description}") -> str:
    """Get the slide helper type prompt with dynamic slide type descriptions"""
    return generate_slide_helper_type_prompt(schema_format, description)

slide_helper_type = CriterionInfo(
    criterion_name="Slide Type",
    criterion_type="slide",
    criterion_description="Defining the type of the slide",
    criterion_prompt=prompt,  # This will be replaced dynamically when used
    criterion_schema=SlideType,
    applicable_slide_types=None,  # Applies to all slide types
    priority=1,  # High priority - needed by other criteria
    requires_slide_type=False,
    category="structure"
)